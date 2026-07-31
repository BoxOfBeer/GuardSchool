"""Remove extracted blocks from app.py."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "guardschool" / "app.py"
lines = APP.read_text(encoding="utf-8").splitlines(keepends=True)

for s, e in [
    (3232, 3232),
    (3175, 3232),
    (3150, 3150),
    (2996, 3150),
    (2797, 2797),
    (2775, 2797),
    (1468, 1468),
    (1206, 1468),
    (1175, 1203),
    (1095, 1106),
    (930, 955),
    (794, 904),
    (581, 791),
    (330, 578),
]:
    pass

delete_ranges = [
    (3175, 3232),
    (2996, 3150),
    (2775, 2797),
    (1206, 1468),
    (1175, 1203),
    (1095, 1106),
    (930, 955),
    (794, 904),
    (581, 791),
    (330, 578),
]

for start, end in sorted(delete_ranges, reverse=True):
    del lines[start - 1 : end]

text = "".join(lines)

imp = """from .gs_app_config import (
    apply_emergency_template_to_screen,
    default_config,
    default_screen,
    load_config,
    sanitize_config,
)
from .routes_auth import register_auth_routes
from .routes_public import register_public_routes
"""

if "from .gs_app_config import" not in text:
    anchor = "from .routes_screen import register_screen_routes\n"
    text = text.replace(anchor, anchor + imp)

reg = """register_public_routes(app)
register_auth_routes(app)
"""
if "register_auth_routes(app)" not in text:
    text = text.replace("register_screen_routes(app)\n", "register_screen_routes(app)\n" + reg)

APP.write_text(text, encoding="utf-8")
print("patched app.py lines", text.count("\n"))
