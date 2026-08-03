from app.db import get_db, update_row
from app.models import InventoryItem, InventoryPhoto
from app.pricing import compute_sp_range


def _row_to_photo(row) -> InventoryPhoto:
    return InventoryPhoto(
        id=row["id"],
        inventory_item_id=row["inventory_item_id"],
        filename=row["filename"],
        original_filename=row["original_filename"],
        content_type=row["content_type"],
        is_primary=bool(row["is_primary"]),
        sort_order=row["sort_order"],
        uploaded_at=row["uploaded_at"],
    )


def _row_to_item(row, photos: list[InventoryPhoto]) -> InventoryItem:
    return InventoryItem(
        id=row["id"],
        sku=row["sku"],
        name=row["name"],
        ip=row["ip"],
        faction=row["faction"],
        source=row["source"],
        catalog_item_id=row["catalog_item_id"],
        box_price=row["box_price"],
        models_per_box=row["models_per_box"],
        qty=row["qty"],
        condition=row["condition"],
        third_party_price=row["third_party_price"],
        sp_min=row["sp_min"],
        sp_max=row["sp_max"],
        sell_price=row["sell_price"],
        date_sold=row["date_sold"],
        status=row["status"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        photos=photos,
    )


async def list_photos(inventory_item_id: int) -> list[InventoryPhoto]:
    db = get_db()
    rows = await (
        await db.execute(
            "SELECT * FROM inventory_photos WHERE inventory_item_id = ? ORDER BY sort_order, id",
            (inventory_item_id,),
        )
    ).fetchall()
    return [_row_to_photo(r) for r in rows]


async def generate_sku(prefix: str, width: int = 3) -> str:
    """Next unused zero-padded SKU for a prefix, e.g. generate_sku('40KTSC') ->
    '40KTSC-004' if 40KTSC-001..40KTSC-003 already exist. Scans existing SKUs
    with that prefix rather than a separate counter table, so it self-heals if
    rows get deleted instead of drifting out of sync."""
    db = get_db()
    rows = await (
        await db.execute(
            "SELECT sku FROM inventory_items WHERE sku LIKE ? ORDER BY sku",
            (f"{prefix}-%",),
        )
    ).fetchall()
    used = set()
    for r in rows:
        suffix = r["sku"][len(prefix) + 1 :]
        if suffix.isdigit():
            used.add(int(suffix))
    n = 1
    while n in used:
        n += 1
    return f"{prefix}-{n:0{width}d}"


async def create_item(
    sku: str,
    name: str,
    ip: str | None = None,
    faction: str | None = None,
    source: str = "manual",
    catalog_item_id: int | None = None,
    box_price: float | None = None,
    models_per_box: int | None = None,
    qty: int = 1,
    condition: str = "assembled",
    notes: str | None = None,
) -> int:
    db = get_db()
    cursor = await db.execute(
        """
        INSERT INTO inventory_items
            (sku, name, ip, faction, source, catalog_item_id, box_price, models_per_box, qty, condition, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (sku, name, ip, faction, source, catalog_item_id, box_price, models_per_box, qty, condition, notes),
    )
    await db.commit()
    return cursor.lastrowid


async def get_item(item_id: int) -> InventoryItem | None:
    db = get_db()
    row = await (
        await db.execute("SELECT * FROM inventory_items WHERE id = ?", (item_id,))
    ).fetchone()
    if row is None:
        return None
    return _row_to_item(row, await list_photos(item_id))


async def get_item_by_sku(sku: str) -> InventoryItem | None:
    db = get_db()
    row = await (
        await db.execute("SELECT * FROM inventory_items WHERE sku = ?", (sku,))
    ).fetchone()
    if row is None:
        return None
    return _row_to_item(row, await list_photos(row["id"]))


async def list_items(status: str | None = None) -> list[InventoryItem]:
    db = get_db()
    if status:
        rows = await (
            await db.execute(
                "SELECT * FROM inventory_items WHERE status = ? ORDER BY updated_at DESC", (status,)
            )
        ).fetchall()
    else:
        rows = await (
            await db.execute("SELECT * FROM inventory_items ORDER BY updated_at DESC")
        ).fetchall()
    items = []
    for row in rows:
        items.append(_row_to_item(row, await list_photos(row["id"])))
    return items


async def edit_item(
    item_id: int,
    name: str | None = None,
    qty: int | None = None,
    condition: str | None = None,
    notes: str | None = None,
) -> None:
    fields = {}
    if name is not None:
        fields["name"] = name
    if qty is not None:
        fields["qty"] = qty
    if condition is not None:
        fields["condition"] = condition
    if notes is not None:
        fields["notes"] = notes
    await update_row("inventory_items", item_id, fields, touch_updated_at=True)


async def set_pricing(item_id: int, third_party_price: float) -> None:
    sp_min, sp_max = compute_sp_range(third_party_price)
    await update_row(
        "inventory_items",
        item_id,
        {"third_party_price": third_party_price, "sp_min": sp_min, "sp_max": sp_max},
        touch_updated_at=True,
    )


async def set_status(item_id: int, status: str) -> None:
    await update_row("inventory_items", item_id, {"status": status}, touch_updated_at=True)


async def mark_sold(item_id: int, sell_price: float, date_sold: str) -> None:
    await update_row(
        "inventory_items",
        item_id,
        {"status": "sold", "sell_price": sell_price, "date_sold": date_sold},
        touch_updated_at=True,
    )


async def remove_item(item_id: int) -> None:
    db = get_db()
    await db.execute("DELETE FROM inventory_items WHERE id = ?", (item_id,))
    await db.commit()


async def add_photo(
    inventory_item_id: int, filename: str, original_filename: str | None, content_type: str | None
) -> int:
    db = get_db()
    existing = await (
        await db.execute(
            "SELECT COUNT(*) AS n FROM inventory_photos WHERE inventory_item_id = ?",
            (inventory_item_id,),
        )
    ).fetchone()
    is_primary = existing["n"] == 0  # first photo uploaded for an item is automatically primary
    cursor = await db.execute(
        """
        INSERT INTO inventory_photos
            (inventory_item_id, filename, original_filename, content_type, is_primary, sort_order)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (inventory_item_id, filename, original_filename, content_type, int(is_primary), existing["n"]),
    )
    await db.commit()
    return cursor.lastrowid


async def set_primary_photo(inventory_item_id: int, photo_id: int) -> None:
    """Atomically swaps the primary flag — clear the old one and set the new
    one in the same connection before committing, so the partial unique index
    (exactly one is_primary=1 per item) is never violated mid-flight."""
    db = get_db()
    await db.execute(
        "UPDATE inventory_photos SET is_primary = 0 WHERE inventory_item_id = ? AND is_primary = 1",
        (inventory_item_id,),
    )
    await db.execute(
        "UPDATE inventory_photos SET is_primary = 1 WHERE id = ? AND inventory_item_id = ?",
        (photo_id, inventory_item_id),
    )
    await db.commit()


async def get_photo(photo_id: int) -> InventoryPhoto | None:
    db = get_db()
    row = await (
        await db.execute("SELECT * FROM inventory_photos WHERE id = ?", (photo_id,))
    ).fetchone()
    return _row_to_photo(row) if row else None


async def remove_photo(photo_id: int) -> None:
    """Deletes the DB row; if it was primary, auto-promotes the next photo by
    sort_order so an item never silently loses "which photo is the label
    photo" without an explicit re-pick."""
    db = get_db()
    photo = await get_photo(photo_id)
    if photo is None:
        return
    await db.execute("DELETE FROM inventory_photos WHERE id = ?", (photo_id,))
    if photo.is_primary:
        next_photo = await (
            await db.execute(
                "SELECT id FROM inventory_photos WHERE inventory_item_id = ? ORDER BY sort_order, id LIMIT 1",
                (photo.inventory_item_id,),
            )
        ).fetchone()
        if next_photo:
            await db.execute(
                "UPDATE inventory_photos SET is_primary = 1 WHERE id = ?", (next_photo["id"],)
            )
    await db.commit()
