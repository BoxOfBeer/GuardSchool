"""Remove admin routes from app.py after extraction to routes_admin.py."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app_path = ROOT / "guardschool" / "app.py"
lines = app_path.read_text(encoding="utf-8").splitlines(keepends=True)

delete_ranges = [
    (4842, 4852),
    (4198, 4455),
    (3788, 3969),
    (3149, 3705),
]

for start, end in delete_ranges:
    del lines[start - 1 : end]

text = "".join(lines)

if "register_admin_routes" not in text:
    anchor = "register_portal_web_routes(app)\n"
    text = text.replace(
        anchor,
        anchor + "from .routes_admin import register_admin_routes\nregister_admin_routes(app)\n",
    )

app_path.write_text(text, encoding="utf-8")
print("Patched", app_path, "lines", text.count("\n"))
