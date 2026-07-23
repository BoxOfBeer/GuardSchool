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

    def test_availability_recovers_from_stale_service_id(self):
        cfg = booking.default_booking_config()
        cfg["services"] = [{"id": "current", "title": "Текущая", "duration_min": 30, "active": True}]
        booking.save_config(self.module, cfg)
        state = booking.availability(self.module, self.future_monday().date().isoformat(), "removed-service")
        self.assertEqual(state["service_id"], "current")
        self.assertTrue(state["days"])

    def test_admin_state_is_chronological(self):
        start = self.future_monday()
        booking.create_booking(self.module, self.person(start + timedelta(hours=2), device="device-identifier-0002"))
        booking.create_booking(self.module, self.person(start + timedelta(hours=1), device="device-identifier-0003"))
        state = booking.admin_state(self.module, start.date().isoformat())
        starts = [item["start_at"] for item in state["bookings"]]
        self.assertEqual(starts, sorted(starts))

    def test_admin_state_lists_upcoming_before_recent_past(self):
        monday = self.future_monday()
        now = monday + timedelta(days=2, hours=3)
        past_old = monday
        past_recent = monday + timedelta(days=2, hours=1)
        upcoming_near = monday + timedelta(days=2, hours=4)
        upcoming_later = monday + timedelta(days=3)
        with patch.object(booking, "_now", lambda: now):
            for index, start in enumerate((past_old, upcoming_later, past_recent, upcoming_near), start=10):
                booking.create_booking(self.module, self.person(start, device=f"device-identifier-{index:04d}"), actor="admin")
            state = booking.admin_state(self.module, monday.date().isoformat())
        self.assertEqual(
            [item["start_at"] for item in state["bookings"]],
            [upcoming_near.isoformat(), upcoming_later.isoformat(), past_recent.isoformat(), past_old.isoformat()],
        )
        self.assertEqual(state["now"], now.isoformat())

    def test_admin_all_scope_combines_active_bookings_across_weeks(self):
        first = self.future_monday()
        second = first + timedelta(days=10)
        booking.create_booking(self.module, self.person(second, device="device-identifier-0102"))
        booking.create_booking(self.module, self.person(first, device="device-identifier-0101"))
        state = booking.admin_state(self.module)
        self.assertEqual(state["scope"], "all")
        self.assertEqual(
            [item["start_at"] for item in state["bookings"]],
            [first.isoformat(), second.isoformat()],
        )

    def test_admin_move_updates_start_and_preserves_duration(self):
        start = self.future_monday()
        row = booking.create_booking(self.module, self.person(start), actor="admin")
        moved_start = start + timedelta(days=1, hours=1, minutes=30)
        moved = booking.admin_action(self.module, row["id"], "move", {"start_at": moved_start.isoformat()})
        self.assertEqual(moved["start_at"], moved_start.isoformat())
        self.assertEqual(
            datetime.fromisoformat(moved["end_at"]) - datetime.fromisoformat(moved["start_at"]),
            timedelta(minutes=30),
        )

    def test_admin_move_rejects_occupied_time(self):
        start = self.future_monday()
        first = booking.create_booking(self.module, self.person(start), actor="admin")
        occupied = start + timedelta(hours=1)
        booking.create_booking(
            self.module,
            self.person(occupied, device="device-identifier-0002"),
            actor="admin",
        )
        with self.assertRaisesRegex(ValueError, "уже занято"):
            booking.admin_action(self.module, first["id"], "move", {"start_at": occupied.isoformat()})

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
