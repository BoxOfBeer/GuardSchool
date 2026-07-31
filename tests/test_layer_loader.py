"""Загрузка опциональных слоёв."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guardschool.capabilities import reset_capabilities_for_tests
from guardschool.layer_loader import load_optional_layers, reset_layer_loader_for_tests


def _reset() -> None:
    reset_capabilities_for_tests()
    reset_layer_loader_for_tests()


class LayerLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset()

    def tearDown(self) -> None:
        _reset()

    def test_loads_saas_layer_once(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as tmp:
            layer = Path(tmp) / "saas"
            layer.mkdir()
            (layer / "__init__.py").write_text(
                "def register_capabilities(registry):\n"
                "    pass\n"
                "def register_routes(app):\n"
                "    pass\n",
                encoding="utf-8",
            )
            os.environ["GUARDSCHOOL_LAYER_PATH"] = tmp
            try:
                names1 = load_optional_layers()
                names2 = load_optional_layers()
            finally:
                os.environ.pop("GUARDSCHOOL_LAYER_PATH", None)
        self.assertEqual(names1, ["saas"])
        self.assertEqual(names2, ["saas"])


if __name__ == "__main__":
    unittest.main()
