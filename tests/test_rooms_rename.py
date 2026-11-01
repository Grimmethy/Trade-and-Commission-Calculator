"""Renaming a side must never move the room's URL; the explicit code rename refuses guessable defaults.

Written as unittest.TestCase (pytest runs these too) because the review pipeline's executed verification
runs Python tests with `python -m unittest`, which finds nothing in plain pytest functions."""
import tempfile
import unittest

import app.db as db
from app import rooms


class RoomRenameTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_path = db.DATABASE_PATH
        db.DATABASE_PATH = f"{self._tmp.name}/t.db"
        await db.init_db()
        self.room = await rooms.create_room()

    async def asyncTearDown(self):
        await db._db.close()
        db._db = None
        db.DATABASE_PATH = self._old_path
        self._tmp.cleanup()

    async def test_renaming_a_side_never_changes_the_room_code(self):
        await rooms.rename_side(self.room.id, "B", "Alice")
        await rooms.rename_side(self.room.id, "A", "Bob")
        again = await rooms.get_room(self.room.code)          # the original code must still resolve
        self.assertIsNotNone(again)
        self.assertEqual(again.code, self.room.code)
        self.assertEqual((again.label_a, again.label_b), ("Bob", "Alice"))

    async def test_renaming_side_b_to_its_default_text_keeps_the_code(self):
        await rooms.rename_side(self.room.id, "B", "Side B")   # what the old blur handler sent on a plain Tab
        again = await rooms.get_room(self.room.code)
        self.assertIsNotNone(again)
        self.assertEqual(again.code, self.room.code)

    async def test_explicit_rename_refuses_guessable_defaults(self):
        for name in ("Side B", "side-a", "SIDE B"):
            with self.subTest(name=name):
                self.assertIsNone(await rooms.rename_room_code(self.room.id, name))
                again = await rooms.get_room(self.room.code)
                self.assertIsNotNone(again)
                self.assertEqual(again.code, self.room.code)

    async def test_explicit_rename_still_works_for_a_normal_name(self):
        self.assertEqual(await rooms.rename_room_code(self.room.id, "My Trade"), "my-trade")


if __name__ == "__main__":
    unittest.main()
