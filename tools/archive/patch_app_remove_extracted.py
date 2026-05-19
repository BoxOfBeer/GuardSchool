"""Remove PWA + portal blocks from app.py after extraction."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app_path = ROOT / "guardschool" / "app.py"
lines = app_path.read_text(encoding="utf-8").splitlines(keepends=True)

# Ranges to delete (1-based inclusive), reverse order
delete_ranges = [
    (6023, 6040),
    (5255, 6020),
    (3174, 3290),
    (3090, 3093),
    (3005, 3027),
    (2873, 3002),
    (2869, 2870),
]

for start, end in delete_ranges:
    del lines[start - 1 : end]

text = "".join(lines)

# Add imports after app_saas_portal import if missing
imports_add = """from .app_pwa_manifest import (
    apply_saas_screen_tenant_from_request as _apply_saas_screen_tenant_from_request,
    register_pwa_manifest_routes,
    screen_html_manifest_link as _pwa_screen_html_manifest_link,
    tv_access_lookup_row as _tv_access_lookup_row,
    tv_pair_html_manifest_link as _pwa_tv_pair_html_manifest_link,
)
from .app_portal_web import register_portal_web_routes
"""

if "register_pwa_manifest_routes" not in text:
    anchor = "from .app_saas_portal import register_saas_portal_routes\n"
    if anchor not in text:
        raise SystemExit("anchor import not found")
    text = text.replace(anchor, anchor + imports_add)

register_add = """register_pwa_manifest_routes(app)
register_portal_web_routes(app)
"""
if "register_pwa_manifest_routes(app)" not in text:
    anchor = "register_saas_portal_routes(app)\n"
    if anchor not in text:
        raise SystemExit("register anchor not found")
    text = text.replace(anchor, anchor + register_add)

app_path.write_text(text, encoding="utf-8")
print("Patched", app_path, "lines", text.count("\n"))
