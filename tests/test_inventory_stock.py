"""Inventory stock link: verified rule, inventory fields on items, same-side qty merge, coverage_gaps logging.

unittest-based (pytest runs these too), with a temp DATABASE_PATH like tests/test_rooms_rename.py."""
import tempfile
import unittest
from unittest import mock

import app.db as db
from app import rooms
from app.routers import inventory_link as il
from app.routers import ws


def _item(msrp=10.0):
    return {"code": "ABC", "name": "Thing", "grade": "A", "status": "in_stock", "quantity": 3,
            "owner": "me", "msrp": msrp, "listed_on": None}


def _detail(*kinds):
    return {"location": "Shelf 1", "msrp_source": "manual",
            "flags": [{"kind": k, "status": "open"} for k in kinds]}


class VerifiedRuleTests(unittest.TestCase):
    def test_needs_photos_only_is_verified(self):
        out = il.project_item(_item(), _detail("needs_photos"))
        self.assertTrue(out["verified"])
        for key in ("flags", "location", "msrp_source", "verified"):
            self.assertIn(key, out)

    def test_each_price_flag_is_not_verified(self):
        for kind in il.PRICE_FLAGS:
            with self.subTest(kind=kind):
                self.assertFalse(il.project_item(_item(), _detail(kind))["verified"])

    def test_missing_msrp_is_not_verified(self):
        self.assertFalse(il.project_item(_item(msrp=None), _detail())["verified"])

    def test_failed_detail_is_not_verified_and_does_not_raise(self):
        self.assertFalse(il.project_item(_item(), None)["verified"])

        def boom(code):
            raise RuntimeError("down")

        out = il.enrich_items([_item()], fetch_detail=boom)
        self.assertFalse(out[0]["verified"])
        with mock.patch.object(il, "_get", side_effect=OSError("down")):
            self.assertIsNone(il._fetch_detail("ABC"))
            self.assertFalse(il.enrich_items([_item()])[0]["verified"])


class InventoryStockDbTests(unittest.IsolatedAsyncioTestCase):
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

    async def _items(self):
        return (await rooms.get_room_by_id(self.room.id)).items

    async def _gap_count(self):
        row = await (await db.get_db().execute("SELECT COUNT(*) AS n FROM coverage_gaps")).fetchone()
        return row["n"]

    def _payload(self, side="A", **kw):
        p = {"side": side, "name": "Thing", "qty": 1, "unit_price": 5.0}
        p.update(kw)
        return p

    async def test_add_item_stores_and_reloads_inventory_fields(self):
        await rooms.add_item(self.room.id, "A", "Thing", 1, 5.0, "manual", inventory_code="ABC", inventory_stock=7)
        await rooms.add_item(self.room.id, "A", "Plain", 1, 5.0, "manual")
        items = await self._items()
        by_name = {i.name: i for i in items}
        self.assertEqual(by_name["Thing"].inventory_code, "ABC")
        self.assertEqual(by_name["Thing"].inventory_stock, 7)
        self.assertIsNone(by_name["Plain"].inventory_code)
        self.assertIsNone(by_name["Plain"].inventory_stock)

    async def test_same_code_same_side_merges_qty_into_one_row(self):
        room = await rooms.get_room_by_id(self.room.id)
        await ws._handle_add_item(room, self._payload(inventory_code="ABC", inventory_stock=5, qty=1))
        await ws._handle_add_item(room, self._payload(inventory_code="ABC", inventory_stock=5, qty=2))
        items = await self._items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].qty, 3)

    async def test_same_code_other_side_makes_second_row(self):
        room = await rooms.get_room_by_id(self.room.id)
        await ws._handle_add_item(room, self._payload("A", inventory_code="ABC", inventory_stock=5))
        await ws._handle_add_item(room, self._payload("B", inventory_code="ABC", inventory_stock=5))
        items = await self._items()
        self.assertEqual(sorted(i.side for i in items), ["A", "B"])
        self.assertIsNone(await rooms.find_item_by_inventory_code(self.room.id, "A", "NOPE"))

    async def test_inventory_add_writes_no_gap_but_manual_add_does(self):
        room = await rooms.get_room_by_id(self.room.id)
        await ws._handle_add_item(room, self._payload(inventory_code="ABC", inventory_stock=5))
        self.assertEqual(await self._gap_count(), 0)
        await ws._handle_add_item(room, self._payload(name="Manual thing"))
        self.assertEqual(await self._gap_count(), 1)


if __name__ == "__main__":
    unittest.main()
