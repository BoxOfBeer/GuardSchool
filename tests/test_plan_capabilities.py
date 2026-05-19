"""plan_id → locked capabilities (env и tenant БД)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from guardschool.capabilities import (
    CAP_CLOUD_SYNC,
    CAP_PUSH_NOTIFICATIONS,
    CAP_LICENSE_CHECK,
    CapabilityStatus,
    ensure_capabilities_initialized,
    get_capabilities,
    has_capability,
    reset_capabilities_for_tests,
)
from guardschool.layer_loader import reset_layer_loader_for_tests
from guardschool.tenant_ctx import set_tenant_slug


class PlanCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_mode = os.environ.get("GUARDSCHOOL_DEPLOYMENT_MODE")
        self._prev_plan = os.environ.get("GUARDSCHOOL_TENANT_PLAN_ID")
        self._prev_layer = os.environ.get("GUARDSCHOOL_LAYER_PATH")
        os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = "hybrid"
        os.environ.pop("GUARDSCHOOL_LAYER_PATH", None)
        set_tenant_slug(None)
        reset_capabilities_for_tests()
        reset_layer_loader_for_tests()

    def tearDown(self) -> None:
        set_tenant_slug(None)
        if self._prev_mode is None:
            os.environ.pop("GUARDSCHOOL_DEPLOYMENT_MODE", None)
        else:
            os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = self._prev_mode
        if self._prev_plan is None:
            os.environ.pop("GUARDSCHOOL_TENANT_PLAN_ID", None)
        else:
            os.environ["GUARDSCHOOL_TENANT_PLAN_ID"] = self._prev_plan
        if self._prev_layer is None:
            os.environ.pop("GUARDSCHOOL_LAYER_PATH", None)
        else:
            os.environ["GUARDSCHOOL_LAYER_PATH"] = self._prev_layer
        reset_capabilities_for_tests()
        reset_layer_loader_for_tests()

    def _require_license_available(self) -> None:
        ensure_capabilities_initialized()
        caps = get_capabilities()
        self.assertEqual(
            caps[CAP_LICENSE_CHECK].status,
            CapabilityStatus.available,
            "hybrid tree needs saas_db.py for license_check",
        )

    def test_starter_env_locks_push(self) -> None:
        os.environ["GUARDSCHOOL_TENANT_PLAN_ID"] = "starter"
        self._require_license_available()
        caps = get_capabilities()
        self.assertEqual(caps[CAP_CLOUD_SYNC].status, CapabilityStatus.available)
        self.assertEqual(caps[CAP_PUSH_NOTIFICATIONS].status, CapabilityStatus.locked)
        self.assertFalse(has_capability(CAP_PUSH_NOTIFICATIONS))

    def test_free_env_locks_cloud_sync(self) -> None:
        os.environ["GUARDSCHOOL_TENANT_PLAN_ID"] = "free"
        self._require_license_available()
        caps = get_capabilities()
        self.assertEqual(caps[CAP_CLOUD_SYNC].status, CapabilityStatus.locked)

    def test_paid_db_unlocks_full_saas_bundle(self) -> None:
        os.environ.pop("GUARDSCHOOL_TENANT_PLAN_ID", None)
        set_tenant_slug("school-a")
        with (
            patch("guardschool.saas_db.saas_db_enabled", return_value=True),
            patch("guardschool.saas_db.lookup_tenant_plan_id", return_value="paid"),
        ):
            self._require_license_available()
            caps = get_capabilities()
        self.assertEqual(caps[CAP_CLOUD_SYNC].status, CapabilityStatus.available)
        self.assertEqual(caps[CAP_PUSH_NOTIFICATIONS].status, CapabilityStatus.available)
        self.assertTrue(has_capability(CAP_PUSH_NOTIFICATIONS))

    def test_tenant_db_overrides_env(self) -> None:
        os.environ["GUARDSCHOOL_TENANT_PLAN_ID"] = "free"
        set_tenant_slug("school-b")
        with (
            patch("guardschool.saas_db.saas_db_enabled", return_value=True),
            patch("guardschool.saas_db.lookup_tenant_plan_id", return_value="pro"),
        ):
            self._require_license_available()
            caps = get_capabilities()
        self.assertEqual(caps[CAP_PUSH_NOTIFICATIONS].status, CapabilityStatus.available)

    def test_normalize_plan_aliases(self) -> None:
        from guardschool.license_capability_provider import normalize_plan_id

        self.assertEqual(normalize_plan_id("paid"), "paid")
        self.assertEqual(normalize_plan_id("saas_only"), "saas_only")
        self.assertEqual(normalize_plan_id("full"), "paid")


if __name__ == "__main__":
    unittest.main()
