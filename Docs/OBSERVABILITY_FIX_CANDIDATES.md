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

### AC-2 · Silent Exception Swallowing in WebSocket Message Handling
Strength: Strong
Files: app/routers/ws.py
Snippet:
```
            try:
                await _handle_message(room_id, msg_type, payload)
                await _broadcast_state(room_id)
            except ValueError as exc:
                await manager.send_to(websocket, {"type": "error", "payload": {"message": str(exc)}})
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)
```

Problem:
The `try/except` block around `_handle_message` silently catches `ValueError` and sends a user-facing error message via `manager.send_to`, but does not log the exception. Moreover, any other exception (e.g., `KeyError`, `TypeError`) is caught by the outer `except Exception` block, which sends a generic "Internal server error" message but does not log it — leaving no observability trail. Since the project has no metrics system, logging is the only way to detect and debug silent failures. Without logging, operators cannot trace root causes or confirm system health.

Solution:
Log all exceptions using `logging.error()` with context (room_id, msg_type, payload) before re-raising or returning. For `ValueError`, log the error message. For all other exceptions, log the full traceback using `exc_info=True`. The fix modifies the `try/except` block to log both `ValueError` and `Exception` cases, ensuring no exception is silently swallowed without a log.

Benefits:
Operators can now detect and debug silent failures in message handling by reviewing logs. The system’s health becomes observable through logs, even without metrics. The fix uses only stdlib logging — no new dependencies or telemetry systems required — and preserves the existing user-facing error behavior.
