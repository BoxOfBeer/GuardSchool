"""visibility / audience для capabilities (отдельно от status и has_capability)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock

from guardschool.capabilities import (
    CAP_CLOUD_SYNC,
    CAP_PAYMENT,
    CAP_PRODUCTION_PORTAL,
    CAP_REGISTRATION,
    CAP_TENANT_FEEDBACK,
    CapabilityStatus,
    CapabilityVisibility,
    default_capability_visibility,
    ensure_capabilities_initialized,
    filter_capabilities_for_audience,
    get_capabilities,
    get_capabilities_public,
    has_capability,
    reset_capabilities_for_tests,
    resolve_capabilities_audience,
)
from guardschool.layer_loader import reset_layer_loader_for_tests


class CapabilityVisibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_mode = os.environ.get("GUARDSCHOOL_DEPLOYMENT_MODE")
        self._prev_aud = os.environ.get("GUARDSCHOOL_CAPABILITIES_AUDIENCE")
        self._prev_dev = os.environ.get("GUARDSCHOOL_DEV_CAPABILITIES")
        self._prev_layer = os.environ.get("GUARDSCHOOL_LAYER_PATH")
        os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = "hybrid"
        os.environ.pop("GUARDSCHOOL_CAPABILITIES_AUDIENCE", None)
        os.environ.pop("GUARDSCHOOL_DEV_CAPABILITIES", None)
        os.environ.pop("GUARDSCHOOL_LAYER_PATH", None)
        reset_capabilities_for_tests()
        reset_layer_loader_for_tests()

    def tearDown(self) -> None:
        for key, val in (
            ("GUARDSCHOOL_DEPLOYMENT_MODE", self._prev_mode),
            ("GUARDSCHOOL_CAPABILITIES_AUDIENCE", self._prev_aud),
            ("GUARDSCHOOL_DEV_CAPABILITIES", self._prev_dev),
            ("GUARDSCHOOL_LAYER_PATH", self._prev_layer),
        ):
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        reset_capabilities_for_tests()
        reset_layer_loader_for_tests()

    def test_default_visibility_mapping(self) -> None:
        self.assertEqual(default_capability_visibility(CAP_REGISTRATION), CapabilityVisibility.licensor)
        self.assertEqual(default_capability_visibility(CAP_CLOUD_SYNC), CapabilityVisibility.school)
        self.assertEqual(default_capability_visibility(CAP_TENANT_FEEDBACK), CapabilityVisibility.school)

    def test_school_audience_excludes_licensor_caps(self) -> None:
        ensure_capabilities_initialized()
        pub = get_capabilities_public(audience="school")
        self.assertIn(CAP_CLOUD_SYNC, pub)
        self.assertNotIn(CAP_REGISTRATION, pub)
        self.assertNotIn(CAP_PAYMENT, pub)
        self.assertNotIn(CAP_PRODUCTION_PORTAL, pub)

    def test_licensor_audience_includes_licensor_caps(self) -> None:
        ensure_capabilities_initialized()
        pub = get_capabilities_public(audience="licensor")
        self.assertIn(CAP_REGISTRATION, pub)
        self.assertIn(CAP_CLOUD_SYNC, pub)

    def test_internal_audience_includes_all_registered(self) -> None:
        ensure_capabilities_initialized()
        all_caps = get_capabilities()
        pub = get_capabilities_public(audience="internal")
        self.assertEqual(set(pub.keys()), set(all_caps.keys()))

    def test_has_capability_independent_of_public_audience(self) -> None:
        ensure_capabilities_initialized()
        all_caps = get_capabilities()
        if all_caps[CAP_REGISTRATION].status != CapabilityStatus.available:
            self.skipTest("registration not available in this tree")
        self.assertTrue(has_capability(CAP_REGISTRATION))
        pub = get_capabilities_public(audience="school")
        self.assertNotIn(CAP_REGISTRATION, pub)

    def test_filter_capabilities_for_audience(self) -> None:
        ensure_capabilities_initialized()
        caps = get_capabilities()
        school_only = filter_capabilities_for_audience(caps, "school")
        for _id, info in school_only.items():
            self.assertEqual(info.visibility, CapabilityVisibility.school)

    def test_resolve_audience_school_host(self) -> None:
        os.environ["GUARDSCHOOL_PUBLIC_SCHOOL_HOST"] = "school.example.test"
        req = MagicMock()
        req.headers = {"host": "school.example.test"}
        self.assertEqual(resolve_capabilities_audience(req), "school")

    def test_resolve_audience_portal_host(self) -> None:
        req = MagicMock()
        req.headers = {"host": "guarddoc.ru"}
        self.assertEqual(resolve_capabilities_audience(req), "licensor")

    def test_resolve_audience_localhost_internal(self) -> None:
        req = MagicMock()
        req.headers = {"host": "127.0.0.1:8000"}
        self.assertEqual(resolve_capabilities_audience(req), "internal")

    def test_env_override_audience(self) -> None:
        os.environ["GUARDSCHOOL_CAPABILITIES_AUDIENCE"] = "licensor"
        req = MagicMock()
        req.headers = {"host": "school.example.test"}
        os.environ["GUARDSCHOOL_PUBLIC_SCHOOL_HOST"] = "school.example.test"
        self.assertEqual(resolve_capabilities_audience(req), "licensor")


if __name__ == "__main__":
    unittest.main()
