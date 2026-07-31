"""Монтирование SaaS/commercial routes только при наличии _*_pg."""
from __future__ import annotations

import os
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from guardschool.commercial_routes import configure_commercial_http
from guardschool.layer_loader import reset_layer_loader_for_tests
from guardschool.saas_routes import configure_saas_http


class RoutesSeparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_mode = os.environ.get("GUARDSCHOOL_DEPLOYMENT_MODE")
        self._prev_layer = os.environ.get("GUARDSCHOOL_LAYER_PATH")
        os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = "local"
        os.environ.pop("GUARDSCHOOL_LAYER_PATH", None)
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
        reset_layer_loader_for_tests()

    def test_local_saas_push_stub_503(self) -> None:
        app = FastAPI()
        configure_saas_http(app)
        client = TestClient(app)
        r = client.get("/api/screen/tv-1/push/vapid-public-key")
        self.assertEqual(r.status_code, 503)

    def test_local_tv_pair_stub_503(self) -> None:
        app = FastAPI()
        configure_saas_http(app)
        client = TestClient(app)
        r = client.post("/api/tv/pair", json={"code": "abcd", "pin": "1234", "screen_slug": "tv-1"})
        self.assertEqual(r.status_code, 503)

    def test_local_commercial_register_stub_503(self) -> None:
        app = FastAPI()
        configure_commercial_http(app)
        client = TestClient(app)
        r = client.post("/api/saas/register", json={})
        self.assertEqual(r.status_code, 503)


if __name__ == "__main__":
    unittest.main()
