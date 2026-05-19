"""guardschool_private на GUARDSCHOOL_PRIVATE_PYTHONPATH."""
from __future__ import annotations

import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from guardschool.private_modules import (
    ensure_private_pythonpath,
    import_optional_module,
    module_present,
    private_pythonpath,
)


class PrivateModulesTests(unittest.TestCase):
    _tmpdir: str | None = None

    def tearDown(self) -> None:
        os.environ.pop("GUARDSCHOOL_PRIVATE_PYTHONPATH", None)
        sys.modules.pop("guardschool_private.gs_private_marker_test", None)
        sys.modules.pop("guardschool_private", None)
        if self._tmpdir and self._tmpdir in sys.path:
            sys.path.remove(self._tmpdir)

    def test_module_present_and_import_from_private_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gs_private_test_") as tmp:
            self._tmpdir = tmp
            pkg = Path(tmp) / "guardschool_private"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            mod_name = "gs_private_marker_test"
            (pkg / f"{mod_name}.py").write_text("MARKER = 42\n", encoding="utf-8")
            os.environ["GUARDSCHOOL_PRIVATE_PYTHONPATH"] = tmp
            ensure_private_pythonpath()
            self.assertIsNotNone(private_pythonpath())
            self.assertTrue(module_present(mod_name))
            mod = import_optional_module(mod_name)
            self.assertEqual(mod.MARKER, 42)


if __name__ == "__main__":
    unittest.main()
