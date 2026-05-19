"""Commercial layer из репозитория поднимает capabilities и routes."""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from fastapi import FastAPI

from guardschool.capabilities import (
    CAP_LICENSE_CHECK,
    CapabilityStatus,
    ensure_capabilities_initialized,
    get_capabilities,
    reset_capabilities_for_tests,
)
from guardschool.layer_loader import (
    apply_layer_routes,
    commercial_routes_mounted_by_layer,
    is_commercial_layer_loaded,
    reset_layer_loader_for_tests,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


class CommercialLayerSkeletonTests(unittest.TestCase):
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

    def test_commercial_layer_loads(self) -> None:
        self.assertTrue(is_commercial_layer_loaded())

    def test_commercial_routes_mounted(self) -> None:
        app = FastAPI()
        apply_layer_routes(app)
        self.assertTrue(commercial_routes_mounted_by_layer())

    def test_license_check_available(self) -> None:
        ensure_capabilities_initialized()
        caps = get_capabilities()
        self.assertEqual(caps[CAP_LICENSE_CHECK].status, CapabilityStatus.available)
        self.assertEqual(caps[CAP_LICENSE_CHECK].module_hint, "commercial")


if __name__ == "__main__":
    unittest.main()
