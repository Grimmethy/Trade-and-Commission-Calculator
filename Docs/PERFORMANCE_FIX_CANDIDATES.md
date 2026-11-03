# Performance Fix Candidates

### AC-1 · Batch Concurrent DB Inserts to Reduce Latency
Strength: Strong
Files: app/commissions.py
Snippet:
```

async def create_commission(painter_name: str) -> Commission:
    db = get_db()
    for _ in range(10):
        code = "".join(secrets.choice(ALPHABET) for _ in range(5))
        try:
            cursor = await db.execute(
```

Problem:
The current loop runs 10 sequential database inserts, each awaiting a potentially I/O-bound operation. Since each insert is independent (unique code per iteration), the total execution time is effectively 10x the time of a single insert — even though the DB could handle all 10 concurrently. This creates unnecessary latency and resource waste, especially under load.

Solution:
Replace the loop with asyncio.gather to run all 10 DB operations in parallel. This leverages the existing asyncio runtime to issue all inserts concurrently, reducing total latency from ~10x to ~1x (assuming no DB serialization or contention).

Benefits:
The total time to insert 10 records drops dramatically — from ~10 sequential DB round trips to ~1 concurrent round trip — improving responsiveness and throughput. No new dependencies or APIs are required — only asyncio.gather, which is already available in the async context.

### AC-2 · Parallelize Catalog Seeding with asyncio.gather
Strength: Strong
Files: app/db.py
Snippet:
```
    if row["n"] > 0:
        return
    data = json.loads(CATALOG_SEED_PATH.read_text(encoding="utf-8"))
    for item in data:
        cursor = await _db.execute(
            """
            INSERT INTO catalog_items (ip, faction, item_name, box_price, website_link, image_url, source_file, imported_at)
```

Problem:
The current loop iterates over 1000+ catalog items sequentially, executing each `await _db.execute(...)` one after another. Since each database insert is independent and the DB driver is async (as implied by `await`), this serial execution creates a significant performance bottleneck — potentially 1000x slower than concurrent execution. This is especially costly during startup, as catalog seeding is likely a hot path.

Solution:
Replace the sequential loop with `asyncio.gather` to run all database inserts concurrently. Collect each `await _db.execute(...)` coroutine into a list of tasks, then await them all at once. This leverages the async nature of the DB driver without introducing new dependencies or changing the data model.

Benefits:
The total time to seed the catalog will be reduced to the duration of the slowest insert (instead of summing all insert times). This improves startup latency and reduces resource contention during catalog initialization, making the system more responsive for users.

### AC-3 · Concurrent WebSocket Sends
Strength: Strong
Files: app/websocket_manager.py
Snippet:
```
        sockets = self._rooms.get(room_id, set())
        payload = json.dumps(message)
        dead = []
        for ws in sockets:
            try:
                await ws.send_text(payload)
            except Exception:
```

Problem:
The current loop iterates over `sockets` and calls `await ws.send_text(payload)` synchronously for each connection. This serializes all sends, causing total latency to scale linearly with the number of clients (O(n)), even though the underlying I/O is async. With 100+ clients, this creates a bottleneck where each send blocks until the prior one completes — unnecessarily delaying the entire batch and wasting CPU time waiting for network I/O.

Solution:
Replace the synchronous loop with `asyncio.gather(*[ws.send_text(payload) for ws in sockets])` to send to all sockets concurrently. This parallelizes the I/O operations using the existing `asyncio` primitives, reducing total latency to near O(1) (assuming network is the bottleneck) and eliminating per-iteration blocking.

Benefits:
After the fix, the system will send messages to all connected clients in parallel, dramatically reducing end-to-end latency for large rooms. The fix is zero-cost in terms of dependencies or complexity — it uses only standard library primitives already in use, and preserves all existing behavior (including error handling, since `asyncio.gather` will propagate exceptions).
