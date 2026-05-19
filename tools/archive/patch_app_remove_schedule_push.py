"""Remove extracted schedule/push blocks from app.py; wire imports."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "guardschool" / "app.py"
lines = APP.read_text(encoding="utf-8").splitlines(keepends=True)

delete_ranges = [
    (2093, 2434),
    (1804, 1804),  # blank before _log - keep _log at 1805
    (988, 1802),
    (978, 986),
    (968, 976),  # load_rss only - keep load_marquee removed in 978-986
    (721, 744),
    (537, 576),
    (509, 527),
]

# Fix: 968-976 is load_rss, 978-982 marquee, 984-986 overrides - delete 968-986 together
delete_ranges = [
    (2093, 2434),
    (988, 1802),
    (968, 986),
    (721, 744),
    (537, 576),
    (509, 527),
]

for start, end in sorted(delete_ranges, reverse=True):
    del lines[start - 1 : end]

text = "".join(lines)

imp = '''from .gs_data_loaders import (
    load_announcements,
    load_full_schedule,
    load_holidays,
    load_marquee_items,
    load_overrides,
    load_rss_news,
    load_schedule,
    load_schedule_sample,
)
from .gs_schedule_bells import (
    build_bell_audio_payload,
    build_bell_status,
    build_schedule_payload,
    calendar_today_for_config,
    collect_enriched_schedule_rows,
    compute_max_lesson_index_for_screen_day,
    display_settings_dict,
    wall_clock_minutes_for_config,
)
from .gs_screen_push import (
    maybe_push_screen_content_if_data_revision_changed,
    notify_push_emergency_change,
    notify_push_checkin_journal_bulk_confirm,
    notify_push_checkin_journal_confirmed,
    notify_push_checkin_journal_new_row,
)

# Back-compat aliases (underscore) for modules still importing from app
_maybe_push_screen_content_if_data_revision_changed = maybe_push_screen_content_if_data_revision_changed
_notify_push_emergency_change = notify_push_emergency_change
_notify_push_checkin_journal_new_row = notify_push_checkin_journal_new_row
_notify_push_checkin_journal_confirmed = notify_push_checkin_journal_confirmed
_notify_push_checkin_journal_bulk_confirm = notify_push_checkin_journal_bulk_confirm

'''

if "from .gs_schedule_bells import" not in text:
    anchor = "from .gs_app_config import (\n"
    text = text.replace(anchor, imp + anchor)

APP.write_text(text, encoding="utf-8")
print("patched lines", text.count("\n"))
