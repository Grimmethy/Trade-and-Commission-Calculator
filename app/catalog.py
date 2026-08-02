from app.db import get_db
from app.models import CatalogItem


async def list_ips() -> list[str]:
    db = get_db()
    rows = await (
        await db.execute("SELECT DISTINCT ip FROM catalog_items ORDER BY ip")
    ).fetchall()
    return [r["ip"] for r in rows]


async def list_factions(ip: str) -> list[str]:
    db = get_db()
    rows = await (
        await db.execute(
            "SELECT DISTINCT faction FROM catalog_items WHERE ip = ? ORDER BY faction",
            (ip,),
        )
    ).fetchall()
    return [r["faction"] for r in rows]


async def list_units(ip: str, faction: str) -> list[CatalogItem]:
    db = get_db()
    rows = await (
        await db.execute(
            """
            SELECT ci.*, co.models_per_box AS overlay_models_per_box
            FROM catalog_items ci
            LEFT JOIN catalog_overlay co ON co.catalog_item_id = ci.id
            WHERE ci.ip = ? AND ci.faction = ?
            ORDER BY ci.item_name
            """,
            (ip, faction),
        )
    ).fetchall()
    return [_row_to_catalog_item(r) for r in rows]


async def search_catalog(query: str, limit: int = 20) -> list[CatalogItem]:
    db = get_db()
    rows = await (
        await db.execute(
            """
            SELECT ci.*, co.models_per_box AS overlay_models_per_box
            FROM catalog_items ci
            LEFT JOIN catalog_overlay co ON co.catalog_item_id = ci.id
            WHERE ci.item_name LIKE ?
            ORDER BY ci.item_name
            LIMIT ?
            """,
            (f"%{query}%", limit),
        )
    ).fetchall()
    return [_row_to_catalog_item(r) for r in rows]


async def get_catalog_item(catalog_item_id: int) -> CatalogItem | None:
    db = get_db()
    row = await (
        await db.execute(
            """
            SELECT ci.*, co.models_per_box AS overlay_models_per_box
            FROM catalog_items ci
            LEFT JOIN catalog_overlay co ON co.catalog_item_id = ci.id
            WHERE ci.id = ?
            """,
            (catalog_item_id,),
        )
    ).fetchone()
    return _row_to_catalog_item(row) if row else None


async def set_models_per_box(catalog_item_id: int, models_per_box: int) -> None:
    """User-driven correction via the UI. Tagged 'manual override' so a later
    catalog re-import (which only auto-fills rows still tagged 'scraped from
    warhammer.com') never silently clobbers it."""
    db = get_db()
    await db.execute(
        """
        INSERT INTO catalog_overlay (catalog_item_id, models_per_box, notes, updated_at)
        VALUES (?, ?, 'manual override', datetime('now'))
        ON CONFLICT(catalog_item_id) DO UPDATE SET
            models_per_box = excluded.models_per_box,
            notes = 'manual override',
            updated_at = datetime('now')
        """,
        (catalog_item_id, models_per_box),
    )
    await db.commit()


async def log_kit_size_gap(catalog_item_id: int) -> None:
    """Called when someone adds a catalog item that has no known models_per_box.
    Queues it for the next scrape-assisted batch instead of just prompting for
    manual entry — see /catalog/kit-size-gaps."""
    db = get_db()
    await db.execute(
        """
        INSERT INTO kit_size_gaps (catalog_item_id, times_selected, first_seen_at, last_seen_at)
        VALUES (?, 1, datetime('now'), datetime('now'))
        ON CONFLICT(catalog_item_id) DO UPDATE SET
            times_selected = times_selected + 1,
            last_seen_at = datetime('now')
        """,
        (catalog_item_id,),
    )
    await db.commit()


async def list_kit_size_gaps() -> list[dict]:
    """Items someone has tried to trade that still have no kit size — the queue
    for the next browser-assisted scrape pass. Auto-resolves itself: once
    catalog_overlay has a row for an item (scraped or manually set), it drops
    out of this list on its own, no separate 'resolved' bookkeeping needed."""
    db = get_db()
    rows = await (
        await db.execute(
            """
            SELECT ci.id, ci.item_name, ci.faction, ci.ip, ci.website_link,
                   g.times_selected, g.first_seen_at, g.last_seen_at
            FROM kit_size_gaps g
            JOIN catalog_items ci ON ci.id = g.catalog_item_id
            LEFT JOIN catalog_overlay co ON co.catalog_item_id = ci.id
            WHERE co.catalog_item_id IS NULL
            ORDER BY g.times_selected DESC, g.first_seen_at ASC
            """
        )
    ).fetchall()
    return [dict(r) for r in rows]


def _row_to_catalog_item(row) -> CatalogItem:
    return CatalogItem(
        id=row["id"],
        ip=row["ip"],
        faction=row["faction"],
        item_name=row["item_name"],
        box_price=row["box_price"],
        website_link=row["website_link"],
        image_url=row["image_url"],
        models_per_box=row["overlay_models_per_box"],
    )
