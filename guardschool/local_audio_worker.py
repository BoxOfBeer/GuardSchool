"""Локальное воспроизведение: звонки по расписанию и фон из data/break_music (ffplay)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .local_audio_ffmpeg import ffmpeg_has_wasapi_output_muxer
from .local_audio_orchestration import (
    describe_pc_audio_preview,
    get_break_music_playback_info,
    tick_once,
)
from .local_audio_playback import (
    get_last_playback,
    get_status,
    play_file_async,
    stop_playback,
    stop_playback_hard,
)

__all__ = [
    "describe_pc_audio_preview",
    "ffmpeg_has_wasapi_output_muxer",
    "get_break_music_playback_info",
    "get_last_playback",
    "get_status",
    "play_break_music_preview",
    "play_file_async",
    "play_test_file",
    "stop_playback",
    "stop_playback_hard",
    "tick_once",
]


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
