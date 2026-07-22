from __future__ import annotations

import unittest

from guardschool.gs_pwa_profile import PWA_DEFAULT_ICON, PWA_DEFAULT_TITLE, resolve_pwa_profile


def _widget(widget_id: str, widget_type: str, **settings: str) -> dict:
    return {"id": widget_id, "type": widget_type, "enabled": True, "settings": settings}


class PwaProfileTests(unittest.TestCase):
    def test_booking_override_wins_general_profile(self) -> None:
        cfg = {
            "pwa": {"title": "Общее", "icon_url": "/uploads/general.png"},
            "screens": [
                {
                    "slug": "mobil",
                    "widgets": [
                        _widget(
                            "booking",
                            "booking_public",
                            pwa_title="Своя запись",
                            pwa_icon_url="/uploads/booking.png",
                        )
                    ],
                }
            ],
        }
        self.assertEqual(resolve_pwa_profile(cfg, "mobil"), ("Своя запись", "/uploads/booking.png"))

    def test_booking_empty_fields_inherit_general_independently(self) -> None:
        cfg = {
            "pwa": {"title": "Общее", "icon_url": "/uploads/general.png"},
            "screens": [
                {
                    "slug": "mobil",
                    "widgets": [_widget("booking", "booking_manager", pwa_title="Управление", pwa_icon_url="")],
                }
            ],
        }
        self.assertEqual(resolve_pwa_profile(cfg, "mobil"), ("Управление", "/uploads/general.png"))

    def test_checkin_monitor_wins_submit_and_general(self) -> None:
        cfg = {
            "pwa": {"title": "Общее", "icon_url": "/uploads/general.png"},
            "screens": [
                {
                    "slug": "check",
                    "widgets": [
                        _widget("submit", "checkin_submit", pwa_title="Форма", pwa_icon_url="/uploads/form.png"),
                        _widget("monitor", "checkin_monitor", pwa_title="Сводка", pwa_icon_url="/uploads/board.png"),
                    ],
                }
            ],
        }
        self.assertEqual(resolve_pwa_profile(cfg, "check"), ("Сводка", "/uploads/board.png"))

    def test_unknown_screen_uses_general_then_technical_defaults(self) -> None:
        cfg = {"pwa": {"title": "Общее", "icon_url": "/uploads/general.png"}, "screens": []}
        self.assertEqual(resolve_pwa_profile(cfg, "missing"), ("Общее", "/uploads/general.png"))
        self.assertEqual(resolve_pwa_profile({}, "missing"), (PWA_DEFAULT_TITLE, PWA_DEFAULT_ICON))

    def test_disabled_widget_does_not_override_general(self) -> None:
        widget = _widget("booking", "booking_public", pwa_title="Скрыто", pwa_icon_url="/uploads/hidden.png")
        widget["enabled"] = False
        cfg = {
            "pwa": {"title": "Общее", "icon_url": "/uploads/general.png"},
            "screens": [{"slug": "mobil", "widgets": [widget]}],
        }
        self.assertEqual(resolve_pwa_profile(cfg, "mobil"), ("Общее", "/uploads/general.png"))

    def test_device_filter_selects_public_or_manager_profile_on_same_screen(self) -> None:
        cfg = {
            "pwa": {"title": "Общее", "icon_url": "/uploads/general.png"},
            "screens": [
                {
                    "slug": "mobil",
                    "widgets": [
                        _widget("public", "booking_public", pwa_title="Записаться", pwa_icon_url="/uploads/public.png"),
                        _widget("manager", "booking_manager", pwa_title="Управление", pwa_icon_url="/uploads/manager.png"),
                    ],
                }
            ],
        }
        self.assertEqual(
            resolve_pwa_profile(cfg, "mobil", ("booking_public",)),
            ("Записаться", "/uploads/public.png"),
        )
        self.assertEqual(
            resolve_pwa_profile(cfg, "mobil", ("booking_manager",)),
            ("Управление", "/uploads/manager.png"),
        )


if __name__ == "__main__":
    unittest.main()
