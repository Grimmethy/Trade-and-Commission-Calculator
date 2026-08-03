import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

DATABASE_PATH = os.environ.get("DATABASE_PATH", "trade.db")
CATALOG_SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog_seed.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    code                     TEXT UNIQUE NOT NULL,
    label_a                  TEXT NOT NULL DEFAULT 'Side A',
    label_b                  TEXT NOT NULL DEFAULT 'Side B',
    cash_a                   REAL NOT NULL DEFAULT 0,
    cash_b                   REAL NOT NULL DEFAULT 0,
    trade_venue              TEXT NOT NULL DEFAULT 'direct' CHECK (trade_venue IN ('direct','in_person','online')),
    in_person_differential   REAL NOT NULL DEFAULT 0.20,
    online_differential      REAL NOT NULL DEFAULT 0.40,
    commission_side          TEXT CHECK (commission_side IN ('A','B')),
    commission_type          TEXT NOT NULL DEFAULT 'percentage' CHECK (commission_type IN ('percentage','flat')),
    commission_rate          REAL NOT NULL DEFAULT 0.40,
    commission_base          REAL NOT NULL DEFAULT 0,
    commission_flat_amount   REAL NOT NULL DEFAULT 0,
    created_at               TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at               TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS catalog_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ip            TEXT NOT NULL,
    faction       TEXT NOT NULL,
    item_name     TEXT NOT NULL,
    box_price     REAL NOT NULL,
    website_link  TEXT,
    image_url     TEXT,
    source_file   TEXT NOT NULL,
    imported_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(ip, faction, item_name)
);

CREATE TABLE IF NOT EXISTS catalog_overlay (
    catalog_item_id  INTEGER PRIMARY KEY REFERENCES catalog_items(id) ON DELETE CASCADE,
    models_per_box   INTEGER NOT NULL,
    notes            TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS commissions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    code              TEXT UNIQUE NOT NULL,
    painter_name      TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted','returned','verified')),
    commission_rate   REAL NOT NULL DEFAULT 0.40,
    cash_amount       REAL NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Shared by trades (room_id set) and painting commissions (commission_id set) --
-- side A/B means different things per owner: trade counterparty vs. submitted-for-
-- painting/payment-goods. Exactly one owner column is set per row (see CHECK below).
CREATE TABLE IF NOT EXISTS items (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id           INTEGER REFERENCES rooms(id) ON DELETE CASCADE,
    commission_id     INTEGER REFERENCES commissions(id) ON DELETE CASCADE,
    side              TEXT NOT NULL CHECK (side IN ('A','B')),
    name              TEXT NOT NULL,
    qty               INTEGER NOT NULL DEFAULT 1,
    unit_price        REAL NOT NULL,
    source            TEXT NOT NULL CHECK (source IN ('catalog','manual')),
    catalog_item_id   INTEGER REFERENCES catalog_items(id),
    box_price         REAL,
    models_per_box    INTEGER,
    condition         TEXT NOT NULL DEFAULT 'assembled'
                        CHECK (condition IN ('needs_repair','assembled','partial_paint','showcase')),
    sort_order        INTEGER NOT NULL DEFAULT 0,
    verified          INTEGER NOT NULL DEFAULT 0,
    verify_note       TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK ((room_id IS NOT NULL) + (commission_id IS NOT NULL) = 1)
);

CREATE TABLE IF NOT EXISTS coverage_gaps (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    faction_hint  TEXT,
    item_name     TEXT NOT NULL,
    unit_price    REAL,
    room_code     TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    synced        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS kit_size_gaps (
    catalog_item_id  INTEGER PRIMARY KEY REFERENCES catalog_items(id) ON DELETE CASCADE,
    times_selected   INTEGER NOT NULL DEFAULT 1,
    first_seen_at    TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_items_room ON items(room_id);
CREATE INDEX IF NOT EXISTS idx_catalog_items_name ON catalog_items(item_name);
CREATE INDEX IF NOT EXISTS idx_catalog_items_ip_faction ON catalog_items(ip, faction);
"""

_db: aiosqlite.Connection | None = None


async def init_db() -> None:
    global _db
    _db = await aiosqlite.connect(DATABASE_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA foreign_keys = ON")
    await _db.executescript(SCHEMA)
    await _db.commit()
    await _migrate_existing_columns()
    await _migrate_items_table_for_commissions()
    await _load_seed_if_empty()


async def _migrate_existing_columns() -> None:
    """CREATE TABLE IF NOT EXISTS is a no-op on a database that already has these
    tables from before a column was added — ALTER TABLE the columns in by hand
    for anyone with an existing trade.db on disk."""
    migrations = [
        ("items", "condition", "TEXT NOT NULL DEFAULT 'assembled'"),
        ("rooms", "trade_venue", "TEXT NOT NULL DEFAULT 'direct'"),
        ("rooms", "in_person_differential", "REAL NOT NULL DEFAULT 0.20"),
        ("rooms", "online_differential", "REAL NOT NULL DEFAULT 0.40"),
        ("rooms", "commission_side", "TEXT"),
        ("rooms", "commission_type", "TEXT NOT NULL DEFAULT 'percentage'"),
        ("rooms", "commission_rate", "REAL NOT NULL DEFAULT 0.40"),
        ("rooms", "commission_base", "REAL NOT NULL DEFAULT 0"),
        ("rooms", "commission_flat_amount", "REAL NOT NULL DEFAULT 0"),
    ]
    for table, column, ddl in migrations:
        existing = await (await _db.execute(f"PRAGMA table_info({table})")).fetchall()
        if column not in {row["name"] for row in existing}:
            await _db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    await _db.commit()


async def _migrate_items_table_for_commissions() -> None:
    """SQLite can't ALTER a NOT NULL constraint away, so making room_id nullable
    (to allow commission-only items with no room) needs the standard SQLite
    rebuild-and-swap procedure, not a plain ALTER TABLE ADD COLUMN. Guarded by
    checking room_id's notnull flag — a fresh DB already gets the final shape
    from SCHEMA above, so this is a no-op there."""
    info = await (await _db.execute("PRAGMA table_info(items)")).fetchall()
    room_id_col = next(row for row in info if row["name"] == "room_id")
    if room_id_col["notnull"] == 0:
        return

    await _db.execute("PRAGMA foreign_keys = OFF")
    await _db.execute(
        """
        CREATE TABLE items_new (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id           INTEGER REFERENCES rooms(id) ON DELETE CASCADE,
            commission_id     INTEGER REFERENCES commissions(id) ON DELETE CASCADE,
            side              TEXT NOT NULL CHECK (side IN ('A','B')),
            name              TEXT NOT NULL,
            qty               INTEGER NOT NULL DEFAULT 1,
            unit_price        REAL NOT NULL,
            source            TEXT NOT NULL CHECK (source IN ('catalog','manual')),
            catalog_item_id   INTEGER REFERENCES catalog_items(id),
            box_price         REAL,
            models_per_box    INTEGER,
            condition         TEXT NOT NULL DEFAULT 'assembled'
                                CHECK (condition IN ('needs_repair','assembled','partial_paint','showcase')),
            sort_order        INTEGER NOT NULL DEFAULT 0,
            verified          INTEGER NOT NULL DEFAULT 0,
            verify_note       TEXT,
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK ((room_id IS NOT NULL) + (commission_id IS NOT NULL) = 1)
        )
        """
    )
    await _db.execute(
        """
        INSERT INTO items_new
            (id, room_id, commission_id, side, name, qty, unit_price, source,
             catalog_item_id, box_price, models_per_box, condition, sort_order,
             verified, verify_note, created_at)
        SELECT id, room_id, NULL, side, name, qty, unit_price, source,
               catalog_item_id, box_price, models_per_box, condition, sort_order,
               0, NULL, created_at
        FROM items
        """
    )
    await _db.execute("DROP TABLE items")
    await _db.execute("ALTER TABLE items_new RENAME TO items")
    await _db.execute("CREATE INDEX IF NOT EXISTS idx_items_room ON items(room_id)")
    await _db.execute("CREATE INDEX IF NOT EXISTS idx_items_commission ON items(commission_id)")
    await _db.commit()
    await _db.execute("PRAGMA foreign_keys = ON")


async def _load_seed_if_empty() -> None:
    if not CATALOG_SEED_PATH.exists():
        return
    row = await (await _db.execute("SELECT COUNT(*) AS n FROM catalog_items")).fetchone()
    if row["n"] > 0:
        return
    data = json.loads(CATALOG_SEED_PATH.read_text(encoding="utf-8"))
    for item in data:
        cursor = await _db.execute(
            """
            INSERT INTO catalog_items (ip, faction, item_name, box_price, website_link, image_url, source_file, imported_at)
            VALUES (:ip, :faction, :item_name, :box_price, :website_link, :image_url, :source_file, datetime('now'))
            ON CONFLICT(ip, faction, item_name) DO NOTHING
            """,
            item,
        )
        models_per_box = item.get("models_per_box")
        if models_per_box:
            catalog_item_id = cursor.lastrowid
            if not catalog_item_id:
                row = await (
                    await _db.execute(
                        "SELECT id FROM catalog_items WHERE ip = ? AND faction = ? AND item_name = ?",
                        (item["ip"], item["faction"], item["item_name"]),
                    )
                ).fetchone()
                catalog_item_id = row["id"]
            await _db.execute(
                """
                INSERT INTO catalog_overlay (catalog_item_id, models_per_box, notes, updated_at)
                VALUES (?, ?, 'scraped from warhammer.com', datetime('now'))
                ON CONFLICT(catalog_item_id) DO NOTHING
                """,
                (catalog_item_id, models_per_box),
            )
    await _db.commit()


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Database not initialized — call init_db() first")
    return _db


@asynccontextmanager
async def lifespan(app):
    await init_db()
    try:
        yield
    finally:
        await close_db()
