#!/usr/bin/env python3
"""Прогон тестового push — подписки с 410 Gone удаляются из push.sqlite3."""
from __future__ import annotations

import json
import os
import sys

env_file = "/etc/guardschool/environment"
if os.path.isfile(env_file):
    for line in open(env_file, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, "/opt/guardschool")

from guardschool.tenant_ctx import set_tenant_slug  # noqa: E402

from guardschool.gs_push import (  # noqa: E402
    delete_subscription,
    list_subscriptions,
    vapid_private_key_for_webpush,
    vapid_subject,
    webpush_subscription_stale,
)
from pywebpush import webpush  # noqa: E402

tenant = (sys.argv[1] if len(sys.argv) > 1 else "s970eb024b17d").strip()
set_tenant_slug(tenant)
screens = [s.strip().lower() for s in (sys.argv[2:] if len(sys.argv) > 2 else ["tv-1", "tv-2"])]
payload = json.dumps(
    {"title": "prune", "body": "stale cleanup", "url": "/", "tag": "prune"},
    ensure_ascii=False,
)
removed = 0
sent = 0
for slug in screens:
    subs = list_subscriptions(tenant_id=tenant, screen_slug=slug, topic=None)
    print(f"{slug}: {len(subs)} subscription(s)")
    for s in subs:
        ep = str(s.get("endpoint") or "").strip()
        try:
            webpush(
                subscription_info={"endpoint": ep, "keys": s["keys"]},
                data=payload,
                vapid_private_key=vapid_private_key_for_webpush(),
                vapid_claims={"sub": vapid_subject()},
            )
            sent += 1
        except Exception as exc:
            if webpush_subscription_stale(exc) and ep:
                n = delete_subscription(tenant_id=tenant, screen_slug=slug, endpoint=ep)
                removed += n
                print("  removed stale:", ep[:56], "...")
            else:
                print("  fail:", ep[:56], "...", exc)
print("done: sent", sent, "removed", removed)
