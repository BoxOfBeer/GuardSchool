"""Point local_audio_worker at domain modules instead of guardschool.app."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "guardschool" / "local_audio_worker.py"
text = path.read_text(encoding="utf-8")

imports = '''from .gs_app_config import DEFAULT_BELL_TRIGGER_SEC_WINDOW, load_config, sanitize_audio_stream
from .gs_paths import BREAK_MUSIC_DIR
from .gs_schedule_bells import (
    BREAK_ORCH_FADE_SEC,
    BREAK_ORCH_HEAD_SEC,
    BREAK_ORCH_SILENCE_SEC,
    BREAK_ORCH_START_BELL_SEC,
    MORNING_PRE_FIRST_LESSON_MIN,
    PRE_BELL_AFADE_IN_SEC,
    PRE_BELL_FIRE_SEC_WINDOW,
    PRE_BELL_LEAD_MINUTES,
    PRE_BELL_MAX_DURATION_SEC,
    audio_trigger_sec_window,
    bell_audio_url_to_path,
    build_bell_audio_payload,
    build_bell_status,
    entry_academic_num,
    time_to_minutes,
)

'''

marker = "log = logging.getLogger(\"guard_school.local_audio\")"
if imports.strip() not in text:
    text = text.replace(marker, marker + "\n\n" + imports)

# Remove lazy app loader
for block in (
    "\n_app_module: Any = None\n",
    "\ndef _app() -> Any:\n    global _app_module\n    if _app_module is None:\n        from . import app\n\n        _app_module = app\n    return _app_module\n",
):
    text = text.replace(block, "\n")

replacements = [
    ("gs.time_to_minutes", "time_to_minutes"),
    ("gs.bell_audio_url_to_path", "bell_audio_url_to_path"),
    ("gs.build_bell_audio_payload", "build_bell_audio_payload"),
    ("gs.build_bell_status", "build_bell_status"),
    ("gs.load_config", "load_config"),
    ("gs.sanitize_audio_stream", "sanitize_audio_stream"),
    ("gs.audio_trigger_sec_window", "audio_trigger_sec_window"),
    ("gs.DEFAULT_BELL_TRIGGER_SEC_WINDOW", "DEFAULT_BELL_TRIGGER_SEC_WINDOW"),
    ("gs.BREAK_ORCH_HEAD_SEC", "BREAK_ORCH_HEAD_SEC"),
    ("gs.BREAK_ORCH_FADE_SEC", "BREAK_ORCH_FADE_SEC"),
    ("gs.BREAK_ORCH_SILENCE_SEC", "BREAK_ORCH_SILENCE_SEC"),
    ("gs.BREAK_ORCH_START_BELL_SEC", "BREAK_ORCH_START_BELL_SEC"),
    ("gs.PRE_BELL_LEAD_MINUTES", "PRE_BELL_LEAD_MINUTES"),
    ("gs.PRE_BELL_FIRE_SEC_WINDOW", "PRE_BELL_FIRE_SEC_WINDOW"),
    ("gs.PRE_BELL_MAX_DURATION_SEC", "PRE_BELL_MAX_DURATION_SEC"),
    ("gs.PRE_BELL_AFADE_IN_SEC", "PRE_BELL_AFADE_IN_SEC"),
    ("gs.BREAK_MUSIC_DIR", "BREAK_MUSIC_DIR"),
    ('int(getattr(gs, "MORNING_PRE_FIRST_LESSON_MIN", 30))', "int(MORNING_PRE_FIRST_LESSON_MIN)"),
]
for old, new in replacements:
    text = text.replace(old, new)

text = text.replace("def _find_break_gap(\n    gs: Any,\n    entries:", "def _find_break_gap(\n    entries:")
text = text.replace("def _allocate_break_tail(total_sec: float, gs: Any)", "def _allocate_break_tail(total_sec: float)")
text = text.replace(
    "def _tick_break_orchestration(\n    gs: Any,\n    screen:",
    "def _tick_break_orchestration(\n    screen:",
)
text = text.replace("def _list_break_tracks(gs: Any)", "def _list_break_tracks()")
text = text.replace("_find_break_gap(gs, entries", "_find_break_gap(entries")
text = text.replace("_allocate_break_tail(total_sec, gs)", "_allocate_break_tail(total_sec)")
text = text.replace("_list_break_tracks(gs)", "_list_break_tracks()")
text = text.replace("    gs = _app()\n", "")
text = text.replace("    app = _app()\n", "")
text = text.replace("                nn = app.entry_academic_num(entries[i + 1])", "                nn = entry_academic_num(entries[i + 1])")
text = text.replace(
    "_tick_break_orchestration(\n                gs,",
    "_tick_break_orchestration(",
)

path.write_text(text, encoding="utf-8")
print("local_audio_worker.py updated")
