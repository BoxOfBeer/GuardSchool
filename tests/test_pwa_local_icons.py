from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from guardschool.gs_paths import STATIC_DIR
from guardschool import gs_pwa_local_icons
from guardschool.gs_pwa_local_icons import local_manifest_icon_entries


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise AssertionError(f"Not a PNG with IHDR: {path}")
    return struct.unpack(">II", data[16:24])


class PwaLocalIconsTests(unittest.TestCase):
    def test_default_icons_declare_their_real_sizes(self) -> None:
        entries = local_manifest_icon_entries("/static/pwa/icon_default.png")
        self.assertEqual([entry["sizes"] for entry in entries], ["192x192", "512x512"])
        self.assertEqual(
            _png_size(STATIC_DIR / "pwa" / "icon_default_192.png"),
            (192, 192),
        )
        self.assertEqual(
            _png_size(STATIC_DIR / "pwa" / "icon_default.png"),
            (512, 512),
        )

    def test_missing_custom_raster_never_claims_fake_512_size(self) -> None:
        entries = local_manifest_icon_entries("/uploads/widget_images/missing.png")
        self.assertEqual(entries[0]["sizes"], "any")
        self.assertEqual(entries[0]["type"], "image/png")

    def test_vector_icon_uses_scalable_size(self) -> None:
        entries = local_manifest_icon_entries("/uploads/widget_images/logo.svg")
        self.assertEqual(
            entries,
            [
                {
                    "src": "/uploads/widget_images/logo.svg",
                    "sizes": "any",
                    "type": "image/svg+xml",
                    "purpose": "any",
                }
            ],
        )

    def test_uploaded_raster_prefers_generated_192_and_512_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "logo.jpg"
            source.write_bytes(b"test")
            variants = {
                192: source.with_name("logo_gs_pwa192.png"),
                512: source.with_name("logo_gs_pwa512.png"),
            }
            with (
                patch.object(gs_pwa_local_icons, "_resolve_public_icon", return_value=(source, True)),
                patch.object(
                    gs_pwa_local_icons,
                    "_ensure_square_png_variant",
                    side_effect=lambda _source, size: variants[size],
                ),
            ):
                entries = local_manifest_icon_entries("/uploads/widget_images/logo.jpg")
        self.assertEqual([entry["sizes"] for entry in entries], ["192x192", "512x512"])
        self.assertTrue(all(entry["type"] == "image/png" for entry in entries))

    def test_non_writable_raster_reports_actual_size(self) -> None:
        source = STATIC_DIR / "pwa" / "screenshot_wide.png"
        with (
            patch.object(gs_pwa_local_icons, "_resolve_public_icon", return_value=(source, False)),
            patch.object(gs_pwa_local_icons, "_image_size", return_value=(1280, 720)),
        ):
            entries = local_manifest_icon_entries("/static/pwa/screenshot_wide.png")
        self.assertEqual(entries[0]["sizes"], "1280x720")


if __name__ == "__main__":
    unittest.main()
