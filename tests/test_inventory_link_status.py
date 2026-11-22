"""Regression: GET /api/inventory/status must never raise; any failure fetching /api/summary yields {"ok": False, ...}.

unittest.TestCase (pytest runs these too) because the review pipeline's executed verification uses python -m unittest.
The inventory plugin is never contacted: app.routers.inventory_link._get is replaced by a function that raises."""
import importlib
import os
import tempfile
import unittest
from unittest import mock

from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.db as db
from app.routers import inventory_link


def _client(mode):
    with mock.patch.dict(os.environ, {"TRADE_MODE": mode}):
        import app.mode, app.main
        importlib.reload(app.mode)
        importlib.reload(app.main)
        return TestClient(app.main.app)


class InventoryStatusErrorContractTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = db.DATABASE_PATH
        db.DATABASE_PATH = f"{self._tmp.name}/t.db"

    def tearDown(self):
        db.DATABASE_PATH = self._old
        self._tmp.cleanup()

    def _status_with(self, exc):
        def boom(*args, **kwargs):
            raise exc

        with mock.patch.object(inventory_link, "_get", boom):
            with _client("private") as c:
                return c.get("/api/inventory/status")

    def test_connection_error_returns_ok_false(self):
        r = self._status_with(ConnectionError("down"))
        self.assertEqual(r.status_code, 200)
        self.assertIs(r.json()["ok"], False)

    def test_type_error_returns_ok_false(self):
        r = self._status_with(TypeError("bad"))
        self.assertEqual(r.status_code, 200)
        self.assertIs(r.json()["ok"], False)

    def test_http_exception_502_returns_ok_false(self):
        r = self._status_with(HTTPException(502, "bad gateway"))
        self.assertEqual(r.status_code, 200)
        self.assertIs(r.json()["ok"], False)


if __name__ == "__main__":
    unittest.main()
