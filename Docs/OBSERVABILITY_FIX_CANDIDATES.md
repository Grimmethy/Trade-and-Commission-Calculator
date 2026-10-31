# Observability Fix Candidates

### AC-1 · Silent Infinite Loop Without Heartbeat Logging
Strength: Strong
Files: app/rooms.py
Snippet:
```
async def _unique_code_for_slug(db, base_slug: str, row_id: int, table: str = "rooms") -> str:
    candidate = base_slug
    suffix = 2
    while True:
        row = await (
            await db.execute(
                f"SELECT id FROM {table} WHERE code = ? AND id != ?", (candidate, row_id)
```

Problem:
The `_unique_code_for_slug` function contains an infinite `while True` loop that lacks any heartbeat logging or progress signal. Since the project has no metrics system, operators have no way to detect if the loop is stuck due to a database lock, query timeout, or misconfigured slug — especially since the loop does not log any iteration count or state. Without logging, the loop may run indefinitely or silently fail to terminate, leading to resource exhaustion or data inconsistency with no observable failure.

Solution:
Add a heartbeat log every 1000 iterations using `logging.warning` to surface stalls or hangs. The log includes the base slug, current suffix, and room ID to aid in debugging. The loop already exits on success, and exceptions from `db.execute` or `fetchone` will propagate — no need to rethrow or add telemetry.

Benefits:
With the heartbeat log, operators can detect when the loop is stalled or hanging — for example, if a database is down or a query is slow — and take corrective action. The fix is minimal, uses only available logging, and does not require metrics or telemetry — making it safe to deploy in the current environment.
