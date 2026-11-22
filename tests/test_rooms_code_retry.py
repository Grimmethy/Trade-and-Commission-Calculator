"""Room-code collision retry: a taken code must be skipped, and exhaustion must raise after 10 attempts.

Written as unittest.IsolatedAsyncioTestCase (same as tests/test_rooms_rename.py) so the review
pipeline's `python -m unittest` run picks it up.
"""
import tempfile
import unittest
from unittest import mock

import app.db as db
from app import rooms
from app.models import Room

SEEDED_CODE = "aaaaa"
FRESH_CODE = "bbbbb"


def _chars(*codes: str) -> list[str]:
    # create_room draws each code as 5 secrets.choice() calls, one character at a time.
    return [c for code in codes for c in code]


class RoomCodeRetryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_path = db.DATABASE_PATH
        db.DATABASE_PATH = f"{self._tmp.name}/t.db"
        await db.init_db()
        conn = rooms.get_db()
        await conn.execute("INSERT INTO rooms (code) VALUES (?)", (SEEDED_CODE,))
        await conn.commit()

    async def asyncTearDown(self):
        await db._db.close()
        db._db = None
        db.DATABASE_PATH = self._old_path
        self._tmp.cleanup()

    async def test_retries_after_collision_and_returns_room(self):
        with mock.patch("app.rooms.secrets.choice", side_effect=_chars(SEEDED_CODE, FRESH_CODE)) as choice:
            result = await rooms.create_room()
        self.assertIsInstance(result, Room)
        self.assertEqual(result.code, FRESH_CODE)
        self.assertEqual(choice.call_count, 10)  # 2 attempts x 5 characters

    async def test_raises_runtime_error_after_exactly_10_collisions(self):
        with mock.patch("app.rooms.secrets.choice", side_effect=_chars(*([SEEDED_CODE] * 10))) as choice:
            with self.assertRaises(RuntimeError):
                await rooms.create_room()
        self.assertEqual(choice.call_count, 50)  # 10 attempts x 5 characters


if __name__ == "__main__":
    unittest.main()
