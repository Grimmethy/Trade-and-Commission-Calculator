"""Commission sheet: instant 'Returned' checkbox + note saving, progress count, read-only returned state.

unittest.TestCase (pytest runs these too) because the review pipeline's executed verification uses python -m unittest."""
import importlib
import os
import tempfile
import unittest
from unittest import mock

from fastapi.testclient import TestClient

import app.db as db


def _client(mode):
    with mock.patch.dict(os.environ, {"TRADE_MODE": mode}):
        import app.mode, app.main
        importlib.reload(app.mode)
        importlib.reload(app.main)
        return TestClient(app.main.app)


class CommissionVerifyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = db.DATABASE_PATH
        db.DATABASE_PATH = f"{self._tmp.name}/t.db"

    def tearDown(self):
        db.DATABASE_PATH = self._old
        self._tmp.cleanup()

    def _commission_with_items(self, c, names=("Box A", "Box B")):
        code = c.post("/commissions", data={"painter_name": "Test Painter"}, follow_redirects=False).headers["location"].rsplit("/", 1)[1]
        for n in names:
            r = c.post(f"/commissions/{code}/items", data={"side": "A", "name": n, "qty": 1, "unit_price": 10}, follow_redirects=False)
            self.assertEqual(r.status_code, 303)
        return code

    def _item_ids(self, c, code):
        import re
        html = c.get(f"/commissions/{code}").text
        return [int(x) for x in re.findall(r"/items/(\d+)/verify\"", html)]

    def test_instant_save_returns_progress_and_persists(self):
        with _client("private") as c:
            code = self._commission_with_items(c)
            first, second = self._item_ids(c, code)
            r = c.post(f"/commissions/{code}/items/{first}/verify.json", data={"verified": "true", "note": "  scratched base  "})
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertEqual((body["returned_count"], body["total"], body["note"], body["status"]), (1, 2, "scratched base", "submitted"))
            html = c.get(f"/commissions/{code}").text
            self.assertIn("scratched base", html)
            self.assertIn('<span id="returned-count">1</span> of <span id="returned-total">2</span> returned', html)
            c.post(f"/commissions/{code}/items/{second}/verify.json", data={"verified": "true", "note": ""})
            html = c.get(f"/commissions/{code}").text
            self.assertNotIn('id="mark-returned-form" hidden', html)        # all returned: the button is offered
            r = c.post(f"/commissions/{code}/items/{first}/verify.json", data={"note": "back"})   # checkbox cleared
            self.assertEqual(r.json()["returned_count"], 1)

    def test_item_from_another_commission_is_rejected_on_both_routes(self):
        with _client("private") as c:
            mine = self._commission_with_items(c, ("Mine",))
            other = self._commission_with_items(c, ("Theirs",))
            other_id = self._item_ids(c, other)[0]
            for route in ("verify.json", "verify"):
                r = c.post(f"/commissions/{mine}/items/{other_id}/{route}", data={"verified": "true"}, follow_redirects=False)
                self.assertEqual(r.status_code, 404, route)
            self.assertIn("Not yet", _public_page(self, other))             # untouched

    def test_side_b_payment_items_cannot_be_ticked_returned(self):
        """Only the items sent out for painting (side A) can be marked returned; the goods paid back (side B) cannot."""
        with _client("private") as c:
            code = self._commission_with_items(c, ("Sent out",))
            r = c.post(f"/commissions/{code}/items", data={"side": "B", "name": "Paid in goods", "qty": 1, "unit_price": 20}, follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            html = c.get(f"/commissions/{code}").text
            import re
            side_b_id = max(int(x) for x in re.findall(r"/items/(\d+)/delete", html))
            side_a_id = self._item_ids(c, code)[0]
            self.assertNotEqual(side_a_id, side_b_id)
            for route in ("verify.json", "verify"):
                r = c.post(f"/commissions/{code}/items/{side_b_id}/{route}", data={"verified": "true", "note": "x"}, follow_redirects=False)
                self.assertEqual(r.status_code, 404, route)
            body = c.post(f"/commissions/{code}/items/{side_a_id}/verify.json", data={"verified": "true"}).json()
            self.assertEqual((body["returned_count"], body["total"]), (1, 1))   # the payment line is not counted

    def test_json_route_does_not_exist_publicly(self):
        with _client("private") as c:
            code = self._commission_with_items(c, ("One",))
            item_id = self._item_ids(c, code)[0]
        with _client("public") as p:
            self.assertEqual(p.post(f"/commissions/{code}/items/{item_id}/verify.json", data={"verified": "true"}).status_code, 404)

    def test_public_sheet_shows_returned_state_as_text_without_returned_controls(self):
        with _client("private") as c:
            code = self._commission_with_items(c, ("One", "Two"))
            first = self._item_ids(c, code)[0]
            c.post(f"/commissions/{code}/items/{first}/verify.json", data={"verified": "true", "note": "perfect"})
        html = _public_page(self, code)
        self.assertIn("Returned", html)
        self.assertIn("perfect", html)
        self.assertIn("1</span> of <span id=\"returned-total\">2", html)
        self.assertNotIn("verify-item-form", html)                             # the returned/note controls are not in the public markup at all
        self.assertNotIn('type="checkbox"', html)


def _public_page(test, code):
    with _client("public") as p:
        r = p.get(f"/commissions/{code}")
        test.assertEqual(r.status_code, 200)
        return r.text


if __name__ == "__main__":
    unittest.main()
