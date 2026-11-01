"""Pinned links on the home page: read from a JSON file, same-site paths only, missing/broken file means nothing shown.

unittest.TestCase (pytest runs these too) because the review pipeline's executed verification uses python -m unittest."""
import importlib
import json
import os
import tempfile
import unittest
from unittest import mock

from fastapi.testclient import TestClient

import app.db as db
from app import pinned


class LoaderTests(unittest.TestCase):
    def _load(self, content):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "pins.json")
            if content is not None:
                with open(p, "w") as f:
                    f.write(content if isinstance(content, str) else json.dumps(content))
            with mock.patch.dict(os.environ, {"PINNED_LINKS_PATH": p}):
                return pinned.load_pinned_links()

    def test_valid_links_are_returned_trimmed(self):
        self.assertEqual(self._load([{"label": "  Mark 8P  ", "href": "/commissions/abc"}]), [{"label": "Mark 8P", "href": "/commissions/abc"}])

    def test_missing_or_broken_file_means_no_links(self):
        self.assertEqual(self._load(None), [])
        self.assertEqual(self._load("not json"), [])
        self.assertEqual(self._load({"label": "x", "href": "/y"}), [])

    def test_only_same_site_paths_are_accepted(self):
        bad = ["https://evil.example/x", "//evil.example/x", "javascript:alert(1)", "commissions/x", "/a b", "/a\\b", ""]
        self.assertEqual(self._load([{"label": "x", "href": h} for h in bad]), [])

    def test_bad_entries_are_skipped_and_the_count_is_capped(self):
        entries = [{"label": 5, "href": "/a"}, {"href": "/b"}, "text", {"label": "", "href": "/c"}] + [{"label": f"L{i}", "href": f"/ok/{i}"} for i in range(30)]
        got = self._load(entries)
        self.assertEqual(len(got), pinned.MAX_LINKS)
        self.assertEqual(got[0]["href"], "/ok/0")

    def test_long_labels_are_truncated(self):
        self.assertEqual(len(self._load([{"label": "x" * 500, "href": "/a"}])[0]["label"]), pinned.MAX_LABEL)


class HomePageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = db.DATABASE_PATH
        db.DATABASE_PATH = f"{self._tmp.name}/t.db"

    def tearDown(self):
        db.DATABASE_PATH = self._old
        self._tmp.cleanup()

    def _home(self, mode_name, entries):
        p = os.path.join(self._tmp.name, "pins.json")
        with open(p, "w") as f:
            json.dump(entries, f)
        with mock.patch.dict(os.environ, {"TRADE_MODE": mode_name, "PINNED_LINKS_PATH": p}):
            import app.mode, app.main
            importlib.reload(app.mode)
            importlib.reload(app.main)
            with TestClient(app.main.app) as c:
                r = c.get("/")
                self.assertEqual(r.status_code, 200)
                return r.text

    def test_links_show_in_public_and_private_mode_and_are_escaped(self):
        entries = [{"label": "Mark <b>8P</b> job", "href": "/commissions/abc123"}]
        for mode_name in ("public", "private"):
            html = self._home(mode_name, entries)
            self.assertIn('<a href="/commissions/abc123">Mark &lt;b&gt;8P&lt;/b&gt; job</a>', html, mode_name)
            self.assertIn("Pinned", html)

    def test_no_pinned_box_without_links(self):
        self.assertNotIn("Pinned", self._home("public", []))


if __name__ == "__main__":
    unittest.main()
