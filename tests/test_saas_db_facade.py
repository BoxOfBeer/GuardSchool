"""Фасад saas_db: embedded PG, private overlay, community stub."""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from guardschool import saas_db


class SaasDbFacadeTests(unittest.TestCase):
    _tmpdir: str | None = None

    def tearDown(self) -> None:
        os.environ.pop("GUARDSCHOOL_SAAS_DATABASE_URL", None)
        os.environ.pop("GUARDSCHOOL_PRIVATE_PYTHONPATH", None)
        sys.modules.pop("guardschool._saas_db_backend", None)  # _private_facade cache key
        sys.modules.pop("guardschool_private.saas_db", None)
        sys.modules.pop("guardschool_private", None)
        if self._tmpdir and self._tmpdir in sys.path:
            sys.path.remove(self._tmpdir)
        importlib.reload(saas_db)

    def test_schema_name_for_slug_via_facade(self) -> None:
        self.assertEqual(saas_db.schema_name_for_slug("My-School"), "t_myschool")

    def test_disabled_without_database_url(self) -> None:
        os.environ.pop("GUARDSCHOOL_SAAS_DATABASE_URL", None)
        sys.modules.pop("guardschool._saas_db_backend", None)  # _private_facade cache key
        importlib.reload(saas_db)
        self.assertFalse(saas_db.saas_db_enabled())

    def test_private_saas_db_module_overrides(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gs_saas_db_test_") as tmp:
            self._tmpdir = tmp
            pkg = Path(tmp) / "guardschool_private"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            (pkg / "saas_db.py").write_text(
                textwrap.dedent(
                    """
                    def saas_db_enabled():
                        return True

                    def saas_database_url():
                        return "postgresql://example"
                    """
                ),
                encoding="utf-8",
            )
            os.environ["GUARDSCHOOL_PRIVATE_PYTHONPATH"] = tmp
            sys.modules.pop("guardschool._saas_db_backend", None)  # _private_facade cache key
            importlib.reload(saas_db)
            self.assertTrue(saas_db.saas_db_enabled())
            self.assertIn("postgresql", saas_db.saas_database_url())


if __name__ == "__main__":
    unittest.main()
