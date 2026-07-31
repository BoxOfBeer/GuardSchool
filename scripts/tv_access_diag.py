"""Диагностика tv_access + тот же SQL, что в app.py (запуск на сервере с env)."""
from __future__ import annotations

import os
import re
import sys

# минимум импортов как в app
from guardschool.saas_db import connect_public, tv_code_hash

_TV_ACCESS_BY_CODE_SQL = (
    "SELECT tenant_slug, pin_salt, pin_hash, COALESCE(pin_bypass, false) FROM tv_access "
    "WHERE code_hash=%s "
    "OR lower(trim(coalesce(code_plaintext, '')))=%s "
    "OR regexp_replace(lower(trim(coalesce(code_plaintext, ''))), '[^a-z0-9]', '', 'g')=%s "
    "LIMIT 1"
)


def main() -> int:
    code = (sys.argv[1] if len(sys.argv) > 1 else "g6cp-qnr7-tdk6").strip().lower()
    ch = tv_code_hash(code)
    comp = re.sub(r"[^a-z0-9]", "", code)
    print("code", code, "hash_prefix", ch[:20], "digits_only", comp)
    with connect_public() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tenant_slug, code_plaintext, left(code_hash,20), length(code_plaintext) FROM tv_access")
            rows = cur.fetchall() or []
            print("rows_count", len(rows))
            for r in rows:
                print(" ", repr(r[0]), repr(r[1]), r[2], r[3])
            cur.execute(_TV_ACCESS_BY_CODE_SQL, (ch, code, comp))
            hit = cur.fetchone()
            print("lookup_result", hit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
