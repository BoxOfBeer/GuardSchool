"""Локальное воспроизведение: звонки по расписанию и фон из data/break_music (ffplay)."""
from __future__ import annotations

import logging
import os
import random
import shlex
import shutil
import subprocess
import sys
import threading
import time
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

log = logging.getLogger("guard_school.local_audio")

# После terminate ffplay поток runner ещё освобождает семафор — без паузы новый звонок часто ловит «занято».
_AFTER_STOP_GRACE_SEC = 0.1

_app_module: Any = None

_play_sem = threading.Semaphore(1)
_active_proc: subprocess.Popen | None = None
_proc_guard = threading.Lock()
_play_kind: str = "idle"  # idle | bell | break | test | break_orch_*

_last_playback: dict[str, Any] | None = None
_played_keys: set[str] = set()
_played_day: str | None = None
_played_lock = threading.Lock()

_break_queue: list[Path] = []
_break_queue_day: str | None = None

_break_global_cursor: int = 0
_break_orch_state: dict[str, Any] = {"gap": None}
_orch_music_wait_advance: bool = False
_orch_skip_music_advance: bool = False
_orch_music_path: Path | None = None
_orch_music_started_at: datetime | None = None

_ORCH_KINDS = frozenset(
    {"break", "break_music", "break_orch_end", "break_orch_fade", "break_orch_start"}
)

_ffplay_missing_logged = False
_diag_logged: set[str] = set()
_logged_pc_audio_on = False
# Кэш: есть ли у данного ffmpeg.exe выходной muxer wasapi (в WinGet full build иногда отсутствует).
_ffmpeg_wasapi_muxer_cache: dict[str, bool] = {}


def _payload_sec_window(payload: dict[str, Any], audio: dict[str, Any]) -> int:
    w = payload.get("trigger_sec_window")
    if w is None:
        try:
            w = int(audio.get("bell_trigger_sec_window", 25))
        except (TypeError, ValueError):
            w = 25
    try:
        w = int(w)
    except (TypeError, ValueError):
        w = 25
    return max(5, min(55, w))


def _app() -> Any:
    global _app_module
    if _app_module is None:
        import app

        _app_module = app
    return _app_module


def _creationflags() -> int:
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _ffmpeg_wasapi_muxer_cache_key(ffmpeg_exe: str) -> str:
    try:
        return str(Path(ffmpeg_exe).resolve())
    except OSError:
        return str(ffmpeg_exe)


def ffmpeg_has_wasapi_output_muxer(ffmpeg_exe: str) -> bool:
    """True только если `ffmpeg -f wasapi` поддерживается (иначе — ffplay)."""
    if sys.platform != "win32":
        return False
    key = _ffmpeg_wasapi_muxer_cache_key(ffmpeg_exe)
    if key in _ffmpeg_wasapi_muxer_cache:
        return _ffmpeg_wasapi_muxer_cache[key]
    ok = False
    try:
        r = subprocess.run(
            [ffmpeg_exe, "-hide_banner", "-muxers"],
            capture_output=True,
            text=True,
            timeout=25,
            creationflags=_creationflags(),
        )
        blob = (r.stdout or "") + "\n" + (r.stderr or "")
        for raw_line in blob.splitlines():
            line = raw_line.strip()
            if "wasapi" not in line.lower():
                continue
            # Только выход (muxer): строка с E, не одна буква D (демультиплексор).
            if line.startswith("D ") or line.startswith("D\t"):
                continue
            if line.startswith("E ") or line.startswith("E\t") or "\tE\t" in line:
                ok = True
                break
            if "wasapi" in line.lower() and ("muxer" in line.lower() or "output" in line.lower()):
                if "demux" not in line.lower():
                    ok = True
                    break
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    _ffmpeg_wasapi_muxer_cache[key] = ok
    if not ok:
        log.info(
            "ffmpeg без выхода wasapi (%s) — воспроизведение на ПК через ffplay из того же каталога (SDL).",
            ffmpeg_exe,
        )
    return ok


def _common_windows_ffmpeg_bin_dirs() -> list[Path]:
    """Типичные каталоги, куда кладут ffmpeg-full (не нужно указывать вручную, если совпало)."""
    if sys.platform != "win32":
        return []
    dirs: list[Path | None] = []
    for key in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(key)
        if base:
            dirs.append(Path(base) / "ffmpeg" / "bin")
    dirs.append(Path(r"C:\ffmpeg\bin"))
    dirs.append(Path(__file__).resolve().parent / "ffmpeg" / "bin")
    home = os.environ.get("USERPROFILE", "")
    if home:
        dirs.append(Path(home) / "scoop" / "shims")
        dirs.append(Path(home) / "scoop" / "apps" / "ffmpeg" / "current" / "bin")
    out: list[Path] = []
    seen: set[str] = set()
    for d in dirs:
        if d is None:
            continue
        try:
            key = str(d.resolve())
        except OSError:
            key = str(d)
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def _first_exe_in_dirs(dirs: list[Path], names: tuple[str, ...]) -> str | None:
    for bin_dir in dirs:
        for name in names:
            cand = bin_dir / name
            if cand.is_file():
                return str(cand)
    return None


def _resolve_ffplay(audio: dict[str, Any]) -> str | None:
    custom = str(audio.get("ffmpeg_path") or "").strip().strip('"')
    if custom:
        p = Path(custom)
        if p.is_file():
            parent = p.parent
            for name in ("ffplay.exe", "ffplay"):
                cand = parent / name
                if cand.is_file():
                    return str(cand)
        parent = p if p.is_dir() else None
        if parent:
            for name in ("ffplay.exe", "ffplay"):
                cand = parent / name
                if cand.is_file():
                    return str(cand)
    w = shutil.which("ffplay")
    if w:
        return w
    if sys.platform == "win32":
        w = shutil.which("ffplay.exe")
        if w:
            return w
        found = _first_exe_in_dirs(_common_windows_ffmpeg_bin_dirs(), ("ffplay.exe", "ffplay"))
        if found:
            return found
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        for name in ("ffplay.exe", "ffplay"):
            cand = exe_dir / name
            if cand.is_file():
                return str(cand)
    ff = _resolve_ffmpeg(audio)
    if ff:
        parent = Path(ff).resolve().parent
        for name in ("ffplay.exe", "ffplay"):
            cand = parent / name
            if cand.is_file():
                return str(cand)
    return None


def _resolve_ffmpeg(audio: dict[str, Any]) -> str | None:
    """Тот же каталог, что и в настройке «Путь к ffmpeg.exe»."""
    custom = str(audio.get("ffmpeg_path") or "").strip().strip('"')
    if custom:
        p = Path(custom)
        if p.is_file():
            low = p.name.lower()
            if low.startswith("ffmpeg") and low.endswith((".exe", "ffmpeg")):
                return str(p)
            parent = p.parent
            for name in ("ffmpeg.exe", "ffmpeg"):
                cand = parent / name
                if cand.is_file():
                    return str(cand)
        parent = p if p.is_dir() else None
        if parent:
            for name in ("ffmpeg.exe", "ffmpeg"):
                cand = parent / name
                if cand.is_file():
                    return str(cand)
    w = shutil.which("ffmpeg")
    if w:
        return w
    if sys.platform == "win32":
        w = shutil.which("ffmpeg.exe")
        if w:
            return w
        found = _first_exe_in_dirs(_common_windows_ffmpeg_bin_dirs(), ("ffmpeg.exe", "ffmpeg"))
        if found:
            return found
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        for name in ("ffmpeg.exe", "ffmpeg"):
            cand = exe_dir / name
            if cand.is_file():
                return str(cand)
    return None


def _resolve_ffprobe(audio: dict[str, Any]) -> str | None:
    custom = str(audio.get("ffmpeg_path") or "").strip().strip('"')
    if custom:
        p = Path(custom)
        if p.is_file():
            parent = p.parent
            for name in ("ffprobe.exe", "ffprobe"):
                cand = parent / name
                if cand.is_file():
                    return str(cand)
        parent = p if p.is_dir() else None
        if parent:
            for name in ("ffprobe.exe", "ffprobe"):
                cand = parent / name
                if cand.is_file():
                    return str(cand)
    w = shutil.which("ffprobe")
    if w:
        return w
    if sys.platform == "win32":
        w = shutil.which("ffprobe.exe")
        if w:
            return w
        found = _first_exe_in_dirs(_common_windows_ffmpeg_bin_dirs(), ("ffprobe.exe", "ffprobe"))
        if found:
            return found
    return None


def _media_duration_sec(path: Path, audio: dict[str, Any]) -> float | None:
    probe = _resolve_ffprobe(audio)
    if not probe or not path.is_file():
        return None
    try:
        r = subprocess.run(
            [
                probe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=_creationflags(),
        )
        return float((r.stdout or "").strip())
    except (ValueError, subprocess.TimeoutExpired, OSError):
        return None


def _dt_minute(today: date, minute_of_day: int) -> datetime:
    h, m = divmod(int(minute_of_day), 60)
    return datetime.combine(today, time(hour=h, minute=m))


def _find_break_gap(
    gs: Any,
    entries: list[dict[str, Any]],
    now_mins: int,
    cap: int | None = None,
) -> tuple[int, dict[str, Any], dict[str, Any]] | None:
    """Перемена между строками шаблона; если cap задан — не считать переменой окно перед уроком с номером > cap (нет в расписании)."""
    app = _app()
    for i, e in enumerate(entries):
        if i + 1 >= len(entries):
            return None
        end = gs.time_to_minutes(str(e.get("end") or "00:00"))
        ns = gs.time_to_minutes(str(entries[i + 1].get("start") or "00:00"))
        if end < now_mins < ns:
            if cap is not None:
                nn = app.entry_academic_num(entries[i + 1])
                if nn is not None and nn > cap:
                    continue
            return i, e, entries[i + 1]
    return None


def _orch_lesson_cleanup() -> None:
    global _break_orch_state, _orch_music_wait_advance, _orch_skip_music_advance
    global _orch_music_path, _orch_music_started_at
    with _proc_guard:
        pk = _play_kind
    if pk in _ORCH_KINDS:
        stop_playback_hard()
        time.sleep(_AFTER_STOP_GRACE_SEC)
    _break_orch_state = {"gap": None}
    _orch_music_wait_advance = False
    _orch_skip_music_advance = False
    _orch_music_path = None
    _orch_music_started_at = None


def _orch_poll_music_advance(tracks: list[Path]) -> None:
    global _break_global_cursor, _orch_music_wait_advance, _orch_skip_music_advance
    if not _orch_music_wait_advance or not tracks:
        return
    alive, _ = _proc_alive()
    if alive:
        return
    last = _last_playback
    _orch_music_wait_advance = False
    skip = _orch_skip_music_advance
    _orch_skip_music_advance = False
    if skip:
        return
    # Переходим к следующему треку после любого завершённого фрагмента (в т.ч. обрезанного по времени).
    # Если требовать ok=True, при сбое ffplay очередь застревает на одном файле.
    if last and last.get("finished") and last.get("kind") == "break_music":
        _break_global_cursor = (_break_global_cursor + 1) % len(tracks)


def _allocate_break_tail(total_sec: float, gs: Any) -> tuple[float, float, float, float]:
    """head_sec, fade_sec, silence_sec, start_bell_sec (сумма хвоста = fade+silence+start)."""
    H = float(gs.BREAK_ORCH_HEAD_SEC)
    Fd = float(gs.BREAK_ORCH_FADE_SEC)
    Si = float(gs.BREAK_ORCH_SILENCE_SEC)
    St = float(gs.BREAK_ORCH_START_BELL_SEC)
    ideal_tail = Fd + Si + St
    if total_sec <= 0:
        return 0.0, 0.0, 0.0, 0.0
    if total_sec >= H + ideal_tail + 5:
        return H, Fd, Si, St
    head = min(H, max(20.0, total_sec * 0.17))
    rest = max(0.0, total_sec - head)
    if rest <= 1:
        return head, 0.0, 0.0, 0.0
    ratio = rest / ideal_tail
    fade_s = max(15.0, Fd * ratio)
    silence_s = max(8.0, Si * ratio)
    start_s = max(12.0, St * ratio)
    tail = fade_s + silence_s + start_s
    cap = max(0.0, total_sec - head)
    if tail > cap and tail > 0:
        k = cap / tail
        fade_s, silence_s, start_s = fade_s * k, silence_s * k, start_s * k
    return head, fade_s, silence_s, start_s


def _tick_break_orchestration(
    gs: Any,
    screen: dict[str, Any],
    today: date,
    now: datetime,
    audio: dict[str, Any],
    status: dict[str, Any],
    today_iso: str,
    vbell: int,
    vb_break: int,
) -> None:
    global _break_orch_state, _orch_music_wait_advance, _orch_skip_music_advance
    global _orch_music_path, _orch_music_started_at

    entries = status.get("entries") or []
    now_mins = now.hour * 60 + now.minute
    try:
        tw = int(audio.get("bell_trigger_sec_window", gs.DEFAULT_BELL_TRIGGER_SEC_WINDOW))
    except (TypeError, ValueError):
        tw = gs.DEFAULT_BELL_TRIGGER_SEC_WINDOW
    payload = gs.build_bell_audio_payload(screen, today, trigger_sec_window=tw)
    rows = payload.get("entries") or []
    cap_raw = payload.get("max_lesson_index_cap")
    try:
        gap_cap: int | None = int(cap_raw) if cap_raw is not None else None
    except (TypeError, ValueError):
        gap_cap = None

    gap = _find_break_gap(gs, entries, now_mins, gap_cap)
    force_skip_head = False
    gap_key: str
    B: datetime
    T: datetime
    sound_end_url: str | None
    sound_start_url: str | None

    start_row_for_orch_mark: dict[str, Any] | None = None

    if not gap and status.get("state") == "before" and entries:
        pre_m = int(getattr(gs, "MORNING_PRE_FIRST_LESSON_MIN", 30))
        raw_start = str(entries[0].get("start") or "08:00")
        try:
            hp, mp = raw_start.split(":")
            T = datetime.combine(today, time(int(hp), int(mp)))
        except (TypeError, ValueError):
            return
        B = T - timedelta(minutes=max(5, pre_m))
        gap_key = f"{today_iso}_morning0"
        if now < B:
            gk = str(_break_orch_state.get("gap") or "")
            if gk.endswith("_morning0"):
                _orch_lesson_cleanup()
            return
        if now >= T:
            return
        sound_end_url = None
        sound_start_url = rows[0].get("sound_start") if rows else None
        force_skip_head = True
        start_row_for_orch_mark = rows[0] if rows else None
    else:
        if not gap:
            return
        gap_i, ended_entry, next_entry = gap
        next_start_m = gs.time_to_minutes(str(next_entry.get("start") or "00:00"))
        gap_key = f"{today_iso}_{gap_i}_{next_start_m}"
        end_m = gs.time_to_minutes(str(ended_entry.get("end") or "00:00"))
        B = _dt_minute(today, end_m) + timedelta(minutes=1)
        T = _dt_minute(today, next_start_m)
        sound_end_url = rows[gap_i].get("sound_end") if gap_i < len(rows) else None
        sound_start_url = (
            rows[gap_i + 1].get("sound_start") if gap_i + 1 < len(rows) else None
        )
        if gap_i + 1 < len(rows):
            start_row_for_orch_mark = rows[gap_i + 1]

    if _break_orch_state.get("gap") != gap_key:
        did_end_init = bool(force_skip_head)
        if not force_skip_head and gap is not None:
            _ge_i, ended_e, _gn = gap
            ei = ended_e.get("index")
            if ei is not None:
                with _played_lock:
                    did_end_init = f"{today_iso}_{int(ei)}_e" in _played_keys
        _break_orch_state = {
            "gap": gap_key,
            "did_end": did_end_init,
            "did_fade": False,
            "did_start": False,
        }
        _orch_music_wait_advance = False
        _orch_skip_music_advance = False
        _orch_music_path = None
        _orch_music_started_at = None

    total_sec = (T - B).total_seconds()
    if total_sec < 30:
        return

    head_s, fade_s, silence_s, start_s = _allocate_break_tail(total_sec, gs)
    tail = fade_s + silence_s + start_s
    if force_skip_head:
        head_s = 0.0
        _break_orch_state["did_end"] = True
    else:
        head_s = min(head_s, max(10.0, total_sec - tail - 5))
    head_end = B + timedelta(seconds=head_s)
    music_hard_end = T - timedelta(seconds=tail)
    t_fade_start = music_hard_end
    t_fade_end = t_fade_start + timedelta(seconds=fade_s)
    t_start_bell = T - timedelta(seconds=start_s)

    tracks = _list_break_tracks(gs)
    _orch_poll_music_advance(tracks)

    alive, _ = _proc_alive()

    if (
        now >= t_fade_end
        and not _break_orch_state.get("did_fade")
        and now < T
    ):
        _break_orch_state["did_fade"] = True
        _orch_skip_music_advance = True
        _orch_music_wait_advance = False
        if alive:
            stop_playback_hard()
            time.sleep(_AFTER_STOP_GRACE_SEC)

    if now < head_end:
        if (
            not _break_orch_state.get("did_end")
            and sound_end_url
            and not alive
        ):
            p = gs.bell_audio_url_to_path(sound_end_url)
            if p and p.is_file():
                rem = max(8.0, (head_end - now).total_seconds())
                cap = min(70.0, rem, head_s + 10.0)
                r_ok, _ = play_file_async(
                    p,
                    vbell,
                    audio,
                    kind="break_orch_end",
                    max_seconds=int(cap) + 45,
                    duration_cap_sec=cap,
                    afade_in_sec=1.0,
                )
                if r_ok:
                    _break_orch_state["did_end"] = True
        return

    if head_end <= now < t_fade_start and tracks:
        if alive and _play_kind == "break_orch_end":
            stop_playback_hard()
            time.sleep(_AFTER_STOP_GRACE_SEC)
        alive, _ = _proc_alive()
        if alive:
            return
        if _orch_music_wait_advance:
            return
        room = (t_fade_start - now).total_seconds()
        # Раньше: room < 12 и dur > room — вторая мелодия часто не запускалась. Играем фрагмент по оставшемуся окну.
        if room < 2.0:
            return
        n = len(tracks)
        idx = _break_global_cursor % n
        path = tracks[idx]
        dur = _media_duration_sec(path, audio) or 3600.0
        play_len = min(dur, max(room - 1.0, 3.0))
        if play_len < 3.0:
            return
        r_ok, _ = play_file_async(
            path,
            vb_break,
            audio,
            kind="break_music",
            max_seconds=min(int(play_len) + 60, 7200),
            duration_cap_sec=play_len,
        )
        if r_ok:
            _orch_music_path = path
            _orch_music_started_at = now
            _orch_music_wait_advance = True
        return

    if head_end <= now < t_fade_start and not tracks:
        return

    if t_fade_start <= now < t_fade_end:
        if _break_orch_state.get("did_fade"):
            return
        _orch_skip_music_advance = True
        _orch_music_wait_advance = False
        if alive:
            stop_playback_hard()
            time.sleep(_AFTER_STOP_GRACE_SEC)
        _break_orch_state["did_fade"] = True
        path = _orch_music_path
        fade_len = min(fade_s, max(8.0, (t_fade_end - now).total_seconds()))
        if path and path.is_file() and _orch_music_started_at and fade_len > 10:
            dur = _media_duration_sec(path, audio) or 300.0
            elapsed = max(0.0, (now - _orch_music_started_at).total_seconds())
            ss = min(max(0.0, elapsed - 1.0), max(0.0, dur - fade_len - 1.0))
            play_file_async(
                path,
                vb_break,
                audio,
                kind="break_orch_fade",
                max_seconds=int(fade_len) + 30,
                input_start_sec=ss,
                duration_cap_sec=fade_len,
                afade_out_sec=fade_len,
            )
        return

    if t_fade_end <= now < t_start_bell:
        if alive and _play_kind in _ORCH_KINDS:
            stop_playback_hard()
        return

    if t_start_bell <= now < T:
        if not _break_orch_state.get("did_start") and sound_start_url:
            p = gs.bell_audio_url_to_path(sound_start_url)
            if p and p.is_file():
                rem = max(5.0, (T - now).total_seconds())
                cap = min(70.0, rem, start_s + 5.0)
                if not alive:
                    r_ok, _ = play_file_async(
                        p,
                        vbell,
                        audio,
                        kind="break_orch_start",
                        max_seconds=int(cap) + 45,
                        duration_cap_sec=cap,
                        afade_in_sec=1.0,
                    )
                    if r_ok:
                        _break_orch_state["did_start"] = True
                        if start_row_for_orch_mark is not None:
                            ri = start_row_for_orch_mark.get("index")
                            if ri is not None:
                                with _played_lock:
                                    _played_keys.add(f"{today_iso}_{int(ri)}_s")
        return


def stop_playback_hard() -> None:
    global _active_proc, _play_kind, _last_playback
    killed = False
    with _proc_guard:
        proc = _active_proc
        if proc is None or proc.poll() is not None:
            _active_proc = None
            _play_kind = "idle"
            return
        try:
            proc.terminate()
            proc.wait(timeout=3)
            killed = True
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=2)
                killed = True
            except Exception:
                pass
        _active_proc = None
        _play_kind = "idle"
    if killed:
        _last_playback = {
            "at": datetime.now().isoformat(timespec="seconds"),
            "returncode": 0,
            "stderr": "Остановлено вручную.",
            "stdout": "",
            "command": "",
            "ok": True,
            "finished": True,
            "kind": "stopped",
            "backend": "user-stop",
        }


def stop_playback() -> dict[str, Any]:
    stop_playback_hard()
    return {"ok": True, "detail": "Воспроизведение остановлено."}


def get_last_playback() -> dict[str, Any] | None:
    return _last_playback


def get_break_music_playback_info() -> dict[str, Any]:
    """Снимок для админки: громкости, режим (оркестрация / простой плейлист), порядок треков и «следующий»."""
    gs = _app()
    cfg = gs.load_config()
    audio = gs.sanitize_audio_stream(cfg.get("audio_stream"))
    tracks = _list_break_tracks(gs)
    names = [p.name for p in tracks]
    n = len(names)

    try:
        vb = max(0, min(100, int(audio.get("volume_percent") or 80)))
    except (TypeError, ValueError):
        vb = 80
    try:
        vbr = max(0, min(100, int(audio.get("break_music_volume_percent") or 40)))
    except (TypeError, ValueError):
        vbr = 40

    break_on = bool(audio.get("break_music_on_breaks"))
    orch = bool(
        break_on
        and audio.get("use_bell_schedule")
        and audio.get("use_bell_sound_files")
    )

    cursor = _break_global_cursor
    bq = list(_break_queue)
    bqd = _break_queue_day
    today_iso = date.today().isoformat()

    with _proc_guard:
        pk = _play_kind

    out: dict[str, Any] = {
        "volume_bell_percent": vb,
        "volume_break_percent": vbr,
        "volume_break_ffmpeg": round(vbr / 100.0, 4),
        "break_music_enabled": break_on,
        "orchestration": orch,
        "play_kind": pk,
        "sorted_filenames": names,
        "queue_date": bqd,
        "orchestration_cursor": cursor,
        "simple_queue_filenames": [p.name for p in bq],
    }

    if not break_on:
        out["mode"] = "off"
        out["mode_label"] = "Фон на переменах выключен"
        out["order_note"] = "Включите «Фон на переменах» и сохраните конфиг."
        out["ordered_rows"] = []
        return out

    if n == 0:
        out["mode"] = "empty"
        out["mode_label"] = "Нет аудиофайлов"
        out["order_note"] = "Положите mp3/wav в data/break_music."
        out["ordered_rows"] = []
        return out

    if orch:
        out["mode"] = "orchestration"
        out["mode_label"] = "Оркестрация перемен (расписание + файлы звонков + фон)"
        ni = cursor % n
        out["next_index_1based"] = ni + 1
        out["next_filename"] = names[ni]
        out["order_note"] = (
            "Музыка на перемене: файлы по алфавиту имён; после каждого сыгранного трека — следующий по списку, с конца в начало. "
            f"Сейчас указатель очереди: {ni + 1} из {n} (следующий файл — «{names[ni]}»). Громкость этой музыки и затухания — {vbr}%."
        )
        out["ordered_rows"] = [
            {"i": i + 1, "filename": fn, "is_next": i == ni}
            for i, fn in enumerate(names)
        ]
        return out

    out["mode"] = "simple_shuffle"
    out["mode_label"] = "Простой фон (без оркестрации перемен)"
    if bq:
        out["next_filename"] = bq[0].name
        out["next_index_1based"] = 1
        out["order_note"] = (
            f"Очередь на день {bqd or today_iso}: случайный порядок при первом обращении к перемене; дальше — по кругу с начала списка. "
            f"Следующий трек: «{bq[0].name}». Громкость фона — {vbr}%."
        )
        out["ordered_rows"] = [
            {"i": i + 1, "filename": p.name, "is_next": i == 0}
            for i, p in enumerate(bq)
        ]
    else:
        out["next_filename"] = None
        out["next_index_1based"] = None
        out["order_note"] = (
            "Очередь на сегодня ещё не построена (случайное перемешивание при первом тике в состоянии «Перемена»). "
            f"Ниже — файлы на диске по алфавиту; реальный порядок воспроизведения будет случайным. Громкость фона — {vbr}%."
        )
        out["ordered_rows"] = [
            {"i": i + 1, "filename": fn, "is_next": False}
            for i, fn in enumerate(names)
        ]
    return out


def _proc_alive() -> tuple[bool, int | None]:
    with _proc_guard:
        proc = _active_proc
        if proc is not None and proc.poll() is None:
            return True, proc.pid
        return False, None


def get_status() -> dict[str, Any]:
    alive, pid = _proc_alive()
    out: dict[str, Any] = {
        "ffmpeg_process_running": alive,
        "pid": pid,
        "stream_slot_busy": alive,
        "last": _last_playback,
        "play_kind": _play_kind,
    }
    try:
        gs = _app()
        cfg = gs.load_config()
        audio = gs.sanitize_audio_stream(cfg.get("audio_stream"))
        out["pc_audio_enabled"] = bool(audio.get("enabled"))
        out["use_bell_schedule"] = bool(audio.get("use_bell_schedule"))
        out["use_bell_sound_files"] = bool(audio.get("use_bell_sound_files"))
        try:
            vb = int(audio.get("volume_percent") or 80)
            out["volume_bell_percent"] = max(0, min(100, vb))
        except (TypeError, ValueError):
            out["volume_bell_percent"] = 80
        try:
            vbr = int(audio.get("break_music_volume_percent") or 40)
            out["volume_break_percent"] = max(0, min(100, vbr))
        except (TypeError, ValueError):
            out["volume_break_percent"] = 40
        ff = _resolve_ffmpeg(audio)
        fp = _resolve_ffplay(audio)
        out["resolved_ffmpeg"] = ff
        out["resolved_ffplay"] = fp
        if sys.platform == "win32" and ff and ffmpeg_has_wasapi_output_muxer(ff):
            out["pc_playback_backend_hint"] = "ffmpeg-wasapi"
        elif fp:
            out["pc_playback_backend_hint"] = "ffplay"
        else:
            out["pc_playback_backend_hint"] = None
    except Exception:
        out["pc_audio_enabled"] = None
        out["resolved_ffmpeg"] = None
        out["resolved_ffplay"] = None
        out["pc_playback_backend_hint"] = None
    return out


def _reset_day(today_iso: str) -> None:
    global _played_day, _played_keys, _break_queue, _break_queue_day, _diag_logged
    global _break_global_cursor, _break_orch_state, _orch_music_wait_advance
    global _orch_skip_music_advance, _orch_music_path, _orch_music_started_at
    if _played_day != today_iso:
        _played_day = today_iso
        with _played_lock:
            _played_keys.clear()
        _break_queue = []
        _break_queue_day = None
        _diag_logged.clear()
        _break_global_cursor = 0
        _break_orch_state = {"gap": None}
        _orch_music_wait_advance = False
        _orch_skip_music_advance = False
        _orch_music_path = None
        _orch_music_started_at = None


def _try_mark(key: str) -> bool:
    with _played_lock:
        if key in _played_keys:
            return False
        _played_keys.add(key)
        return True


def _unmark(key: str) -> None:
    with _played_lock:
        _played_keys.discard(key)


def _pick_source_screen(cfg: dict[str, Any], audio: dict[str, Any]) -> dict[str, Any] | None:
    screens = cfg.get("screens") or []
    if not screens:
        return None
    sid = str(audio.get("source_screen_id") or "").strip()
    if sid:
        for s in screens:
            if str(s.get("id")) == sid:
                return s
    return screens[0]


def _list_break_tracks(gs: Any) -> list[Path]:
    d = gs.BREAK_MUSIC_DIR
    exts = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.suffix.lower() in exts and p.is_file())


def _ensure_break_queue(_gs: Any, tracks: list[Path], today_iso: str) -> None:
    global _break_queue, _break_queue_day
    if _break_queue_day != today_iso:
        _break_queue = []
        _break_queue_day = today_iso
    if not tracks:
        _break_queue = []
        return
    if not _break_queue:
        q = list(tracks)
        random.shuffle(q)
        _break_queue = q


def play_file_async(
    path: Path,
    volume_percent: int,
    audio: dict[str, Any],
    *,
    kind: str,
    max_seconds: int = 3600,
    afade_in_sec: float | None = None,
    duration_cap_sec: float | None = None,
    input_start_sec: float | None = None,
    afade_out_sec: float | None = None,
) -> tuple[bool, str]:
    global _ffplay_missing_logged, _active_proc, _last_playback, _play_kind
    if not path.is_file():
        return False, "Файл не найден."

    ffmpeg_exe = _resolve_ffmpeg(audio) if sys.platform == "win32" else None
    use_wasapi = bool(ffmpeg_exe) and ffmpeg_has_wasapi_output_muxer(ffmpeg_exe)
    ffplay = _resolve_ffplay(audio)
    if not use_wasapi and not ffplay:
        if not _ffplay_missing_logged:
            log.warning(
                "Нет ffplay (рядом с ffmpeg или в PATH). Установите полный комплект ffmpeg с ffplay.exe.",
            )
            _ffplay_missing_logged = True
        return False, (
            "Не найден ffplay.exe. Рядом с ffmpeg.exe из WinGet обычно есть ffplay — добавьте папку …\\bin в PATH "
            "или укажите полный путь к ffmpeg.exe в настройках (ffplay ищется в той же папке)."
        )

    if not _play_sem.acquire(blocking=False):
        return False, "Уже идёт воспроизведение."

    vol = max(0.0, min(1.0, volume_percent / 100.0))
    fade_in = float(afade_in_sec) if afade_in_sec is not None else 0.0
    fade_out = float(afade_out_sec) if afade_out_sec is not None else 0.0
    parts: list[str] = []
    if fade_out > 0:
        parts.append(f"afade=t=out:st=0:d={fade_out:g}")
    if fade_in > 0:
        parts.append(f"afade=t=in:st=0:d={fade_in:g}")
    parts.append(f"volume={vol}")
    af = ",".join(parts)
    iss = float(input_start_sec) if input_start_sec is not None else 0.0
    cap = float(duration_cap_sec) if duration_cap_sec is not None else 0.0

    play_env: dict[str, str] | None = None
    if use_wasapi:
        cmd = [
            ffmpeg_exe,
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "error",
            "-fflags",
            "+discardcorrupt",
        ]
        if iss > 0:
            cmd.extend(["-ss", f"{iss:g}"])
        cmd.extend(["-i", str(path)])
        if cap > 0:
            cmd.extend(["-t", f"{cap:g}"])
        cmd.extend(["-af", af, "-f", "wasapi", "default"])
        busy_msg = "Идёт воспроизведение (ffmpeg WASAPI → устройство по умолчанию)…"
        backend = "ffmpeg-wasapi"
    else:
        cmd = [
            ffplay,
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "error",
            "-fflags",
            "+discardcorrupt",
        ]
        if iss > 0:
            cmd.extend(["-ss", f"{iss:g}"])
        if cap > 0:
            cmd.extend(["-t", f"{cap:g}"])
        cmd.extend(["-af", af, "-i", str(path)])
        busy_msg = "Идёт ffplay…"
        backend = "ffplay"
        if sys.platform == "win32":
            play_env = os.environ.copy()
            play_env["SDL_AUDIODRIVER"] = "wasapi"

    cmd_shell = " ".join(shlex.quote(str(x)) for x in cmd)

    def runner() -> None:
        global _last_playback, _active_proc, _play_kind
        try:
            _play_kind = kind
            _last_playback = {
                "at": datetime.now().isoformat(timespec="seconds"),
                "returncode": None,
                "stderr": busy_msg,
                "stdout": "",
                "command": cmd_shell,
                "command_preview": cmd_shell[:2000],
                "ok": None,
                "finished": False,
                "kind": kind,
                "backend": backend,
            }
            try:
                # argv list + shlex only for logging — no shell=True (injection-safe).
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=_creationflags(),
                    env=play_env,
                )
                with _proc_guard:
                    _active_proc = proc
                try:
                    out_b, err_b = proc.communicate(timeout=max_seconds)
                except subprocess.TimeoutExpired:
                    stop_playback_hard()
                    _last_playback = {
                        "at": datetime.now().isoformat(timespec="seconds"),
                        "returncode": None,
                        "stderr": f"Прервано по таймауту {max_seconds} с.",
                        "stdout": "",
                        "command": cmd_shell,
                        "ok": False,
                        "finished": True,
                        "kind": kind,
                        "backend": backend,
                    }
                    return
                finally:
                    with _proc_guard:
                        if _active_proc is proc:
                            _active_proc = None
                    _play_kind = "idle"
                err = (err_b or "").strip()
                rc = proc.returncode if proc.returncode is not None else -1
                if use_wasapi:
                    ok = rc == 0
                else:
                    ok = rc in (0, 255)  # ffplay иногда 255 при -autoexit
                _last_playback = {
                    "at": datetime.now().isoformat(timespec="seconds"),
                    "returncode": rc,
                    "stderr": err[-8000:] if err else "",
                    "stdout": (out_b or "").strip()[-2000:] if out_b else "",
                    "command": cmd_shell,
                    "ok": ok,
                    "finished": True,
                    "kind": kind,
                    "backend": backend,
                }
                if not ok:
                    log.warning("%s код %s: %s", backend, rc, err[:800] if err else "")
            except Exception:
                log.exception("local_audio: %s", backend)
                _last_playback = {
                    "at": datetime.now().isoformat(timespec="seconds"),
                    "returncode": None,
                    "stderr": f"Ошибка запуска {backend} — см. лог.",
                    "command": cmd_shell,
                    "ok": False,
                    "finished": True,
                    "kind": kind,
                    "backend": backend,
                }
                with _proc_guard:
                    _play_kind = "idle"
        finally:
            _play_sem.release()

    threading.Thread(target=runner, daemon=True).start()
    return True, ""


def tick_once() -> None:
    global _logged_pc_audio_on
    gs = _app()
    cfg = gs.load_config()
    audio = gs.sanitize_audio_stream(cfg.get("audio_stream"))
    if not audio.get("enabled"):
        _logged_pc_audio_on = False
        return
    if not _logged_pc_audio_on:
        log.info(
            "Звук на ПК: Windows — при наличии muxer wasapi в ffmpeg он; иначе ffplay рядом. Экран-источник: «%s».",
            audio.get("source_screen_id") or "(первый экран)",
        )
        _logged_pc_audio_on = True

    screen = _pick_source_screen(cfg, audio)
    if not screen:
        return

    today = date.today()
    today_iso = today.isoformat()
    _reset_day(today_iso)

    now = datetime.now()
    now_mins = now.hour * 60 + now.minute
    secs = now.second

    try:
        vbell = int(audio.get("volume_percent") or 80)
        vbell = max(0, min(100, vbell))
    except (TypeError, ValueError):
        vbell = 80
    try:
        vb_break = int(audio.get("break_music_volume_percent") or 40)
        vb_break = max(0, min(100, vb_break))
    except (TypeError, ValueError):
        vb_break = 40

    status = gs.build_bell_status(screen, today)
    orch = (
        bool(audio.get("break_music_on_breaks"))
        and bool(audio.get("use_bell_schedule"))
        and bool(audio.get("use_bell_sound_files"))
    )

    if audio.get("use_bell_schedule") and audio.get("use_bell_sound_files"):
        try:
            tw = int(audio.get("bell_trigger_sec_window", gs.DEFAULT_BELL_TRIGGER_SEC_WINDOW))
        except (TypeError, ValueError):
            tw = gs.DEFAULT_BELL_TRIGGER_SEC_WINDOW
        payload = gs.build_bell_audio_payload(screen, today, trigger_sec_window=tw)
        sec_win = _payload_sec_window(payload, audio)
        lead = int(gs.PRE_BELL_LEAD_MINUTES)
        pre_fire = int(gs.PRE_BELL_FIRE_SEC_WINDOW)
        pre_dur = float(gs.PRE_BELL_MAX_DURATION_SEC)
        pre_fade = float(gs.PRE_BELL_AFADE_IN_SEC)
        if (
            payload.get("entries")
            and payload.get("day") == today_iso
            and status.get("state") != "done"
        ):
            for row in payload["entries"]:
                idx = row.get("index")
                st = gs.time_to_minutes(str(row.get("start") or "00:00"))
                en = gs.time_to_minutes(str(row.get("end") or "00:00"))
                base = f"{today_iso}_{idx}"
                pre_st_min = st - lead
                if pre_st_min >= 0 and now_mins == pre_st_min and secs < pre_fire and row.get("sound_start"):
                    pk_pre = f"pre_{base}_s"
                    if _try_mark(pk_pre):
                        with _proc_guard:
                            br = _play_kind == "break" and _active_proc is not None and _active_proc.poll() is None
                        if br:
                            stop_playback_hard()
                            time.sleep(_AFTER_STOP_GRACE_SEC)
                        p_pre = gs.bell_audio_url_to_path(row["sound_start"])
                        if p_pre:
                            r_ok, r_err = play_file_async(
                                p_pre,
                                vbell,
                                audio,
                                kind="pre_bell",
                                max_seconds=int(pre_dur) + 90,
                                afade_in_sec=pre_fade,
                                duration_cap_sec=pre_dur,
                            )
                            if not r_ok:
                                _unmark(pk_pre)
                                if r_err:
                                    log.warning("Предзвонок начало: %s", r_err)
                        else:
                            _unmark(pk_pre)
                pre_en_min = en - lead
                if pre_en_min >= 0 and now_mins == pre_en_min and secs < pre_fire and row.get("sound_end"):
                    pk_pre = f"pre_{base}_e"
                    if _try_mark(pk_pre):
                        with _proc_guard:
                            br = _play_kind == "break" and _active_proc is not None and _active_proc.poll() is None
                        if br:
                            stop_playback_hard()
                            time.sleep(_AFTER_STOP_GRACE_SEC)
                        p_pre = gs.bell_audio_url_to_path(row["sound_end"])
                        if p_pre:
                            r_ok, r_err = play_file_async(
                                p_pre,
                                vbell,
                                audio,
                                kind="pre_bell",
                                max_seconds=int(pre_dur) + 90,
                                afade_in_sec=pre_fade,
                                duration_cap_sec=pre_dur,
                            )
                            if not r_ok:
                                _unmark(pk_pre)
                                if r_err:
                                    log.warning("Предзвонок конец: %s", r_err)
                        else:
                            _unmark(pk_pre)
                if now_mins == st and secs < sec_win:
                    if not row.get("sound_start"):
                        dk = f"{base}_no_start"
                        if dk not in _diag_logged:
                            _diag_logged.add(dk)
                            log.warning(
                                "Время начала строки %s (%s), но нет sound_start "
                                "(и нет дефолта «начало» в шаблоне) — на ПК тишина.",
                                idx,
                                row.get("start"),
                            )
                    else:
                        k = f"{base}_s"
                        if _try_mark(k):
                            p = gs.bell_audio_url_to_path(row["sound_start"])
                            if p:
                                stop_playback_hard()
                                time.sleep(_AFTER_STOP_GRACE_SEC)
                                r_ok, r_err = play_file_async(p, vbell, audio, kind="bell", max_seconds=180)
                                if not r_ok:
                                    _unmark(k)
                                if not r_ok and r_err:
                                    log.warning("Звонок начало: %s", r_err)
                            else:
                                _unmark(k)
                                dk = f"{base}_path_start"
                                if dk not in _diag_logged:
                                    _diag_logged.add(dk)
                                    log.warning(
                                        "sound_start=%s нет на диске (uploads/bells).",
                                        row.get("sound_start"),
                                    )
                if now_mins == en and secs < sec_win:
                    if not row.get("sound_end"):
                        dk = f"{base}_no_end"
                        if dk not in _diag_logged:
                            _diag_logged.add(dk)
                            log.warning(
                                "Время конца строки %s (%s), но нет sound_end "
                                "(и нет дефолта «конец» в шаблоне звонков) — на ПК тишина. "
                                "Окончание урока ≠ начало следующего.",
                                idx,
                                row.get("end"),
                            )
                    else:
                        k = f"{base}_e"
                        if _try_mark(k):
                            p = gs.bell_audio_url_to_path(row["sound_end"])
                            if p:
                                stop_playback_hard()
                                time.sleep(_AFTER_STOP_GRACE_SEC)
                                r_ok, r_err = play_file_async(p, vbell, audio, kind="bell", max_seconds=180)
                                if not r_ok:
                                    _unmark(k)
                                if not r_ok and r_err:
                                    log.warning("Звонок конец: %s", r_err)
                            else:
                                _unmark(k)
                                dk = f"{base}_path_end"
                                if dk not in _diag_logged:
                                    _diag_logged.add(dk)
                                    log.warning(
                                        "sound_end=%s нет на диске (uploads/bells).",
                                        row.get("sound_end"),
                                    )

    if orch:
        if status.get("state") in ("break", "before"):
            _tick_break_orchestration(
                gs, screen, today, now, audio, status, today_iso, vbell, vb_break
            )
        else:
            _orch_lesson_cleanup()
        return

    if not audio.get("break_music_on_breaks"):
        return

    if status.get("state") != "break":
        with _proc_guard:
            pk = _play_kind
            proc = _active_proc
        if pk == "break" and proc is not None and proc.poll() is None:
            stop_playback_hard()
        return

    tracks = _list_break_tracks(gs)
    if not tracks:
        return

    alive, _ = _proc_alive()
    if alive:
        return

    _ensure_break_queue(gs, tracks, today_iso)
    if not _break_queue:
        return
    nxt = _break_queue.pop(0)
    _break_queue.append(nxt)
    play_file_async(nxt, vb_break, audio, kind="break", max_seconds=7200)


def describe_pc_audio_preview(
    screen: dict[str, Any],
    audio_stream_raw: dict[str, Any] | None,
) -> dict[str, Any]:
    """Предпросмотр: структурированные события для i18n на клиенте (ключи preview.pcAudio.*)."""
    gs = _app()
    audio = gs.sanitize_audio_stream(audio_stream_raw)
    today = date.today()
    now = datetime.now()
    today_iso = today.isoformat()
    events: list[dict[str, Any]] = []
    tw = gs.audio_trigger_sec_window(audio)
    try:
        twp = int(audio.get("bell_trigger_sec_window", gs.DEFAULT_BELL_TRIGGER_SEC_WINDOW))
    except (TypeError, ValueError):
        twp = gs.DEFAULT_BELL_TRIGGER_SEC_WINDOW
    payload = gs.build_bell_audio_payload(screen, today, trigger_sec_window=twp)
    status = gs.build_bell_status(screen, today)
    st = get_status()
    now_m = now.hour * 60 + now.minute
    secs = now.second

    events.append(
        {
            "key": "preview.pcAudio.header",
            "params": {"serverTime": now.strftime("%Y-%m-%d %H:%M:%S"), "tw": tw},
        }
    )
    try:
        vp_bell = max(0, min(100, int(audio.get("volume_percent") or 80)))
    except (TypeError, ValueError):
        vp_bell = 80
    try:
        vp_br = max(0, min(100, int(audio.get("break_music_volume_percent") or 40)))
    except (TypeError, ValueError):
        vp_br = 40
    events.append(
        {
            "key": "preview.pcAudio.pcFlags",
            "params": {
                "enabled": bool(audio.get("enabled")),
                "useSchedule": bool(audio.get("use_bell_schedule")),
                "useFiles": bool(audio.get("use_bell_sound_files")),
                "breakMusic": bool(audio.get("break_music_on_breaks")),
            },
        }
    )
    events.append({"key": "preview.pcAudio.volumes", "params": {"vpBell": vp_bell, "vpBr": vp_br}})

    if payload.get("day") != today_iso:
        events.append(
            {
                "key": "preview.pcAudio.dayMismatch",
                "params": {"bellDay": str(payload.get("day")), "today": today_iso},
            }
        )

    state = status.get("state") or "?"
    events.append({"key": "preview.pcAudio.slot", "params": {"state": str(state), "message": str(status.get("message", ""))}})

    orch = bool(
        audio.get("break_music_on_breaks")
        and audio.get("use_bell_schedule")
        and audio.get("use_bell_sound_files")
    )
    if orch:
        events.append({"key": "preview.pcAudio.orchIntro", "params": {}})
        if state == "before":
            pm = int(getattr(gs, "MORNING_PRE_FIRST_LESSON_MIN", 30))
            events.append({"key": "preview.pcAudio.orchMorning", "params": {"minutes": pm}})
        elif state != "break":
            events.append({"key": "preview.pcAudio.orchLesson", "params": {}})

    tv_keys: set[tuple[Any, str, int]] = set()
    rows = payload.get("entries") or []
    for row in rows:
        idx = row.get("index")
        st_m = gs.time_to_minutes(str(row.get("start") or "00:00"))
        en_m = gs.time_to_minutes(str(row.get("end") or "00:00"))
        for lab_key, minute, url in (
            ("start", st_m, row.get("sound_start")),
            ("end", en_m, row.get("sound_end")),
        ):
            if not url:
                continue
            key = (idx, lab_key, minute)
            if key in tv_keys:
                continue
            tv_keys.add(key)
            hm = f"{minute // 60:02d}:{minute % 60:02d}"
            slot = _dt_minute(today, minute)
            win_end = slot + timedelta(seconds=tw)
            if now_m == minute:
                if secs < tw:
                    events.append(
                        {
                            "key": "preview.pcAudio.tvActive",
                            "params": {"idx": idx, "bellKind": lab_key, "hm": hm, "remainSec": tw - secs},
                        }
                    )
                else:
                    events.append(
                        {
                            "key": "preview.pcAudio.tvMissed",
                            "params": {"idx": idx, "bellKind": lab_key, "hm": hm, "secs": secs, "tw": tw},
                        }
                    )
            elif win_end < now < slot + timedelta(minutes=15):
                events.append(
                    {
                        "key": "preview.pcAudio.tvPassed",
                        "params": {"idx": idx, "bellKind": lab_key, "hm": hm, "tw": tw},
                    }
                )

    if orch and state == "break":
        entries = status.get("entries") or []
        cap_raw = payload.get("max_lesson_index_cap")
        try:
            gap_cap: int | None = int(cap_raw) if cap_raw is not None else None
        except (TypeError, ValueError):
            gap_cap = None
        gap = _find_break_gap(gs, entries, now_m, gap_cap)
        if gap:
            _gap_i, ended_entry, next_entry = gap
            next_start_m = gs.time_to_minutes(str(next_entry.get("start") or "00:00"))
            end_m = gs.time_to_minutes(str(ended_entry.get("end") or "00:00"))
            B = _dt_minute(today, end_m) + timedelta(minutes=1)
            T = _dt_minute(today, next_start_m)
            total_sec = (T - B).total_seconds()
            if total_sec >= 30:
                head_s, fade_s, silence_s, start_s = _allocate_break_tail(total_sec, gs)
                tail = fade_s + silence_s + start_s
                head_s = min(head_s, max(10.0, total_sec - tail - 5))
                head_end = B + timedelta(seconds=head_s)
                music_hard_end = T - timedelta(seconds=tail)
                t_fade_end = music_hard_end + timedelta(seconds=fade_s)
                t_start_bell = T - timedelta(seconds=start_s)
                tracks = _list_break_tracks(gs)
                n = len(tracks)
                ct = _break_global_cursor % n if n else 0
                cur = tracks[ct].name if n else "—"
                if now < head_end:
                    events.append(
                        {
                            "key": "preview.pcAudio.pcPhaseEndLesson",
                            "params": {
                                "headEnd": head_end.strftime("%H:%M:%S"),
                                "remainSec": max(0, int((head_end - now).total_seconds())),
                            },
                        }
                    )
                elif head_end <= now < music_hard_end:
                    events.append(
                        {
                            "key": "preview.pcAudio.pcPhaseMusic",
                            "params": {
                                "ct": ct + 1,
                                "n": n,
                                "cur": cur,
                                "musicHardEnd": music_hard_end.strftime("%H:%M:%S"),
                                "remainSec": max(0, int((music_hard_end - now).total_seconds())),
                            },
                        }
                    )
                elif music_hard_end <= now < t_fade_end:
                    events.append(
                        {
                            "key": "preview.pcAudio.pcPhaseFade",
                            "params": {
                                "tFadeEnd": t_fade_end.strftime("%H:%M:%S"),
                                "remainSec": max(0, int((t_fade_end - now).total_seconds())),
                            },
                        }
                    )
                elif t_fade_end <= now < t_start_bell:
                    events.append(
                        {
                            "key": "preview.pcAudio.pcPhaseSilence",
                            "params": {"tStartBell": t_start_bell.strftime("%H:%M:%S")},
                        }
                    )
                elif t_start_bell <= now < T:
                    events.append(
                        {
                            "key": "preview.pcAudio.pcPhaseStartLesson",
                            "params": {
                                "T": T.strftime("%H:%M:%S"),
                                "remainSec": max(0, int((T - now).total_seconds())),
                            },
                        }
                    )
                events.append(
                    {
                        "key": "preview.pcAudio.breakSpan",
                        "params": {"b": B.strftime("%H:%M"), "t": T.strftime("%H:%M")},
                    }
                )
            else:
                events.append({"key": "preview.pcAudio.breakTooShort", "params": {}})
        else:
            events.append({"key": "preview.pcAudio.breakNoGap", "params": {}})
    elif not orch and audio.get("use_bell_schedule") and audio.get("use_bell_sound_files"):
        for row in rows:
            idx = row.get("index")
            st_m = gs.time_to_minutes(str(row.get("start") or "00:00"))
            en_m = gs.time_to_minutes(str(row.get("end") or "00:00"))
            for lab_key, minute, url in (
                ("start", st_m, row.get("sound_start")),
                ("end", en_m, row.get("sound_end")),
            ):
                if not url or not audio.get("enabled"):
                    continue
                if now_m == minute and secs < tw:
                    events.append(
                        {"key": "preview.pcAudio.pcBellPlay", "params": {"idx": idx, "bellKind": lab_key, "tw": tw}}
                    )

    last_b = (st.get("last") or {}).get("backend") if isinstance(st.get("last"), dict) else None
    events.append(
        {
            "key": "preview.pcAudio.process",
            "params": {
                "running": st.get("ffmpeg_process_running"),
                "backend": last_b or "?",
                "playKind": st.get("play_kind"),
                "pid": st.get("pid"),
            },
        }
    )
    last = st.get("last")
    if isinstance(last, dict) and last.get("finished"):
        events.append(
            {
                "key": "preview.pcAudio.lastSession",
                "params": {
                    "ok": last.get("ok"),
                    "code": last.get("returncode"),
                    "stderr": str(last.get("stderr") or "")[:120],
                },
            }
        )

    return {
        "lines": [],
        "events": events,
        "orch_mode": orch,
        "tv_window_sec": tw,
        "bell_status_state": state,
    }


def play_test_file(path: Path, audio: dict[str, Any]) -> tuple[bool, str]:
    try:
        v = int(audio.get("volume_percent") or 80)
        v = max(0, min(100, v))
    except (TypeError, ValueError):
        v = 80
    return play_file_async(path, v, audio, kind="test", max_seconds=600)


def play_break_music_preview(path: Path, audio: dict[str, Any]) -> tuple[bool, str]:
    """Предпрослушивание файла из break_music с громкостью «на перемене» (ffmpeg volume=…)."""
    try:
        v = int(audio.get("break_music_volume_percent") or 40)
        v = max(0, min(100, v))
    except (TypeError, ValueError):
        v = 40
    return play_file_async(path, v, audio, kind="break_preview", max_seconds=600)
