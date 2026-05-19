"""Фасады gs_push / gs_sync_http без полной реализации."""
from __future__ import annotations

import os
import unittest

from guardschool import gs_push, gs_sync_http
from guardschool.capabilities import CAP_PUSH_NOTIFICATIONS, CapabilityStatus, get_capabilities, reset_capabilities_for_tests
from guardschool.layer_loader import reset_layer_loader_for_tests
from guardschool.optional_imports import push_module


class PrivateFacadeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_mode = os.environ.get("GUARDSCHOOL_DEPLOYMENT_MODE")
        os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = "local"
        os.environ.pop("GUARDSCHOOL_LAYER_PATH", None)
        reset_capabilities_for_tests()
        reset_layer_loader_for_tests()

    def tearDown(self) -> None:
        if self._prev_mode is None:
            os.environ.pop("GUARDSCHOOL_DEPLOYMENT_MODE", None)
        else:
            os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = self._prev_mode
        reset_capabilities_for_tests()
        reset_layer_loader_for_tests()

    def test_push_stub_vapid_empty(self) -> None:
        self.assertEqual(gs_push.vapid_public_key(), "")

    def test_sync_http_public_revision_local(self) -> None:
        payload = gs_sync_http.public_revision_payload()
        self.assertIn("data_revision", payload)
        self.assertIn("app_version", payload)

    def test_local_push_capability_missing(self) -> None:
        ensure = __import__("guardschool.capabilities", fromlist=["ensure_capabilities_initialized"]).ensure_capabilities_initialized
        ensure()
        caps = get_capabilities()
        self.assertEqual(caps[CAP_PUSH_NOTIFICATIONS].status, CapabilityStatus.missing)
        self.assertIsNone(push_module())


if __name__ == "__main__":
    unittest.main()
