from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from guardschool import gs_booking as booking


class BookingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self.tmp.name) / "booking.sqlite3"
        self.path_patch = patch.object(booking, "_db_path", lambda: self.db)
        self.tz_patch = patch.object(booking, "_tz", lambda: timezone.utc)
        self.path_patch.start()
        self.tz_patch.start()
        self.module = "test-module"

    def tearDown(self):
        self.tz_patch.stop()
        self.path_patch.stop()
        self.tmp.cleanup()

    @staticmethod
    def future_monday():
        day = datetime.now(timezone.utc) + timedelta(days=14)
        return (day - timedelta(days=day.weekday())).replace(hour=9, minute=0, second=0, microsecond=0)

    @staticmethod
    def person(start, device="device-identifier-0001", service="basic"):
        return {"device_id": device, "service_id": service, "start_at": start.isoformat(), "family_name": "Иванов", "given_name": "Иван", "phone": "+70000000000"}

    @staticmethod
    def slot_at(state, start):
        return next(
            slot
            for day in state["days"]
            for slot in day["slots"]
            if slot["start_at"] == start.isoformat()
        )

    def test_public_data_hides_personal_fields(self):
        start = self.future_monday()
        booking.create_booking(self.module, self.person(start))
        state = booking.availability(self.module, start.date().isoformat(), "basic", "device-identifier-0001")
        self.assertTrue(state["mine"])
        self.assertNotIn("phone", state["mine"][0])
        self.assertNotIn("family_name", state["mine"][0])

    def test_pending_cancel_keeps_slot_until_admin_confirms(self):
        start = self.future_monday()
        row = booking.create_booking(self.module, self.person(start))
        booking.request_cancel(self.module, row["id"], "device-identifier-0001")
        blocked = self.slot_at(booking.availability(self.module, start.date().isoformat(), "basic"), start)
        self.assertEqual(blocked["status"], "cancel_requested")
        self.assertFalse(blocked["available"])
        booking.admin_action(self.module, row["id"], "confirm_cancel", {})
        released = self.slot_at(booking.availability(self.module, start.date().isoformat(), "basic"), start)
        self.assertEqual(released["status"], "free")
        self.assertTrue(released["available"])

    def test_confirmed_slot_stays_visible_and_response_has_timezone(self):
        start = self.future_monday()
        booking.create_booking(self.module, self.person(start))
        state = booking.availability(self.module, start.date().isoformat(), "basic")
        slot = self.slot_at(state, start)
        self.assertEqual(slot["status"], "booked")
        self.assertFalse(slot["available"])
        self.assertEqual(state["timezone"], "UTC")

    def test_weekly_limit_counts_cancelled_records(self):
        start = self.future_monday()
        for i in range(5):
            row = booking.create_booking(self.module, self.person(start + timedelta(hours=i)))
            booking.request_cancel(self.module, row["id"], "device-identifier-0001")
            booking.admin_action(self.module, row["id"], "confirm_cancel", {})
        with self.assertRaisesRegex(ValueError, "максимальное"):
            booking.create_booking(self.module, self.person(start + timedelta(hours=6)))

    def test_different_duration_blocks_overlapping_steps(self):
        cfg = booking.default_booking_config()
        cfg["step_min"] = 15
        cfg["services"] = [{"id": "long", "title": "Длительная", "duration_min": 45, "active": True}]
        booking.save_config(self.module, cfg)
        start = self.future_monday()
        booking.create_booking(self.module, self.person(start, service="long"))
        state = booking.availability(self.module, start.date().isoformat(), "long")
        slots = {s["label"]: s for d in state["days"] if d["date"] == start.date().isoformat() for s in d["slots"]}
        self.assertEqual(slots["09:15"]["status"], "booked")
        self.assertEqual(slots["09:30"]["status"], "booked")
        self.assertEqual(slots["09:45"]["status"], "free")

    def test_overnight_window_accepts_after_midnight_slot(self):
        start = self.future_monday()
        cfg = booking.default_booking_config()
        cfg["weekly_windows"] = {str(i): [] for i in range(7)}
        cfg["weekly_windows"][str(start.weekday())] = [["22:00", "03:00"]]
        booking.save_config(self.module, cfg)
        after_midnight = start.replace(hour=0, minute=30) + timedelta(days=1)
        row = booking.create_booking(self.module, self.person(after_midnight))
        self.assertEqual(row["start_at"], after_midnight.isoformat())


if __name__ == "__main__":
    unittest.main()
