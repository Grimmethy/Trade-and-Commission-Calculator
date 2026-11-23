# Observability Fix Candidates

### AC-1 · silent-catch-block at app/catalog_import.py:31
Strength: Moderate
Files: app/catalog_import.py
Snippet:
```
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


```

Problem:
A caught error is discarded with no operator visibility. except block does not appear to log, re-raise, or otherwise surface the exception (low confidence: appears to be deliberate recovery/fallback -- verify) — regex matched but float() failed, silently returning None hides a regex/logic bug in price parsing

Solution:
Log the caught error (message + context) before the existing fallback/return; do not change control flow.

Benefits:
An operator can tell a silent recovery from a real failure in the logs.

### AC-2 · Add Timeout and Logging to Unique Code Generation Loop
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
The loop in `_unique_code_for_slug` can run indefinitely if no unique `candidate` is found, and there’s no heartbeat, timeout, or logging to signal that it’s stuck — making it invisible to operators. Since the project has no metrics system, emitting a counter or gauge is impossible. The only available primitive is `logging`, which is used elsewhere in the codebase (e.g., for error handling). Without a timeout or log, a hung process may appear dead or unresponsive, with no alert or trace to diagnose.

Solution:
Insert a timeout check after the `while True:` block: if `suffix > 1000`, log a warning with context (room ID, base_slug) and raise `TimeoutError` to surface the issue to the caller. This uses only `logging.warning` and `raise` — no metrics or telemetry — and preserves the loop’s bounded behavior while making the stall visible and actionable.

Benefits:
Operators can now detect when unique code generation stalls (e.g., due to a race condition or database lock) via logs or error traces. The fix prevents silent hangs and enables faster debugging and recovery — without requiring metrics or telemetry infrastructure.
