"""Проверка подключения роутеров к FastAPI app."""

from __future__ import annotations



import unittest





class RoutesRegisteredTests(unittest.TestCase):

    def test_core_open_routes_present(self) -> None:

        from guardschool.app import app



        paths = {getattr(r, "path", "") for r in app.routes if hasattr(r, "path")}

        for expected in (

            "/api/capabilities",

            "/api/widgets/registry",

            "/api/sync/status",

            "/api/sync/bundle",

            "/api/screen/{slug}/push/vapid-public-key",

            "/api/screen/{slug}/push/subscribe",

            "/api/screen/{slug}/tv-pair-link",

            "/api/screen/{slug}/feedback",

            "/api/admin/feedback",

        ):

            self.assertIn(expected, paths, msg=f"missing route {expected}")



    def test_commercial_routes_present(self) -> None:

        from guardschool.app import app



        paths = {getattr(r, "path", "") for r in app.routes if hasattr(r, "path")}

        for expected in (

            "/api/provider/licenses",

            "/api/provider/demo",

            "/api/provider/portal-cms",

            "/api/saas/register",

        ):

            self.assertIn(expected, paths, msg=f"missing route {expected}")





if __name__ == "__main__":

    unittest.main()

