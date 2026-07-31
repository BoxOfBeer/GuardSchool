"""CI: паритет Python widget registry ↔ static/widgets/*.js ↔ plugins-manifest.js."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIDGETS_JS_DIR = ROOT / "static" / "widgets"
MANIFEST_PATH = WIDGETS_JS_DIR / "plugins-manifest.js"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

IGNORE_JS = frozenset({"runtime.js", "plugins-manifest.js", "carousel-runtime.js"})
JS_ONLY_RENDERERS = frozenset({"blank"})
RENDER_SPECIAL: dict[str, str] = {"carousel": "carousel-runtime.js"}


def parse_manifest_js_files() -> list[str]:
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    return re.findall(r'"([a-z_0-9]+\.js)"', text)


def collect_python_render_keys() -> dict[str, str]:
    import os

    os.environ.setdefault("GUARDSCHOOL_DEPLOYMENT_MODE", "local")
    from guardschool.capabilities import reset_capabilities_for_tests
    from guardschool.widget_loader import load_all_widgets, reset_widget_loader_for_tests
    from guardschool.widget_registry import get_widget, loaded_widget_types, reset_widget_registry_for_tests

    reset_capabilities_for_tests()
    reset_widget_registry_for_tests()
    reset_widget_loader_for_tests()
    load_all_widgets()

    out: dict[str, str] = {}
    for wtype in loaded_widget_types():
        m = get_widget(wtype)
        if m is None:
            continue
        rk = (m.render_key or m.type or wtype).strip()
        out[wtype] = rk
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Check widget Python/JS/manifest parity")
    parser.parse_args()

    errors: list[str] = []

    if not MANIFEST_PATH.is_file():
        errors.append(f"missing {MANIFEST_PATH.relative_to(ROOT)}")
        for msg in errors:
            print(msg, file=sys.stderr)
        return 1

    manifest_files = parse_manifest_js_files()
    manifest_set = set(manifest_files)
    js_files = sorted(p.name for p in WIDGETS_JS_DIR.glob("*.js") if p.name not in IGNORE_JS)

    for name in manifest_files:
        path = WIDGETS_JS_DIR / name
        if not path.is_file():
            errors.append(f"plugins-manifest lists missing file: static/widgets/{name}")

    for name in js_files:
        if name not in manifest_set and name not in RENDER_SPECIAL.values():
            errors.append(f"static/widgets/{name} not listed in plugins-manifest.js")

    py_render_keys = collect_python_render_keys()
    unique_render_keys = sorted(set(py_render_keys.values()))

    for rk in unique_render_keys:
        if rk in JS_ONLY_RENDERERS:
            continue
        special = RENDER_SPECIAL.get(rk)
        if special:
            special_path = WIDGETS_JS_DIR / special
            if not special_path.is_file():
                errors.append(f"render_key {rk!r}: missing static/widgets/{special}")
            continue
        js_name = f"{rk}.js"
        js_path = WIDGETS_JS_DIR / js_name
        if not js_path.is_file():
            errors.append(f"render_key {rk!r}: missing static/widgets/{js_name}")
        elif js_name not in manifest_set:
            errors.append(f"render_key {rk!r}: {js_name} not in plugins-manifest.js")

    for name in JS_ONLY_RENDERERS:
        js_path = WIDGETS_JS_DIR / f"{name}.js"
        if not js_path.is_file():
            errors.append(f"JS-only renderer {name!r}: missing static/widgets/{name}.js")
        elif f"{name}.js" not in manifest_set:
            errors.append(f"JS-only renderer {name!r}: {name}.js not in plugins-manifest.js")

    if errors:
        print(f"WIDGET PARITY FAILED ({len(errors)} issue(s)):", file=sys.stderr)
        for msg in errors:
            print(f"  - {msg}", file=sys.stderr)
        return 1

    print(
        f"OK: {len(py_render_keys)} Python types, "
        f"{len(unique_render_keys)} render keys, "
        f"{len(manifest_files)} manifest entries, "
        f"{len(js_files)} widget JS files"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
