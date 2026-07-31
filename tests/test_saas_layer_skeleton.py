"""SaaS layer из репозитория (layers/saas) поднимает capabilities и routes."""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from guardschool.capabilities import (
    CAP_TENANT_FEEDBACK,
    CapabilityStatus,
    ensure_capabilities_initialized,
    get_capabilities,
    reset_capabilities_for_tests,
)
from guardschool.layer_loader import (
    apply_layer_routes,
    is_saas_layer_loaded,
    reset_layer_loader_for_tests,
    saas_layer_mounted_groups,
)
from guardschool.saas_routes import configure_saas_http

_REPO_ROOT = Path(__file__).resolve().parent.parent


class SaasLayerSkeletonTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_layer = os.environ.get("GUARDSCHOOL_LAYER_PATH")
        self._prev_mode = os.environ.get("GUARDSCHOOL_DEPLOYMENT_MODE")
        os.environ["GUARDSCHOOL_LAYER_PATH"] = str(_REPO_ROOT)
        os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = "local"
        reset_capabilities_for_tests()
        reset_layer_loader_for_tests()

    def tearDown(self) -> None:
        if self._prev_layer is None:
            os.environ.pop("GUARDSCHOOL_LAYER_PATH", None)
        else:
            os.environ["GUARDSCHOOL_LAYER_PATH"] = self._prev_layer
        if self._prev_mode is None:
            os.environ.pop("GUARDSCHOOL_DEPLOYMENT_MODE", None)
        else:
            os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = self._prev_mode
        reset_capabilities_for_tests()
        reset_layer_loader_for_tests()

    def test_layer_loads_from_repo(self) -> None:
        self.assertTrue(is_saas_layer_loaded())

    def test_layer_marks_route_groups(self) -> None:
        app = FastAPI()
        apply_layer_routes(app)
        groups = saas_layer_mounted_groups()
        self.assertIn("feedback", groups)
        self.assertIn("cloud_sync", groups)
        self.assertIn("push", groups)

    def test_tenant_feedback_available_with_layer(self) -> None:
        ensure_capabilities_initialized()
        caps = get_capabilities()
        self.assertEqual(caps[CAP_TENANT_FEEDBACK].status, CapabilityStatus.available)
        self.assertEqual(caps[CAP_TENANT_FEEDBACK].module_hint, "saas")

    def test_configure_saas_http_skips_when_layer_mounted(self) -> None:
        app = FastAPI()
        apply_layer_routes(app)
        configure_saas_http(app)
        paths = {getattr(route, "path", "") for route in app.routes if hasattr(route, "path")}
        self.assertIn("/api/admin/feedback", paths)
        # stub-only app would still have path; layer mounts real router with same paths
        client = TestClient(app)
        r = client.get("/api/admin/feedback")
        self.assertIn(r.status_code, (401, 403, 503))


if __name__ == "__main__":
    unittest.main()
