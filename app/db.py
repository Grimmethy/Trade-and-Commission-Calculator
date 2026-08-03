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

CREATE TABLE IF NOT EXISTS items (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id           INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
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
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
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

CREATE TABLE IF NOT EXISTS inventory_items (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    sku                TEXT UNIQUE NOT NULL,
    name               TEXT NOT NULL,
    ip                 TEXT,
    faction            TEXT,
    source             TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('catalog','manual')),
    catalog_item_id    INTEGER REFERENCES catalog_items(id),
    box_price          REAL,
    models_per_box     INTEGER,
    qty                INTEGER NOT NULL DEFAULT 1 CHECK (qty >= 0),
    condition          TEXT NOT NULL DEFAULT 'assembled'
                         CHECK (condition IN ('needs_repair','assembled','partial_paint','showcase')),
    third_party_price  REAL,
    sp_min             REAL,
    sp_max             REAL,
    sell_price         REAL,
    date_sold          TEXT,
    status             TEXT NOT NULL DEFAULT 'in_stock'
                         CHECK (status IN ('in_stock','listed','sold','archived')),
    notes              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS inventory_photos (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_item_id  INTEGER NOT NULL REFERENCES inventory_items(id) ON DELETE CASCADE,
    filename           TEXT NOT NULL,
    original_filename  TEXT,
    content_type       TEXT,
    is_primary         INTEGER NOT NULL DEFAULT 0,
    sort_order         INTEGER NOT NULL DEFAULT 0,
    uploaded_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_items_room ON items(room_id);
CREATE INDEX IF NOT EXISTS idx_catalog_items_name ON catalog_items(item_name);
CREATE INDEX IF NOT EXISTS idx_catalog_items_ip_faction ON catalog_items(ip, faction);
CREATE INDEX IF NOT EXISTS idx_inventory_items_status ON inventory_items(status);
CREATE INDEX IF NOT EXISTS idx_inventory_items_catalog_item ON inventory_items(catalog_item_id);
CREATE INDEX IF NOT EXISTS idx_inventory_photos_item ON inventory_photos(inventory_item_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_photos_one_primary
    ON inventory_photos(inventory_item_id) WHERE is_primary = 1;
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


async def update_row(table: str, row_id: int, fields: dict, touch_updated_at: bool = False) -> None:
    """The one place an UPDATE gets built. `fields` is exactly what gets
    written — callers decide what belongs in it, including when None is a
    real value to persist (e.g. clearing commission_side), not a "leave
    unchanged" sentinel. Skipping a key entirely is how a caller says "don't
    touch this column"."""
    if not fields and not touch_updated_at:
        return
    set_clauses = [f"{column} = ?" for column in fields]
    values = list(fields.values())
    if touch_updated_at:
        set_clauses.append("updated_at = datetime('now')")
    values.append(row_id)
    db = get_db()
    await db.execute(f"UPDATE {table} SET {', '.join(set_clauses)} WHERE id = ?", values)
    await db.commit()


@asynccontextmanager
async def lifespan(app):
    await init_db()
    try:
        yield
    finally:
        await close_db()
