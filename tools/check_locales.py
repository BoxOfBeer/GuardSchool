"""Проверка паритета ru/en локалей и опционально — школьной терминологии в значениях."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ROOT / "static" / "locales"

# User-facing: предупреждение, не ошибка (внутренние id ключей bells.* допустимы).
RU_WARN = re.compile(r"(?<![\w-])школ|урок|звонк|учебн", re.I)
EN_WARN = re.compile(r"\bschool\b|\blesson\b|\bbell\b", re.I)
SKIP_KEY_SUBSTR = ("widget.type.bell", "section.bells", "bells.", "lesson.")


def load(name: str) -> dict[str, str]:
    return json.loads((LOCALES / name).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check ru/en locale key parity")
    parser.add_argument("--warn-terms", action="store_true", help="Warn about school-like terms in values")
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

    if args.warn_terms:
        for name, data, pat in (("ru", ru, RU_WARN), ("en", en, EN_WARN)):
            hits = []
            for k, v in data.items():
                if any(s in k for s in SKIP_KEY_SUBSTR):
                    continue
                if pat.search(str(v)):
                    hits.append(k)
            if hits:
                print(f"WARN [{name}]: {len(hits)} values may contain legacy terms")
                for k in hits[:25]:
                    print(f"  {k}: {data[k][:72]}...")
            else:
                print(f"WARN [{name}]: no legacy terms in scanned values")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
