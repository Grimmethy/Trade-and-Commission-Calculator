"""rooms.code must be declared UNIQUE and NOT NULL in the schema from app/db.py.

Written as unittest.TestCase (the repo convention; pytest is not declared). The SCHEMA string is
read statically from app/db.py with ast, because importing app.db requires aiosqlite, which the
system interpreter may not have. The test therefore runs with only the standard library.
"""
import ast
import sqlite3
import unittest
from pathlib import Path

DB_PY = Path(__file__).resolve().parent.parent / "app" / "db.py"


def _load_schema() -> str:
    tree = ast.parse(DB_PY.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "SCHEMA" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("SCHEMA constant not found in app/db.py")


class RoomsCodeSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(_load_schema())

    def tearDown(self):
        self.conn.close()

    def test_rooms_table_exists_in_sqlite_master(self):
        row = self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='rooms'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_code_column_is_not_null(self):
        # PRAGMA table_info rows: (cid, name, type, notnull, dflt_value, pk)
        columns = {r[1]: r for r in self.conn.execute("PRAGMA table_info(rooms)")}
        self.assertIn("code", columns)
        self.assertEqual(columns["code"][3], 1)

    def test_code_column_is_unique(self):
        # Method: find a unique index whose only column is `code`. An inline UNIQUE on a column
        # is materialized by SQLite as a unique autoindex, so PRAGMA index_list/index_info catches
        # it without substring-matching the CREATE TABLE text.
        # PRAGMA index_list rows: (seq, name, unique, origin, partial)
        unique_index_columns = []
        for idx in self.conn.execute("PRAGMA index_list(rooms)").fetchall():
            name, is_unique = idx[1], idx[2]
            if is_unique:
                cols = [r[2] for r in self.conn.execute(f'PRAGMA index_info("{name}")')]
                unique_index_columns.append(cols)
        self.assertIn(["code"], unique_index_columns)

    def test_duplicate_code_raises_integrity_error(self):
        self.conn.execute("INSERT INTO rooms (code) VALUES (?)", ("aaaaa",))
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO rooms (code) VALUES (?)", ("aaaaa",))


if __name__ == "__main__":
    unittest.main()
