import re
import secrets
import string

from app.db import get_db, update_row as _update_row
from app.models import Item, Room

ALPHABET = string.ascii_lowercase + string.digits
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    slug = _SLUG_RE.sub("-", text.strip().lower()).strip("-")
    return slug


async def create_room() -> Room:
    db = get_db()
    for _ in range(10):
        code = "".join(secrets.choice(ALPHABET) for _ in range(5))
        try:
            cursor = await db.execute(
                "INSERT INTO rooms (code) VALUES (?)", (code,)
            )
            await db.commit()
            return Room(
                id=cursor.lastrowid,
                code=code,
                label_a="Side A",
                label_b="Side B",
                cash_a=0,
                cash_b=0,
            )
        except Exception as exc:
            if "UNIQUE" in str(exc):
                continue
            raise
    raise RuntimeError("Could not generate a unique room code after 10 attempts")


def _room_from_row(row, items: list[Item]) -> Room:
    return Room(
        id=row["id"],
        code=row["code"],
        label_a=row["label_a"],
        label_b=row["label_b"],
        cash_a=row["cash_a"],
        cash_b=row["cash_b"],
        trade_venue=row["trade_venue"],
        in_person_differential=row["in_person_differential"],
        online_differential=row["online_differential"],
        commission_side=row["commission_side"],
        commission_type=row["commission_type"],
        commission_rate=row["commission_rate"],
        commission_base=row["commission_base"],
        commission_flat_amount=row["commission_flat_amount"],
        items=items,
    )


async def _load_items(room_id: int) -> list[Item]:
    db = get_db()
    item_rows = await (
        await db.execute(
            "SELECT * FROM items WHERE room_id = ? ORDER BY sort_order, id",
            (room_id,),
        )
    ).fetchall()
    return [
        Item(
            id=r["id"],
            side=r["side"],
            name=r["name"],
            qty=r["qty"],
            unit_price=r["unit_price"],
            source=r["source"],
            catalog_item_id=r["catalog_item_id"],
            box_price=r["box_price"],
            models_per_box=r["models_per_box"],
            condition=r["condition"],
        )
        for r in item_rows
    ]


async def get_room(code: str) -> Room | None:
    db = get_db()
    row = await (
        await db.execute("SELECT * FROM rooms WHERE code = ?", (code,))
    ).fetchone()
    if row is None:
        return None
    return _room_from_row(row, await _load_items(row["id"]))


async def get_room_by_id(room_id: int) -> Room | None:
    db = get_db()
    row = await (
        await db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,))
    ).fetchone()
    if row is None:
        return None
    return _room_from_row(row, await _load_items(room_id))


async def list_rooms() -> list[dict]:
    """Summary of every past room, newest first — the trade history list."""
    db = get_db()
    rows = await (
        await db.execute(
            """
            SELECT r.code, r.label_a, r.label_b, r.created_at, r.updated_at,
                   COUNT(i.id) AS item_count,
                   COALESCE(SUM(CASE WHEN i.side = 'A' THEN i.qty * i.unit_price ELSE 0 END), 0) AS total_a,
                   COALESCE(SUM(CASE WHEN i.side = 'B' THEN i.qty * i.unit_price ELSE 0 END), 0) AS total_b
            FROM rooms r
            LEFT JOIN items i ON i.room_id = r.id
            GROUP BY r.id
            ORDER BY r.updated_at DESC
            """
        )
    ).fetchall()
    return [dict(r) for r in rows]


async def set_cash(room_id: int, side: str, amount: float) -> None:
    column = "cash_a" if side == "A" else "cash_b"
    await _update_row("rooms", room_id, {column: amount}, touch_updated_at=True)


async def _unique_code_for_slug(db, base_slug: str, row_id: int, table: str = "rooms") -> str:
    candidate = base_slug
    suffix = 2
    while True:
        row = await (
            await db.execute(
                f"SELECT id FROM {table} WHERE code = ? AND id != ?", (candidate, row_id)
            )
        ).fetchone()
        if row is None:
            return candidate
        candidate = f"{base_slug}-{suffix}"
        suffix += 1


async def rename_side(room_id: int, side: str, label: str) -> None:
    """Renaming Side B also renames the room's actual code/URL to match
    (slugified, collision-suffixed) — Side A's name never affects the code."""
    column = "label_a" if side == "A" else "label_b"
    fields = {column: label}

    if side == "B":
        base_slug = slugify(label)
        if base_slug:
            fields["code"] = await _unique_code_for_slug(get_db(), base_slug, room_id)

    await _update_row("rooms", room_id, fields, touch_updated_at=True)


async def rename_room_code(room_id: int, new_name: str) -> str | None:
    """Directly renames a room's code/URL, independent of Side A/B labels.
    Returns the actual new code (collision-suffixed if needed), or None if
    the given name slugifies to nothing usable."""
    base_slug = slugify(new_name)
    if not base_slug:
        return None
    new_code = await _unique_code_for_slug(get_db(), base_slug, room_id)
    await _update_row("rooms", room_id, {"code": new_code}, touch_updated_at=True)
    return new_code


async def set_venue(
    room_id: int,
    venue: str,
    in_person_differential: float | None = None,
    online_differential: float | None = None,
) -> None:
    fields = {"trade_venue": venue}
    if in_person_differential is not None:
        fields["in_person_differential"] = in_person_differential
    if online_differential is not None:
        fields["online_differential"] = online_differential
    await _update_row("rooms", room_id, fields, touch_updated_at=True)


async def set_commission(
    room_id: int,
    side: str | None,
    commission_type: str,
    rate: float | None = None,
    base: float | None = None,
    flat_amount: float | None = None,
) -> None:
    # commission_side is always written, even when None — clearing the
    # commission is a real, meaningful value here, not "leave unchanged".
    fields = {"commission_side": side, "commission_type": commission_type}
    if rate is not None:
        fields["commission_rate"] = rate
    if base is not None:
        fields["commission_base"] = base
    if flat_amount is not None:
        fields["commission_flat_amount"] = flat_amount
    await _update_row("rooms", room_id, fields, touch_updated_at=True)


async def add_item(
    room_id: int,
    side: str,
    name: str,
    qty: int,
    unit_price: float,
    source: str,
    catalog_item_id: int | None = None,
    box_price: float | None = None,
    models_per_box: int | None = None,
    condition: str = "assembled",
) -> int:
    db = get_db()
    cursor = await db.execute(
        """
        INSERT INTO items
            (room_id, side, name, qty, unit_price, source, catalog_item_id, box_price, models_per_box, condition)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (room_id, side, name, qty, unit_price, source, catalog_item_id, box_price, models_per_box, condition),
    )
    await _update_row("rooms", room_id, {}, touch_updated_at=True)  # also commits the INSERT above
    return cursor.lastrowid


async def get_item(item_id: int) -> dict | None:
    db = get_db()
    row = await (
        await db.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    ).fetchone()
    return dict(row) if row else None


async def edit_item(
    item_id: int,
    qty: int | None = None,
    unit_price: float | None = None,
    name: str | None = None,
    condition: str | None = None,
) -> None:
    fields = {}
    if qty is not None:
        fields["qty"] = qty
    if unit_price is not None:
        fields["unit_price"] = unit_price
    if name is not None:
        fields["name"] = name
    if condition is not None:
        fields["condition"] = condition
    await _update_row("items", item_id, fields)


async def remove_item(item_id: int) -> None:
    db = get_db()
    await db.execute("DELETE FROM items WHERE id = ?", (item_id,))
    await db.commit()


async def remove_room(code: str) -> bool:
    """Deletes a room and its items (cascade). Returns False if no such room."""
    db = get_db()
    cursor = await db.execute("DELETE FROM rooms WHERE code = ?", (code,))
    await db.commit()
    return cursor.rowcount > 0


async def get_room_id_for_item(item_id: int) -> int | None:
    db = get_db()
    row = await (
        await db.execute("SELECT room_id FROM items WHERE id = ?", (item_id,))
    ).fetchone()
    return row["room_id"] if row else None
