"""FFmpeg/ffplay/ffprobe: поиск бинарников, WASAPI, длительность медиа."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("guard_school.local_audio")

_ffmpeg_wasapi_muxer_cache: dict[str, bool] = {}

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
