#!/usr/bin/env python3
"""Аудит JSON данных школы: tv-1, звонки на сегодня, строки расписания.
Запуск на сервере: python3 scripts/audit_tv_schedule_data.py [--root /opt/guardschool/tenants] [--slug burevestnik]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def schedule_date_iso(raw: object) -> str:
    if raw is None:
        return ""
    if isinstance(raw, datetime):
        return raw.date().isoformat()
    if isinstance(raw, date):
        return raw.isoformat()
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        try:
            n = int(raw)
        except (TypeError, ValueError):
            n = 0
        if 29500 < n < 65000:
            try:
                return (date(1899, 12, 30) + timedelta(days=n)).isoformat()
            except (OverflowError, ValueError):
                return ""
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    if "T" in s:
        s = s.split("T", 1)[0].strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        head = s[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", head):
            return head
    if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", s):
        try:
            return datetime.strptime(s, "%d.%m.%Y").date().isoformat()
        except ValueError:
            return ""
    return ""


def today_for_tz(tzname: str) -> date:
    tzname = (tzname or "Europe/Moscow").strip() or "Europe/Moscow"
    try:
        from zoneinfo import ZoneInfo

        try:
            z = ZoneInfo(tzname)
        except Exception:
            z = ZoneInfo("Europe/Moscow")
        return datetime.now(z).date()
    except Exception:
        return datetime.now(timezone.utc).date()


def bell_entries_for_screen(
    screen: dict, bells: dict, target_date: date
) -> tuple[list, str]:
    iso_date = target_date.isoformat()
    weekday = str(target_date.weekday())
    template_id = screen.get("bell_schedule_template") or "standard"
    for item in bells.get("date_overrides", []) or []:
        if item.get("date") == iso_date:
            return list(item.get("entries", []) or []), "date_override"
    wmap = screen.get("weekday_bell_templates") or {}
    wglob = bells.get("weekday_overrides") or {}
    oid = wmap.get(weekday) or wglob.get(weekday)
    if oid:
        template_id = oid
    for t in bells.get("templates", []) or []:
        if t.get("id") == template_id:
            return list(t.get("entries", []) or []), str(t.get("name") or template_id)
    return [], f"(no template id={template_id!r})"


def audit_data_dir(data: Path, slug: str, screen_slug: str) -> None:
    print(f"\n### tenant slug={slug!r}  data={data}")
    cfgp = data / "config.json"
    if not cfgp.is_file():
        print("  (no config.json)")
        return
    cfg = json.loads(cfgp.read_text(encoding="utf-8"))
    tz = str(cfg.get("timezone") or "Europe/Moscow")
    today = today_for_tz(tz)
    wd = today.weekday()
    schp, fullp, bellp = data / "schedule.json", data / "full_schedule.json", data / "bell_schedules.json"
    bells = json.loads(bellp.read_text(encoding="utf-8")) if bellp.is_file() else {}
    sch = json.loads(schp.read_text(encoding="utf-8")) if schp.is_file() else []
    full = json.loads(fullp.read_text(encoding="utf-8")) if fullp.is_file() else []
    if not isinstance(sch, list):
        sch = []
    if not isinstance(full, list):
        full = []
    tiso = today.isoformat()
    dated = [r for r in sch if schedule_date_iso(r.get("date")) == tiso]
    full_wd = []
    for r in full:
        try:
            if int(r.get("weekday", -99)) == wd:
                full_wd.append(r)
        except (TypeError, ValueError):
            continue
    print(f"  timezone={tz!r} -> today={tiso} weekday={wd}")
    print(f"  schedule.json rows total={len(sch)} for_today={len(dated)}")
    print(f"  full_schedule.json rows total={len(full)} for_weekday={wd} count={len(full_wd)}")
    screens = cfg.get("screens") or []
    slugs = [str(s.get("slug") or "") for s in screens]
    print(f"  config screens slugs: {slugs}")
    scr = next((s for s in screens if str(s.get("slug") or "") == screen_slug), None)
    if not scr:
        print(f"  NO screen slug={screen_slug!r}")
        return
    print(
        f"  {screen_slug}: is_active={scr.get('is_active', True)} mobile_mode={scr.get('mobile_mode')} "
        f"bell_template={scr.get('bell_schedule_template')!r}"
    )
    widgets = scr.get("widgets") or []
    enabled_types = [
        w.get("type")
        for w in widgets
        if w.get("enabled", True) is not False and w.get("type")
    ]
    print(f"  {screen_slug} widget types (enabled): {enabled_types}")
    ent, src = bell_entries_for_screen(scr, bells, today)
    print(f"  bell entries for today: count={len(ent)} source={src!r}")
    if ent:
        print(f"  first_entry: {ent[0]!r}  last_entry: {ent[-1]!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--root",
        type=Path,
        default=Path("/opt/guardschool/tenants"),
        help="Каталог tenants (подкаталоги = slug школы)",
    )
    ap.add_argument("--slug", type=str, default="", help="Только один тенант (иначе все)")
    ap.add_argument("--screen", type=str, default="tv-1", help="Slug экрана")
    args = ap.parse_args()
    root: Path = args.root
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 1
    tenants = sorted(root.iterdir())
    if args.slug:
        tenants = [root / args.slug]
    for tenant_dir in tenants:
        if not tenant_dir.is_dir():
            continue
        data = tenant_dir / "data"
        if not data.is_dir():
            continue
        audit_data_dir(data, tenant_dir.name, args.screen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
