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
