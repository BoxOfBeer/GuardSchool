"""Remove screen API routes from app.py."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app_path = ROOT / "guardschool" / "app.py"
lines = app_path.read_text(encoding="utf-8").splitlines(keepends=True)

delete_ranges = [
    (3461, 3496),  # orphan admin checkin events-status
    (3235, 3458),  # screen routes
]

for start, end in delete_ranges:
    del lines[start - 1 : end]

text = "".join(lines)

if "register_screen_routes" not in text:
    anchor = "register_admin_routes(app)\n"
    text = text.replace(
        anchor,
        anchor + "from .routes_screen import register_screen_routes\nregister_screen_routes(app)\n",
    )

app_path.write_text(text, encoding="utf-8")
print("Patched", app_path, "lines", text.count("\n"))
