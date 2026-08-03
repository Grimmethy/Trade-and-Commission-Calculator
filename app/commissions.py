import secrets

from app.db import get_db
from app.models import Commission, Item
from app.rooms import ALPHABET, _unique_code_for_slug, _update_row, slugify


async def create_commission(painter_name: str) -> Commission:
    db = get_db()
    for _ in range(10):
        code = "".join(secrets.choice(ALPHABET) for _ in range(5))
        try:
            cursor = await db.execute(
                "INSERT INTO commissions (code, painter_name) VALUES (?, ?)", (code, painter_name)
            )
            await db.commit()
            return Commission(
                id=cursor.lastrowid,
                code=code,
                painter_name=painter_name,
                status="submitted",
                commission_rate=0.40,
                cash_amount=0,
            )
        except Exception as exc:
            if "UNIQUE" in str(exc):
                continue
            raise
    raise RuntimeError("Could not generate a unique commission code after 10 attempts")


async def get_commission(code: str) -> Commission | None:
    db = get_db()
    row = await (await db.execute("SELECT * FROM commissions WHERE code = ?", (code,))).fetchone()
    if row is None:
        return None
    item_rows = await (
        await db.execute("SELECT * FROM items WHERE commission_id = ? ORDER BY sort_order, id", (row["id"],))
    ).fetchall()
    items = [
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
            verified=bool(r["verified"]),
            verify_note=r["verify_note"],
        )
        for r in item_rows
    ]
    return Commission(
        id=row["id"],
        code=row["code"],
        painter_name=row["painter_name"],
        status=row["status"],
        commission_rate=row["commission_rate"],
        cash_amount=row["cash_amount"],
        items=items,
    )


async def list_commissions() -> list[dict]:
    db = get_db()
    rows = await (
        await db.execute(
            """
            SELECT c.code, c.painter_name, c.status, c.commission_rate, c.cash_amount,
                   c.created_at, c.updated_at, COUNT(i.id) AS item_count
            FROM commissions c
            LEFT JOIN items i ON i.commission_id = c.id
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            """
        )
    ).fetchall()
    return [dict(r) for r in rows]


async def add_commission_item(
    commission_id: int,
    side: str,
    name: str,
    qty: int,
    unit_price: float,
    source: str,
    catalog_item_id: int | None = None,
    box_price: float | None = None,
    models_per_box: int | None = None,
) -> int:
    db = get_db()
    cursor = await db.execute(
        """
        INSERT INTO items (commission_id, side, name, qty, unit_price, source, catalog_item_id, box_price, models_per_box)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (commission_id, side, name, qty, unit_price, source, catalog_item_id, box_price, models_per_box),
    )
    await db.execute("UPDATE commissions SET updated_at = datetime('now') WHERE id = ?", (commission_id,))
    await db.commit()
    return cursor.lastrowid


async def remove_commission_item(item_id: int) -> None:
    db = get_db()
    await db.execute("DELETE FROM items WHERE id = ?", (item_id,))
    await db.commit()


async def set_item_verification(item_id: int, verified: bool, note: str | None) -> None:
    await _update_row("items", item_id, {"verified": int(verified), "verify_note": note})


async def set_commission_status(commission_id: int, status: str) -> None:
    await _update_row("commissions", commission_id, {"status": status}, touch_updated_at=True)


async def set_painter_name(commission_id: int, painter_name: str) -> None:
    await _update_row("commissions", commission_id, {"painter_name": painter_name}, touch_updated_at=True)


async def set_commission_rate(commission_id: int, rate: float) -> None:
    await _update_row("commissions", commission_id, {"commission_rate": rate}, touch_updated_at=True)


async def set_cash_amount(commission_id: int, amount: float) -> None:
    await _update_row("commissions", commission_id, {"cash_amount": amount}, touch_updated_at=True)


async def rename_commission_code(commission_id: int, new_name: str) -> str | None:
    """Directly renames a commission's code/URL. Returns the actual new code
    (collision-suffixed if needed), or None if the name slugifies to nothing usable."""
    base_slug = slugify(new_name)
    if not base_slug:
        return None
    new_code = await _unique_code_for_slug(get_db(), base_slug, commission_id, table="commissions")
    await _update_row("commissions", commission_id, {"code": new_code}, touch_updated_at=True)
    return new_code


async def remove_commission(code: str) -> bool:
    db = get_db()
    cursor = await db.execute("DELETE FROM commissions WHERE code = ?", (code,))
    await db.commit()
    return cursor.rowcount > 0
