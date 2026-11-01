"""Commission sheet: add items from the inventory by code or name.

unittest.TestCase (pytest runs these too) because the review pipeline's executed verification uses python -m unittest.
The inventory plugin is never contacted: app.routers.inventory_link._get is replaced by a fake that filters like the plugin
(substring on code or name, EXACT status match)."""
import importlib
import os
import tempfile
import unittest
import urllib.parse
from unittest import mock

from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.db as db
from app.routers import inventory_link

SHELF = [
    {"code": "GW40KAC031", "name": "Custodian Guard x5", "grade": "boxed", "status": "in_stock", "quantity": 1, "owner": "SGC", "msrp": 76.0, "listed_on": "square $58.50"},
    {"code": "GW40KAC010", "name": "Venerable Land Raider x1", "grade": "boxed", "status": "in_stock", "quantity": 1, "owner": "SGC", "msrp": None, "listed_on": "square $86.40, ebay $90.00"},
    {"code": "GW40KAC999", "name": "No Price Thing", "grade": "boxed", "status": "in_stock", "quantity": 1, "owner": "SGC", "msrp": None, "listed_on": None},
    {"code": "GW40KAC200", "name": "Listed Thing", "grade": "showcase", "status": "listed", "quantity": 1, "owner": "SGC", "msrp": 10.0, "listed_on": "ebay $25.00"},
    {"code": "GW40KAC300", "name": "Sold Thing", "grade": "boxed", "status": "sold", "quantity": 0, "owner": "SGC", "msrp": 10.0, "listed_on": None},
]


def fake_get(path):
    """Mimic the plugin: GET /api/items?q=&status=&limit=."""
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(path).query))
    q = query.get("q", "").lower()
    rows = [i for i in SHELF if (not q or q in i["code"].lower() or q in i["name"].lower()) and i["status"] == query.get("status", i["status"])]
    return {"total": len(rows), "items": rows[: int(query.get("limit", 100))]}


def _client(mode):
    with mock.patch.dict(os.environ, {"TRADE_MODE": mode}):
        import app.mode, app.main
        importlib.reload(app.mode)
        importlib.reload(app.main)
        return TestClient(app.main.app)


class BridgeTests(unittest.TestCase):
    def test_any_status_merges_in_stock_and_listed_and_never_sold(self):
        with mock.patch.object(inventory_link, "_get", fake_get):
            codes = [i["code"] for i in inventory_link.search_stock("GW40KAC", "any", 50)["items"]]
        self.assertEqual(codes, ["GW40KAC010", "GW40KAC031", "GW40KAC200", "GW40KAC999"])

    def test_default_status_is_still_in_stock_only(self):
        with mock.patch.object(inventory_link, "_get", fake_get):
            codes = [i["code"] for i in inventory_link.search_stock("GW40KAC", "in_stock", 50)["items"]]
        self.assertNotIn("GW40KAC200", codes)

    def test_limit_applies_after_the_merge(self):
        with mock.patch.object(inventory_link, "_get", fake_get):
            self.assertEqual(len(inventory_link.search_stock("GW40KAC", "any", 2)["items"]), 2)

    def test_listed_price_parsing(self):
        self.assertEqual(inventory_link.listed_price("square $58.50, ebay $60.00"), 58.5)
        self.assertEqual(inventory_link.listed_price("ebay $25"), 25.0)
        self.assertIsNone(inventory_link.listed_price(None))
        self.assertIsNone(inventory_link.listed_price("not listed"))


class ByInventoryRouteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = db.DATABASE_PATH
        db.DATABASE_PATH = f"{self._tmp.name}/t.db"
        self._patch = mock.patch.object(inventory_link, "_get", fake_get)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        db.DATABASE_PATH = self._old
        self._tmp.cleanup()

    def _new_commission(self, c):
        return c.post("/commissions", data={"painter_name": "Test"}, follow_redirects=False).headers["location"].rsplit("/", 1)[1]

    def _add(self, c, code, inv):
        return c.post(f"/commissions/{code}/items/by-inventory", data={"inventory_code": inv})

    def test_adds_the_box_named_with_its_code_at_msrp_not_the_listed_price(self):
        with _client("private") as c:
            code = self._new_commission(c)
            r = self._add(c, code, "gw40kac031")                       # case-insensitive
            self.assertEqual(r.status_code, 200)
            self.assertEqual((r.json()["name"], r.json()["unit_price"], r.json()["price_basis"]), ("GW40KAC031 Custodian Guard x5", 76.0, "msrp"))
            html = c.get(f"/commissions/{code}").text
            self.assertIn("GW40KAC031 Custodian Guard x5", html)
            self.assertIn("$76.00", html)

    def test_falls_back_to_the_first_listed_price_when_there_is_no_msrp(self):
        with _client("private") as c:
            code = self._new_commission(c)
            r = self._add(c, code, "GW40KAC010")
            self.assertEqual((r.status_code, r.json()["unit_price"], r.json()["price_basis"]), (200, 86.4, "listed"))

    def test_listed_status_items_can_be_added(self):
        with _client("private") as c:
            self.assertEqual(self._add(c, self._new_commission(c), "GW40KAC200").status_code, 200)

    def test_the_same_code_twice_is_refused(self):
        with _client("private") as c:
            code = self._new_commission(c)
            self.assertEqual(self._add(c, code, "GW40KAC031").status_code, 200)
            self.assertEqual(self._add(c, code, "GW40KAC031").status_code, 409)
            self.assertEqual(c.get(f"/commissions/{code}").text.count('class="item-name">GW40KAC031 Custodian Guard x5'), 1)   # exactly one row

    def test_unknown_sold_priceless_and_unreachable_cases(self):
        with _client("private") as c:
            code = self._new_commission(c)
            self.assertEqual(self._add(c, code, "NOPE123").status_code, 404)
            self.assertEqual(self._add(c, code, "GW40KAC300").status_code, 404)        # sold: not on the shelf
            self.assertEqual(self._add(c, code, "GW40KAC999").status_code, 422)        # no msrp, no listed price
            with mock.patch.object(inventory_link, "_get", side_effect=HTTPException(502, "inventory plugin not reachable")):
                self.assertEqual(self._add(c, code, "GW40KAC031").status_code, 502)
            self.assertEqual(self._add(c, "nosuchcode", "GW40KAC031").status_code, 404)

    def test_private_page_has_the_search_box_and_public_page_and_route_do_not(self):
        with _client("private") as c:
            code = self._new_commission(c)
            self.assertIn('id="inventory-search"', c.get(f"/commissions/{code}").text)
        with _client("public") as p:
            self.assertNotIn("inventory-search", p.get(f"/commissions/{code}").text)
            self.assertEqual(self._add(p, code, "GW40KAC031").status_code, 404)


if __name__ == "__main__":
    unittest.main()
