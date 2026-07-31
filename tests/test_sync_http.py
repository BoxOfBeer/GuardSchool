"""Тесты синхронизации с облаком (Bearer, revision payload)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

from guardschool.capabilities import reset_capabilities_for_tests
from guardschool.gs_sync_http import public_revision_payload, require_sync_bearer


class SyncHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_capabilities_for_tests()
        os.environ.pop("GUARDSCHOOL_SYNC_TOKEN", None)

    def test_require_sync_bearer_missing_token_env(self) -> None:
        req = MagicMock()
        req.headers = {}
        with self.assertRaises(HTTPException) as ctx:
            require_sync_bearer(req)
        self.assertEqual(ctx.exception.status_code, 503)

    def test_require_sync_bearer_wrong_token(self) -> None:
        os.environ["GUARDSCHOOL_SYNC_TOKEN"] = "secret"
        req = MagicMock()
        req.headers = {"authorization": "Bearer wrong"}
        with self.assertRaises(HTTPException) as ctx:
            require_sync_bearer(req)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_require_sync_bearer_ok(self) -> None:
        os.environ["GUARDSCHOOL_SYNC_TOKEN"] = "secret"
        req = MagicMock()
        req.headers = {"authorization": "Bearer secret"}
        require_sync_bearer(req)

    def test_public_revision_payload_keys(self) -> None:
        payload = public_revision_payload()
        self.assertIn("data_revision", payload)
        self.assertIn("app_version", payload)
        self.assertIn("cloud_db", payload)


if __name__ == "__main__":
    unittest.main()
