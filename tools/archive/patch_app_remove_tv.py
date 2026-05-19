"""Remove TV routes/helpers from app.py after extraction."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app_path = ROOT / "guardschool" / "app.py"
lines = app_path.read_text(encoding="utf-8").splitlines(keepends=True)

delete_ranges = [
    (5382, 5382),  # trailing blank before screen-watch if needed - check
    (4993, 5382),  # tv routes + gate (4969-4986 included in 4993 start? gate is 4969-4986)
    (4969, 5382),
    (4614, 4622),
    (2885, 2921),
    (1112, 1161),
    (297, 330),
]

# merge overlapping - use single sorted reverse delete
delete_ranges = [
    (4969, 5382),
    (4614, 4622),
    (2885, 2921),
    (1112, 1161),
    (297, 330),
]

for start, end in delete_ranges:
    del lines[start - 1 : end]

text = "".join(lines)

imports_add = """from .app_screen_html import render_screen_html_page
from .gs_tv_pair import tv_code_plaintext_for_tenant, tv_token_active_tenant
"""

if "from .app_screen_html import render_screen_html_page" not in text:
    anchor = "from .app_portal_web import register_portal_web_routes\n"
    text = text.replace(anchor, anchor + imports_add)

# screen_page uses _render_screen_html_page and _tv_token
text = text.replace("_render_screen_html_page(", "render_screen_html_page(")
text = text.replace("_tv_token_active_tenant(", "tv_token_active_tenant(")
text = text.replace("_tv_code_plaintext_for_tenant(", "tv_code_plaintext_for_tenant(")

app_path.write_text(text, encoding="utf-8")
print("Patched", app_path, "lines", text.count("\n"))
