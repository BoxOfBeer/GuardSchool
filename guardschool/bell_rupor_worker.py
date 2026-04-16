"""
Планировщик звука на ПК. Раньше здесь был UDP-стрим (ffmpeg → сеть) — отключён,
код удалён из активной поставки; при необходимости смотрите историю git.

Сейчас: делегирование в local_audio_worker (ffplay: звонки + плейлист перемен).
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from . import local_audio_worker

log = logging.getLogger("guard_school.bell_schedule")

_stop = threading.Event()
_worker_thread: threading.Thread | None = None


def stream_file_to_rupor(
    path: Path,
    audio: dict[str, Any],
    *,
    max_seconds: int = 600,
) -> tuple[bool, str]:
    """Совместимость API: UDP отключён — тест из админки идёт через локальный ffplay."""
    _ = max_seconds
    local_audio_worker.stop_playback_hard()
    time.sleep(0.1)
    return local_audio_worker.play_test_file(path, audio)


def get_last_ffmpeg_send() -> dict[str, Any] | None:
    return local_audio_worker.get_last_playback()


def get_ffmpeg_status() -> dict[str, Any]:
    return local_audio_worker.get_status()


def stop_current_stream() -> dict[str, Any]:
    return local_audio_worker.stop_playback()


def _loop() -> None:
    while not _stop.wait(0.25):
        try:
            local_audio_worker.tick_once()
        except Exception:
            log.exception("Планировщик звука: сбой тика.")


def start_worker() -> None:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop.clear()
    _worker_thread = threading.Thread(target=_loop, name="local-audio-bells", daemon=True)
    _worker_thread.start()


def stop_worker() -> None:
    _stop.set()
    local_audio_worker.stop_playback_hard()
    t = _worker_thread
    if t and t.is_alive():
        t.join(timeout=2.5)
