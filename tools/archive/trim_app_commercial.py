"""Удалить commercial/provider handlers из app.py (остаются в routes_commercial)."""
from __future__ import annotations

from pathlib import Path

p = Path(__file__).resolve().parent.parent / "guardschool" / "app.py"
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
start = next(i for i, l in enumerate(lines) if l.startswith("def _license_ts_utc"))
end = next(i for i, l in enumerate(lines) if l.strip() == '@app.get("/api/portal/cms")')
lines = lines[:start] + lines[end:]
out: list[str] = []
skip = False
for l in lines:
    if '@app.get("/api/provider/portal-cms")' in l:
        skip = True
    elif skip and '@app.get("/demo/' in l:
        skip = False
    if not skip:
        out.append(l)
text = "".join(out)
marker = '@app.post("/api/saas/register")'
if marker in text:
    i = text.index(marker)
    j = text.index('@app.post("/api/setup")', i)
    text = text[:i] + text[j:]
p.write_text(text, encoding="utf-8", newline="\n")
print(f"trimmed -> {len(text)} bytes")
