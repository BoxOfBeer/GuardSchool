from __future__ import annotations

import os
import tempfile
import time
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from guardschool import _gs_feedback_pg as feedback
from guardschool import _provider_demo_pg as provider_demo
from guardschool import gs_screen_watch as screen_watch
from guardschool import gs_import_bundle as import_bundle
from guardschool.app_hosting import tenant_middleware
from guardschool.gs_auth import create_demo_session_token, require_auth
from guardschool.gs_paths import SAAS_TENANT_COOKIE, SESSION_COOKIE
from guardschool.tenant_ctx import set_tenant_slug, tenant_slug


class FakeRequest:
    def __init__(self, *, host: str = "school.guarddoc.ru", cookies: dict[str, str] | None = None) -> None:
        self.headers = {"host": host}
        self.cookies = cookies or {}
        self.client = SimpleNamespace(host="127.0.0.1")


class DemoTenantIsolationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.tenants = self.root / "tenants"
        self.data.mkdir(parents=True)
        self._env = {
            name: os.environ.get(name)
            for name in (
                "GUARDSCHOOL_DEPLOYMENT_MODE",
                "GUARDSCHOOL_DATA_DIR",
                "GUARDSCHOOL_SAAS_DATA_ROOT",
                "GUARDSCHOOL_PUBLIC_SCHOOL_HOST",
                "GUARDSCHOOL_DEMO_SESSION_SECRET",
            )
        }
        os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = "saas"
        os.environ["GUARDSCHOOL_DATA_DIR"] = str(self.data)
        os.environ["GUARDSCHOOL_SAAS_DATA_ROOT"] = str(self.tenants)
        os.environ["GUARDSCHOOL_PUBLIC_SCHOOL_HOST"] = "school.guarddoc.ru"
        os.environ["GUARDSCHOOL_DEMO_SESSION_SECRET"] = "tenant-isolation-test"
        feedback.FEEDBACK_DB_PATH = self.data / "feedback.sqlite3"
        screen_watch.SCREEN_WATCH_STATS_PATH = self.data / "screen_watch_stats.json"
        screen_watch._CLIENT_ROWS.clear()
        screen_watch._STATS_CACHE.clear()
        screen_watch._STATS_DIRTY.clear()
        screen_watch._STATS_LAST_FLUSH.clear()
        set_tenant_slug(None)

    def tearDown(self) -> None:
        set_tenant_slug(None)
        for name, value in self._env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.temp.cleanup()

    async def test_demo_token_ignores_tampered_tenant_cookie(self) -> None:
        isolated = "demo-template-abc123"
        (self.tenants / isolated / "data").mkdir(parents=True)
        token = create_demo_session_token(int(time.time()) + 300, "template", isolated)
        request = FakeRequest(
            host="template.guarddoc.ru",
            cookies={SESSION_COOKIE: token, SAAS_TENANT_COOKIE: "permanent-school"},
        )

        async def call_next(_request):
            self.assertEqual(tenant_slug(), isolated)
            return "ok"

        self.assertEqual(await tenant_middleware(request, call_next), "ok")
        self.assertIsNone(tenant_slug())

    def test_demo_auth_requires_its_isolated_tenant(self) -> None:
        token = create_demo_session_token(int(time.time()) + 300, "template", "demo-template-abc123")
        request = FakeRequest(cookies={SESSION_COOKIE: token})
        set_tenant_slug("permanent-school")
        with self.assertRaises(HTTPException) as raised:
            require_auth(request)
        self.assertEqual(raised.exception.status_code, 403)

        set_tenant_slug("demo-template-abc123")
        require_auth(request)

    def test_feedback_has_separate_database_per_tenant(self) -> None:
        set_tenant_slug("school-a")
        feedback.ensure_feedback_tables()
        feedback.create_feedback_message("school-a", "same-device", "A only")
        feedback.block_feedback_hash("blocked-in-a")
        self.assertEqual([x["message"] for x in feedback.list_feedback_messages()], ["A only"])

        set_tenant_slug("school-b")
        feedback.ensure_feedback_tables()
        self.assertEqual(feedback.list_feedback_messages(), [])
        self.assertFalse(feedback.is_feedback_blocked("blocked-in-a"))
        self.assertTrue(feedback.can_send_feedback("same-device"))
        feedback.create_feedback_message("school-b", "same-device", "B only")

        set_tenant_slug("school-a")
        self.assertEqual([x["message"] for x in feedback.list_feedback_messages()], ["A only"])

    def test_live_screen_state_and_statistics_are_tenant_scoped(self) -> None:
        request = FakeRequest()
        screen = [{"id": 1, "slug": "main", "name": "Main", "poll_interval_sec": 10}]

        set_tenant_slug("school-a")
        screen_watch.record_screen_poll(request, "main", "client-0001", "A", "Windows")
        snap_a = screen_watch.screen_watch_snapshot(screen)

        set_tenant_slug("school-b")
        screen_watch.record_screen_poll(request, "main", "client-0001", "B", "Android")
        snap_b = screen_watch.screen_watch_snapshot(screen)

        self.assertEqual([x["label"] for x in snap_a["screens"][0]["clients"]], ["A"])
        self.assertEqual([x["label"] for x in snap_b["screens"][0]["clients"]], ["B"])
        self.assertEqual(snap_a["visits"]["today_unique_by_device"], {"windows": 1})
        self.assertEqual(snap_b["visits"]["today_unique_by_device"], {"android": 1})

    def test_demo_snapshot_excludes_private_runtime_data(self) -> None:
        source = self.tenants / "template" / "data"
        source.mkdir(parents=True)
        (source / "config.json").write_text('{"screens": []}', encoding="utf-8")
        for name in (
            "auth.json",
            "checkin.sqlite3",
            "feedback.sqlite3",
            "push.sqlite3",
            "screen_watch_stats.json",
            "sync_state.json",
        ):
            (source / name).write_bytes(b"private")
        isolated = "d" + "a" * 24

        with patch.object(provider_demo, "ensure_tenant_schema"):
            provider_demo.provision_demo_isolated_snapshot("template", isolated)

        copied = self.tenants / isolated / "data"
        self.assertTrue((copied / "config.json").is_file())
        self.assertFalse((copied / "auth.json").exists())
        self.assertFalse((copied / "checkin.sqlite3").exists())
        self.assertFalse((copied / "feedback.sqlite3").exists())
        self.assertFalse((copied / "push.sqlite3").exists())
        self.assertFalse((copied / "screen_watch_stats.json").exists())

    def test_full_export_reads_only_current_tenant_paths(self) -> None:
        tenant_data = self.tenants / "school-a" / "data"
        tenant_data.mkdir(parents=True)
        (tenant_data / "config.json").write_text('{"owner": "school-a"}', encoding="utf-8")

        def tenant_path(path: Path) -> Path:
            return tenant_data / path.name

        with patch.object(import_bundle, "map_data_path", side_effect=tenant_path):
            payload = import_bundle.export_bundle_bytes()
        with zipfile.ZipFile(BytesIO(payload), "r") as archive:
            self.assertEqual(archive.read("config.json"), b'{"owner": "school-a"}')


if __name__ == "__main__":
    unittest.main()
