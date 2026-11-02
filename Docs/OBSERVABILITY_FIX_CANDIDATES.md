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

### AC-3 · Silent Error Swallowing in WebSocket Message Handling
Strength: Strong
Files: app/routers/ws.py
Snippet:
```
                await _broadcast_state(room_id)
            except ValueError as exc:
                await manager.send_to(websocket, {"type": "error", "payload": {"message": str(exc)}})
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)


```

Problem:
The `try/except` block around `_handle_message` catches `ValueError` but only sends an error message to the client via `manager.send_to(...)`. It does not log the error or re-raise it, meaning the error is silently swallowed from an observability perspective. Since the project has no metrics system, there is no telemetry to surface the error. Without logging, operators cannot trace or diagnose why a client received an error — especially if the error is due to a room no longer existing — making the system opaque to human operators.

Solution:
Add a logging statement inside the `except ValueError as exc:` block using the stdlib `logging` module. Log the error with context including `room_id` and `msg_type` to enable traceability. Since the project has no metrics, no telemetry is added. The fix does not re-raise the exception because this is a background WebSocket handler and re-raising would not be appropriate unless the caller expects it — which it does not.

Benefits:
Once fixed, the error will appear in logs with sufficient context to identify the source (room_id, message type) and reason (ValueError), enabling operators to diagnose and respond to client-facing errors without relying on client-side feedback. This closes the observability gap without introducing metrics or telemetry that the project does not support.

### AC-4 · Fix Silent Error Swallowing in Commission Rename
Strength: Strong
Files: app/static/commission.js
Snippet:
```
        // at once, unlike the trade room page where every action goes through one
        // websocket keyed by room id, not room code.
        window.location.href = `/commissions/${newCode}`;
      } catch {
        codeEl.textContent = currentCode;
        codeEl.classList.add("rename-failed");
        setTimeout(() => codeEl.classList.remove("rename-failed"), 1500);
```

Problem:  
The `catch` block around `window.location.href = `/commissions/${newCode}`` silently swallows any error — including network failures, invalid server responses, or DOM manipulation issues — without logging or surfacing it. The UI shows “rename-failed” but no developer or user can diagnose why. Since the project has no metrics system, logging via `console.error` is the only viable observability path — and it’s absent here.

Solution:  
Add `console.error("Commission rename failed:", err)` inside the `catch` block to log the error with context, and rethrow to preserve the error for any higher-level handling (though none exists here — logging is sufficient). The UI state remains unchanged, so no user experience disruption.

Benefits:  
Developers can now debug rename failures by checking browser console logs. The error is no longer silently swallowed, enabling faster diagnosis and reducing time to fix production issues.

### AC-5 · Silent Fetch Error Without Logging or User Feedback
Strength: Strong
Files: app/static/stock.js
Snippet:
```
      timer = setTimeout(async () => {
        let data;
        try { const r = await fetch("/api/inventory/items?limit=8&q=" + encodeURIComponent(q)); data = r.ok ? await r.json() : { items: [] }; }
        catch (e) { data = { items: [] }; }
        list.innerHTML = "";
        if (!data.items.length) { list.innerHTML = "<li>No matching stock (is the inventory tab running?)</li>"; list.hidden = false; return; }
        data.items.forEach((it) => {
```

Problem:
The `fetch` call in `stock.js` silently swallows any error (network, server, CORS, etc.) by assigning an empty array to `data`, with no logging or rethrowing. The UI then shows “No matching stock” only when `data.items.length === 0`, which is distinct from a fetch failure — so users see no indication of why the data is missing. Without logs, debugging is impossible, and the system remains opaque to failures that could be widespread.

Solution:
Replace the `catch (e) { data = { items: [] }; }` block with:
```javascript
catch (e) {
  console.error("Failed to fetch stock data for query:", q, "Error:", e);
  data = { items: [] };
}
```
This logs the error with the query and error object so it can be traced during debugging. The error is still suppressed — which is acceptable given the UI’s current behavior — but developers now have visibility into why fetches fail.

Benefits:
Once fixed, errors that previously went unseen (e.g., server down, CORS blocked, network timeout) will appear in console logs, enabling faster debugging. The UI remains unchanged, but the system’s observability is restored — allowing teams to detect and resolve silent failures without user complaints or repeated failed attempts.

### AC-6 · Silent Error Swallowing in Trade Room Rename
Strength: Strong
Files: app/static/trade.js
Snippet:
```
      roomCodeEl.textContent = newCode;
      document.title = `Trade Calculator — Room ${newCode}`;
      history.replaceState(null, "", `/trade/${newCode}`);
    } catch {
      roomCodeEl.textContent = currentCode;
      roomCodeEl.classList.add("rename-failed");
      setTimeout(() => roomCodeEl.classList.remove("rename-failed"), 1500);
```

Problem:
The `catch` block in the rename operation silently swallows any error from the fetch (network failure, server error, etc.) and only shows a generic UI state ("rename-failed") without logging or preserving the error for debugging. Since the project has no metrics or telemetry system, there’s no way to alert or monitor failures — but logging the error to `console.error` is the only available observability primitive. Without this, operators cannot diagnose why renames fail, and users experience unexplained UI states.

Solution:
Replace the empty `catch` block with one that logs the error to `console.error` with context (operation, URL, error message), then rethrows to preserve the stack trace for the caller. This uses only `console.error` (available) and rethrowing (safe in async context).

Benefits:
Operators can now debug rename failures by checking console logs, and users won’t be left with unexplained UI states without any diagnostic trail — even without metrics, observability is restored via logging.

### AC-7 · Silent WebSocket Failure Without Logging or Rethrow
Strength: Strong
Files: app/websocket_manager.py
Snippet:
```
        for ws in sockets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            sockets.discard(ws)
```

Problem:
The `broadcast` function silently catches any exception thrown during `ws.send_text(payload)` and removes the WebSocket from the set without logging or re-raising. This means connection failures — such as network errors, client disconnections, or protocol violations — are invisible to the caller. Since the function returns `None`, the caller cannot reasonably handle a silent failure, making this a genuine observability hygiene issue. Without logging, operators or developers have no visibility into when or why WebSocket messages fail, leading to potential silent data loss or confusion in message delivery.

Solution:
Log the exception with context including the WebSocket and room ID, then re-raise to surface the error to the caller. Since the function returns `None`, re-raising is appropriate to force visibility — e.g., in the WebSocket server loop or higher-level logic. If the caller cannot act on it, logging is sufficient to make the error visible for debugging.

Benefits:
Once fixed, the system gains visibility into WebSocket connection failures through logs, enabling faster debugging and preventing silent data loss or duplicate message delivery. The fix uses only available primitives (`logging`) and does not fabricate metrics or telemetry.

### AC-8 · Trade Calculator Error Swallowed Without Logging
Strength: Strong
Files: ui/trade-tab.js
Snippet:
```
    const r = await fetch('/api/plugins/trade-calculator/ensure-started', { method: 'POST' });
    const j = await r.json().catch(() => ({}));
    ok = r.ok && j.healthy !== false; why = r.ok ? 'the server did not become healthy in time' : (j.error || r.status);
  } catch (e) { why = String(e); }
  if (!ok) {
    main.innerHTML = `<div style="padding:16px"><strong>Trade calculator did not start</strong><p>${escapeAttr(String(why))}</p><p>Start it by hand: <code>cd /media/model-cache/github/trade-calculator &amp;&amp; ./run.sh</code></p></div>`;
    return;
```

Problem:  
The `try...catch` block in `ui/trade-tab.js` silently swallows errors from the `fetch` call to `/api/plugins/trade-calculator/ensure-started` without logging or rethrowing. This means if the server is unreachable, returns an error, or responds with malformed JSON, the error is lost to the user and cannot be debugged without external logs — because the project has no telemetry system and no other logging mechanism beyond `console.error`.

Solution:  
Inside the `catch` block, log the error with context using `console.error` and rethrow the error to surface it to higher-level error handlers. This ensures the error is visible to developers and can be handled appropriately by the application’s error boundaries — without fabricating any telemetry or metrics.

Benefits:  
Once fixed, developers can debug silent failures in the trade calculator startup process by inspecting console logs. Users will also see more actionable error messages, and the system will no longer hide failures behind generic UI text.

### AC-9 · Add Heartbeat and Guardrail to Long-Running Slug Uniqueness Loop
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
The loop in `_unique_code_for_slug` runs indefinitely until `row is None`, which may never occur due to database collisions or silent query failures. There is no heartbeat, no iteration limit, and no logging to indicate progress or failure — making it unobservable. Without any telemetry or logging (as per project capabilities), the loop could run forever without detection, silently consuming resources and hiding real failures.

Solution:
Add a heartbeat log every 1000 iterations and a hard limit of 10,000 iterations to prevent infinite loops. Log every heartbeat with `logging.warning` and raise a `RuntimeError` if the limit is exceeded, logging the slug and table for context. This uses only `logging`, which the project supports, and does not add metrics or telemetry.

Benefits:
Once fixed, the loop becomes observable: it logs progress every 1000 iterations and will crash with a clear error message if it runs too long — preventing silent hangs and enabling debugging. The fix is minimal, safe, and matches project capabilities.

### AC-10 · Silent Error Swallowing in Commission Save
Strength: Strong
Files: app/static/commission.js
Snippet:
```
        totalEl.textContent = data.total;
        if (markForm) markForm.hidden = !(data.total > 0 && data.returned_count === data.total && data.status === "submitted");
        showStatus(form, "Saved");
      } catch (err) {
        showStatus(form, "Could not save, tap to retry", true);
      }
    }
```

Problem:  
The `catch` block in the `save` function silently swallows the error thrown when the server returns a non-2xx status (e.g., 500), without logging the actual error (status, response body, or stack trace). The user sees a generic “Could not save, tap to retry” message, but no observability exists to debug why the save failed — whether it’s a server crash, API change, or network issue. Since the project has no metrics or third-party logging, the error is completely invisible to operators.

Solution:  
Log the error with sufficient context using `console.error`, preserving the original error object and its message. The user message remains unchanged. Optionally, rethrow the error to allow the caller to handle it if needed — but since no telemetry exists, logging to `console.error` is sufficient to satisfy observability hygiene.

Benefits:  
Once fixed, operators can debug save failures by inspecting console logs during production incidents. The error’s root cause (e.g., HTTP 500, malformed response) becomes visible, enabling faster resolution of outages or regressions — without requiring metrics or telemetry infrastructure.
