from fastapi import APIRouter

from app.db import get_db

router = APIRouter()


@router.get("/gaps")
async def list_gaps(include_synced: bool = False):
    db = get_db()
    if include_synced:
        rows = await (await db.execute("SELECT * FROM coverage_gaps ORDER BY created_at DESC")).fetchall()
    else:
        rows = await (
            await db.execute("SELECT * FROM coverage_gaps WHERE synced = 0 ORDER BY created_at DESC")
        ).fetchall()
    return {
        "gaps": [
            {
                "id": r["id"],
                "faction_hint": r["faction_hint"],
                "item_name": r["item_name"],
                "unit_price": r["unit_price"],
                "room_code": r["room_code"],
                "created_at": r["created_at"],
                "synced": bool(r["synced"]),
            }
            for r in rows
        ]
    }


@router.post("/gaps/{gap_id}/mark-synced")
async def mark_synced(gap_id: int):
    db = get_db()
    await db.execute("UPDATE coverage_gaps SET synced = 1 WHERE id = ?", (gap_id,))
    await db.commit()
    return {"ok": True}
