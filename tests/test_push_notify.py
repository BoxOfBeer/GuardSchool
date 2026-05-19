"""Тесты push_notify (local — без gs_push)."""
from __future__ import annotations

import os
import unittest

from guardschool.capabilities import reset_capabilities_for_tests
from guardschool.push_notify import notify_push_to_screen, push_enabled_on_server


class PushNotifyTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_capabilities_for_tests()
        os.environ["GUARDSCHOOL_DEPLOYMENT_MODE"] = "local"

    def tearDown(self) -> None:
        reset_capabilities_for_tests()

    def test_push_disabled_in_local(self) -> None:
        self.assertFalse(push_enabled_on_server())

    def test_notify_noop_when_disabled(self) -> None:
        notify_push_to_screen(
            tenant_id="local",
            screen_slug="tv-1",
            topic="test",
            title="T",
            body="B",
            url="/screen/tv-1",
        )


if __name__ == "__main__":
    unittest.main()
