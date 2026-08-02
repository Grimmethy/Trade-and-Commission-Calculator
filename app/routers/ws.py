from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from app import catalog as catalog_service
from app import rooms as rooms_service
from app.db import get_db
from app.pricing import (
    CONDITION_MULTIPLIERS,
    DEFAULT_CONDITION,
    apply_condition,
    compute_totals,
    derive_per_model_price,
    rebaseline_condition,
)
from app.websocket_manager import manager

router = APIRouter()


async def _log_coverage_gap(room_code: str, faction_hint: str | None, item_name: str, unit_price: float) -> None:
    db = get_db()
    await db.execute(
        "INSERT INTO coverage_gaps (faction_hint, item_name, unit_price, room_code) VALUES (?, ?, ?, ?)",
        (faction_hint, item_name, unit_price, room_code),
    )
    await db.commit()


def _serialize_state(room) -> dict:
    totals = compute_totals(room)
    return jsonable_encoder(
        {
            "type": "full_state",
            "payload": {
                "room": room.to_dict(),
                "items": [i.to_dict() for i in room.items],
                "totals": {
                    "side_a": totals.total_a,
                    "side_b": totals.total_b,
                    "venue_multiplier": totals.venue_multiplier,
                    "commission_amount": totals.commission_amount,
                    "effective_side_a": totals.effective_side_a,
                    "effective_side_b": totals.effective_side_b,
                    "diff": totals.diff,
                    "suggested_topup_side": totals.suggested_topup_side,
                    "suggested_topup_amount": totals.suggested_topup_amount,
                },
            },
        }
    )


async def _broadcast_state(room_id: int) -> None:
    room = await rooms_service.get_room_by_id(room_id)
    await manager.broadcast(room_id, _serialize_state(room))


@router.websocket("/ws/{room_code}")
async def trade_ws(websocket: WebSocket, room_code: str):
    room = await rooms_service.get_room(room_code)
    if room is None:
        await websocket.close(code=4404)
        return

    room_id = room.id  # stable for the life of this connection, even if the code (Side B's name) changes
    await manager.connect(room_id, websocket)
    await manager.send_to(websocket, _serialize_state(room))

    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")
            payload = message.get("payload", {})

            try:
                await _handle_message(room_id, msg_type, payload)
                await _broadcast_state(room_id)
            except ValueError as exc:
                await manager.send_to(websocket, {"type": "error", "payload": {"message": str(exc)}})
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)


async def _handle_message(room_id: int, msg_type: str, payload: dict) -> None:
    room = await rooms_service.get_room_by_id(room_id)
    if room is None:
        raise ValueError("Room no longer exists")

    if msg_type == "add_item":
        await _handle_add_item(room, payload)
    elif msg_type == "edit_item":
        await _handle_edit_item(payload)
    elif msg_type == "remove_item":
        item_id = payload.get("item_id")
        if item_id is None:
            raise ValueError("item_id is required")
        await rooms_service.remove_item(item_id)
    elif msg_type == "set_cash":
        side = payload.get("side")
        amount = payload.get("amount")
        if side not in ("A", "B") or amount is None:
            raise ValueError("side ('A'/'B') and amount are required")
        await rooms_service.set_cash(room.id, side, float(amount))
    elif msg_type == "rename_side":
        side = payload.get("side")
        label = payload.get("label")
        if side not in ("A", "B") or not label:
            raise ValueError("side ('A'/'B') and label are required")
        await rooms_service.rename_side(room.id, side, label)
    elif msg_type == "set_venue":
        await _handle_set_venue(room, payload)
    elif msg_type == "set_commission":
        await _handle_set_commission(room, payload)
    else:
        raise ValueError(f"Unknown message type: {msg_type}")


async def _handle_set_venue(room, payload: dict) -> None:
    venue = payload.get("venue")
    if venue not in ("direct", "in_person", "online"):
        raise ValueError("venue must be 'direct', 'in_person', or 'online'")

    in_person_differential = payload.get("in_person_differential")
    online_differential = payload.get("online_differential")
    if in_person_differential is not None:
        in_person_differential = float(in_person_differential)
        if not (0 <= in_person_differential <= 1):
            raise ValueError("in_person_differential must be between 0 and 1")
    if online_differential is not None:
        online_differential = float(online_differential)
        if not (0 <= online_differential <= 1):
            raise ValueError("online_differential must be between 0 and 1")

    await rooms_service.set_venue(room.id, venue, in_person_differential, online_differential)


async def _handle_set_commission(room, payload: dict) -> None:
    side = payload.get("side")  # 'A', 'B', or None to clear the commission
    commission_type = payload.get("commission_type", "percentage")

    if side is not None and side not in ("A", "B"):
        raise ValueError("side must be 'A', 'B', or null")
    if commission_type not in ("percentage", "flat"):
        raise ValueError("commission_type must be 'percentage' or 'flat'")

    rate = payload.get("rate")
    base = payload.get("base")
    flat_amount = payload.get("flat_amount")
    if rate is not None:
        rate = float(rate)
        if rate < 0:
            raise ValueError("rate must be non-negative")
    if base is not None:
        base = float(base)
        if base < 0:
            raise ValueError("base must be non-negative")
    if flat_amount is not None:
        flat_amount = float(flat_amount)
        if flat_amount < 0:
            raise ValueError("flat_amount must be non-negative")

    await rooms_service.set_commission(room.id, side, commission_type, rate, base, flat_amount)


async def _handle_add_item(room, payload: dict) -> None:
    side = payload.get("side")
    name = payload.get("name")
    qty = payload.get("qty", 1)
    source = payload.get("source", "manual")
    catalog_item_id = payload.get("catalog_item_id")
    unit_price = payload.get("unit_price")
    condition = payload.get("condition", DEFAULT_CONDITION)

    if side not in ("A", "B"):
        raise ValueError("side must be 'A' or 'B'")
    if not name:
        raise ValueError("name is required")
    if condition not in CONDITION_MULTIPLIERS:
        raise ValueError(f"condition must be one of {list(CONDITION_MULTIPLIERS)}")
    try:
        qty = int(qty)
    except (TypeError, ValueError):
        raise ValueError("qty must be an integer")
    if qty <= 0:
        raise ValueError("qty must be positive")

    box_price = None
    models_per_box = None

    if source == "catalog" and catalog_item_id is not None:
        catalog_item = await catalog_service.get_catalog_item(int(catalog_item_id))
        if catalog_item is None:
            raise ValueError("Catalog item not found")
        box_price = catalog_item.box_price
        models_per_box = catalog_item.models_per_box
        if unit_price is None:
            if models_per_box:
                unit_price = derive_per_model_price(box_price, models_per_box)
            else:
                unit_price = box_price
        if not models_per_box:
            await catalog_service.log_kit_size_gap(catalog_item.id)
    else:
        source = "manual"
        catalog_item_id = None
        if unit_price is None:
            raise ValueError("unit_price is required for a manually-entered item")

    unit_price = apply_condition(float(unit_price), condition)

    await rooms_service.add_item(
        room_id=room.id,
        side=side,
        name=name,
        qty=qty,
        unit_price=unit_price,
        source=source,
        catalog_item_id=catalog_item_id,
        box_price=box_price,
        models_per_box=models_per_box,
        condition=condition,
    )

    if source == "manual":
        await _log_coverage_gap(room.code, payload.get("faction_hint"), name, unit_price)


async def _handle_edit_item(payload: dict) -> None:
    item_id = payload.get("item_id")
    if item_id is None:
        raise ValueError("item_id is required")
    qty = payload.get("qty")
    unit_price = payload.get("unit_price")
    name = payload.get("name")
    condition = payload.get("condition")

    if qty is not None:
        qty = int(qty)
        if qty <= 0:
            raise ValueError("qty must be positive")
    if unit_price is not None:
        unit_price = float(unit_price)
    if condition is not None and condition not in CONDITION_MULTIPLIERS:
        raise ValueError(f"condition must be one of {list(CONDITION_MULTIPLIERS)}")

    if condition is not None and unit_price is None:
        # Re-baseline the price for the new condition. If the caller also sent an
        # explicit unit_price, that wins instead — condition still gets persisted
        # (so a future condition change re-baselines from the right multiplier),
        # but we don't second-guess a price someone typed directly.
        current = await rooms_service.get_item(item_id)
        if current is None:
            raise ValueError("Item not found")
        unit_price = rebaseline_condition(current["unit_price"], current["condition"], condition)

    await rooms_service.edit_item(item_id, qty=qty, unit_price=unit_price, name=name, condition=condition)
