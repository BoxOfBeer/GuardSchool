"""Локальное воспроизведение: ffplay/ffmpeg, stop/status."""
from __future__ import annotations

import logging
import os
import shlex
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("guard_school.local_audio")

from .gs_app_config import load_config, sanitize_audio_stream
from .local_audio_ffmpeg import (
    _creationflags,
    _resolve_ffmpeg,
    _resolve_ffplay,
    ffmpeg_has_wasapi_output_muxer,
)

# После terminate ffplay поток runner ещё освобождает семафор — без паузы новый звонок часто ловит «занято».
AFTER_STOP_GRACE_SEC = 0.1

_play_sem = threading.Semaphore(1)
_active_proc: subprocess.Popen | None = None
_proc_guard = threading.Lock()
_play_kind: str = "idle"  # idle | bell | break | test | break_orch_*

_last_playback: dict[str, Any] | None = None
_ffplay_missing_logged = False

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
        cfg = load_config()
        audio = sanitize_audio_stream(cfg.get("audio_stream"))
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
