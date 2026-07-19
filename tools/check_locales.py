"""Проверка паритета ru/en локалей и опционально — школьной терминологии в значениях."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ROOT / "static" / "locales"
TV_LOCALES_JS = ROOT / "static" / "tv-locales.js"

# User-facing: предупреждение, не ошибка (внутренние id ключей bells.* допустимы).
RU_WARN = re.compile(r"(?<![\w-])школ|урок|звонк|учебн", re.I)
EN_WARN = re.compile(r"\bschool\b|\blesson\b|\bbell\b", re.I)
SKIP_KEY_SUBSTR = ("widget.type.bell", "section.bells", "bells.", "lesson.")

# tv-locales.js camelCase → static/locales tv.* keys
TV_JS_TO_LOCALE_KEY: dict[str, str] = {
    "noData": "tv.noData",
    "lessonColumn": "tv.lessonColumn",
    "bells": "tv.bells",
    "countdown": "tv.countdown",
    "events": "tv.events",
    "announcements": "tv.announcements",
    "schoolNews": "tv.schoolNews",
    "rssNews": "tv.rssNews",
    "noAnnouncements": "tv.noAnnouncements",
    "noSchoolNews": "tv.noSchoolNews",
    "qr": "tv.qr",
    "noRssNews": "tv.noRssNews",
    "scheduleDefault": "tv.scheduleDefault",
    "nextSchoolDay": "tv.nextSchoolDay",
    "carouselBlank": "tv.carouselBlank",
    "imageEmpty": "tv.imageEmpty",
    "imageAlt": "tv.imageAlt",
    "carouselNoSlides": "tv.carouselNoSlides",
    "emergencyTimeLeft": "tv.emergencyTimeLeft",
    "widgetMissing": "tv.widgetMissing",
    "widgetError": "tv.widgetError",
}


def load(name: str) -> dict[str, str]:
    return json.loads((LOCALES / name).read_text(encoding="utf-8"))


def _parse_tv_locales_js() -> dict[str, dict[str, str]]:
    text = TV_LOCALES_JS.read_text(encoding="utf-8")
    out: dict[str, dict[str, str]] = {"ru": {}, "en": {}}
    lang: str | None = None
    for line in text.splitlines():
        lm = re.match(r"\s*(ru|en):\s*\{", line)
        if lm:
            lang = lm.group(1)
            continue
        if lang and re.match(r"\s*\},?\s*$", line):
            lang = None
            continue
        km = re.match(r'\s*(\w+):\s*"((?:[^"\\]|\\.)*)",?\s*$', line)
        if lang and km:
            out[lang][km.group(1)] = km.group(2).replace('\\"', '"')
    if not out["ru"] or not out["en"]:
        raise RuntimeError("tv-locales.js: could not parse ru/en blocks")
    return out


def check_tv_locales_parity(ru: dict[str, str], en: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if not TV_LOCALES_JS.is_file():
        return ["missing static/tv-locales.js"]
    tv = _parse_tv_locales_js()
    for js_key, loc_key in TV_JS_TO_LOCALE_KEY.items():
        for lang, loc in (("ru", ru), ("en", en)):
            js_val = tv.get(lang, {}).get(js_key)
            json_val = loc.get(loc_key)
            if js_val is None:
                errors.append(f"tv-locales.js [{lang}] missing key {js_key}")
                continue
            if json_val is None:
                errors.append(f"{lang}.json missing {loc_key} (tv-locales {js_key})")
                continue
            if js_val != json_val:
                errors.append(
                    f"tv mismatch [{lang}] {js_key}/{loc_key}: js={js_val!r} json={json_val!r}"
                )
    return errors


def scan_values_for_terms(data: dict[str, str], pat: re.Pattern[str], *, skip_keys: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for k, v in data.items():
        if any(s in k for s in skip_keys):
            continue
        if pat.search(str(v)):
            hits.append(k)
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Check ru/en locale key parity")
    parser.add_argument("--warn-terms", action="store_true", help="Warn about school-like terms in values")
    parser.add_argument("--check-tv", action="store_true", help="Verify static/tv-locales.js matches tv.* in JSON")
    args = parser.parse_args()

    ru = load("ru.json")
    en = load("en.json")
    ru_only = sorted(set(ru) - set(en))
    en_only = sorted(set(en) - set(ru))
    if ru_only or en_only:
        print(f"KEY MISMATCH: ru-only={len(ru_only)} en-only={len(en_only)}", file=sys.stderr)
        for k in ru_only[:20]:
            print(f"  ru only: {k}", file=sys.stderr)
        for k in en_only[:20]:
            print(f"  en only: {k}", file=sys.stderr)
        return 1

    print(f"OK: {len(ru)} keys in sync (ru.json + en.json)")

    if args.check_tv or args.warn_terms:
        tv_errors = check_tv_locales_parity(ru, en)
        if tv_errors:
            print(f"TV LOCALES FAILED ({len(tv_errors)}):", file=sys.stderr)
            for msg in tv_errors:
                print(f"  - {msg}", file=sys.stderr)
            return 1
        if args.check_tv:
            print(f"OK: tv-locales.js in sync ({len(TV_JS_TO_LOCALE_KEY)} keys)")

    if args.warn_terms:
        tv = _parse_tv_locales_js()
        for name, data, pat in (("ru", ru, RU_WARN), ("en", en, EN_WARN)):
            hits = scan_values_for_terms(data, pat, skip_keys=SKIP_KEY_SUBSTR)
            if hits:
                print(f"WARN [{name}]: {len(hits)} values may contain legacy terms")
                for k in hits[:25]:
                    print(f"  {k}: {data[k][:72]}...")
            else:
                print(f"WARN [{name}]: no legacy terms in scanned values")
        for lang, pat in (("ru", RU_WARN), ("en", EN_WARN)):
            flat = {f"tv.{k}": v for k, v in tv.get(lang, {}).items()}
            hits = scan_values_for_terms(flat, pat, skip_keys=SKIP_KEY_SUBSTR)
            if hits:
                print(f"WARN [tv-{lang}]: {len(hits)} values may contain legacy terms")
                for k in hits[:10]:
                    print(f"  {k}: {flat[k][:72]}...")
            else:
                print(f"WARN [tv-{lang}]: no legacy terms in scanned values")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
