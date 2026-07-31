"""Community local: без слоя SaaS capabilities missing, stubs → 503."""
from __future__ import annotations

import os
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from guardschool.capabilities import (
    SAAS_CAPABILITY_IDS,
    CapabilityStatus,
    ensure_capabilities_initialized,
    get_capabilities,
    reset_capabilities_for_tests,
)
from guardschool.gs_deploy import deployment_mode
from guardschool.layer_loader import reset_layer_loader_for_tests
from guardschool.saas_routes import configure_saas_http


class CommunityLocalModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_mode = os.environ.get("GUARDSCHOOL_DEPLOYMENT_MODE")
        self._prev_layer = os.environ.get("GUARDSCHOOL_LAYER_PATH")
        os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = "local"
        os.environ.pop("GUARDSCHOOL_LAYER_PATH", None)
        reset_capabilities_for_tests()
        reset_layer_loader_for_tests()

    def tearDown(self) -> None:
        if self._prev_mode is None:
            os.environ.pop("GUARDSCHOOL_DEPLOYMENT_MODE", None)
        else:
            os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = self._prev_mode
        if self._prev_layer is None:
            os.environ.pop("GUARDSCHOOL_LAYER_PATH", None)
        else:
            os.environ["GUARDSCHOOL_LAYER_PATH"] = self._prev_layer
        reset_capabilities_for_tests()
        reset_layer_loader_for_tests()

    def test_deployment_mode_local(self) -> None:
        self.assertEqual(deployment_mode(), "local")

    def test_saas_capabilities_missing(self) -> None:
        ensure_capabilities_initialized()
        caps = get_capabilities()
        for cap_id in SAAS_CAPABILITY_IDS:
            self.assertEqual(
                caps[cap_id].status,
                CapabilityStatus.missing,
                msg=cap_id,
            )

    def test_feedback_stub_returns_503(self) -> None:
        ensure_capabilities_initialized()
        app = FastAPI()
        configure_saas_http(app)
        client = TestClient(app)
        r = client.post(
            "/api/screen/test-screen/feedback",
            json={"device_hash": "abc", "message": "hello"},
        )
        self.assertEqual(r.status_code, 503)

    def test_sync_status_stub_returns_503(self) -> None:
        ensure_capabilities_initialized()
        app = FastAPI()
        configure_saas_http(app)
        client = TestClient(app)
        r = client.get("/api/sync/status")
        self.assertEqual(r.status_code, 503)

    def test_core_capabilities_endpoint_still_defined(self) -> None:
        """Пути остаются (stub), не 404."""
        app = FastAPI()
        configure_saas_http(app)
        paths = {getattr(route, "path", "") for route in app.routes if hasattr(route, "path")}
        self.assertIn("/api/screen/{slug}/feedback", paths)
        self.assertIn("/api/sync/status", paths)
        self.assertIn("/api/admin/sync-status", paths)
        self.assertIn("/api/screen/{slug}/push/vapid-public-key", paths)
        self.assertIn("/api/screen/{slug}/tv-pair-link", paths)

    def test_push_stub_returns_503(self) -> None:
        ensure_capabilities_initialized()
        app = FastAPI()
        configure_saas_http(app)
        client = TestClient(app)
        r = client.get("/api/screen/test-screen/push/vapid-public-key")
        self.assertEqual(r.status_code, 503)

    def test_tv_pair_stub_returns_503(self) -> None:
        ensure_capabilities_initialized()
        app = FastAPI()
        configure_saas_http(app)
        client = TestClient(app)
        r = client.get("/api/screen/test-screen/tv-pair-link")
        self.assertEqual(r.status_code, 503)


if __name__ == "__main__":
    unittest.main()
