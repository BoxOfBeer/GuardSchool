"""Community local: commercial capabilities missing, provider API → 503."""
from __future__ import annotations

import os
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from guardschool.capabilities import (
    COMMERCIAL_CAPABILITY_IDS,
    CapabilityStatus,
    ensure_capabilities_initialized,
    get_capabilities,
    reset_capabilities_for_tests,
)
from guardschool.commercial_routes import configure_commercial_http
from guardschool.layer_loader import reset_layer_loader_for_tests


class CommunityCommercialTests(unittest.TestCase):
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

    def test_commercial_capabilities_missing(self) -> None:
        ensure_capabilities_initialized()
        caps = get_capabilities()
        for cap_id in COMMERCIAL_CAPABILITY_IDS:
            self.assertEqual(caps[cap_id].status, CapabilityStatus.missing, msg=cap_id)

    def test_provider_licenses_stub_503(self) -> None:
        ensure_capabilities_initialized()
        app = FastAPI()
        configure_commercial_http(app)
        client = TestClient(app)
        r = client.get("/api/provider/licenses")
        self.assertEqual(r.status_code, 503)

    def test_saas_register_stub_503(self) -> None:
        ensure_capabilities_initialized()
        app = FastAPI()
        configure_commercial_http(app)
        client = TestClient(app)
        r = client.post("/api/saas/register", json={})
        self.assertEqual(r.status_code, 503)


if __name__ == "__main__":
    unittest.main()
