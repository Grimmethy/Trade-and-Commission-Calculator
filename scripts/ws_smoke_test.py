"""One-off manual smoke test: two WebSocket clients on the same room, verify live sync."""
import asyncio
import json
import sys

import websockets

ROOM_CODE = sys.argv[1] if len(sys.argv) > 1 else "nxcpz"
URL = f"ws://127.0.0.1:8123/ws/{ROOM_CODE}"


async def main():
    async with websockets.connect(URL) as client_a, websockets.connect(URL) as client_b:
        # both get initial full_state on connect
        await client_a.recv()
        await client_b.recv()

        await client_a.send(json.dumps({
            "type": "add_item",
            "payload": {"side": "A", "name": "War Walker", "qty": 2, "source": "catalog", "catalog_item_id": None, "unit_price": 42.5},
        }))

        # client_a sees its own broadcast
        state_a = json.loads(await client_a.recv())
        # client_b should see the SAME update live, without sending anything itself
        state_b = json.loads(await client_b.recv())

        assert state_a["type"] == "full_state", state_a
        assert state_b["type"] == "full_state", state_b
        assert state_b["payload"]["totals"]["side_a"] == 85.0, state_b["payload"]["totals"]

        await client_b.send(json.dumps({"type": "set_cash", "payload": {"side": "B", "amount": 235}}))
        state_a2 = json.loads(await client_a.recv())
        totals = state_a2["payload"]["totals"]
        assert totals["suggested_topup_side"] == "A", totals
        print("Live sync verified: total_a=", totals["side_a"], "suggested topup:", totals)

        # manual item with no catalog match -> should log a coverage gap
        await client_a.send(json.dumps({
            "type": "add_item",
            "payload": {"side": "B", "name": "Death Korps of Krieg squad", "qty": 1, "source": "manual", "unit_price": 53},
        }))
        await client_a.recv()
        await client_b.recv()
        print("Manual unmatched item added OK")


asyncio.run(main())
