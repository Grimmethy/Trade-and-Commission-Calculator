"""Public vs private mode.

The same app runs twice: the *public* instance sits behind a tunnel on the website (customers use the trade calculator and
read a commission sheet they were given the code for), the *private* instance is the Agent Manager tab (owner only: history,
commission admin, gaps, inventory lookup). The public instance is an ALLOWLIST: anything not listed here is a 404, so a new
route is private by default. TRADE_MODE defaults to public so a forgotten env var fails closed.
"""
import os
import re
import time

MODE = os.environ.get("TRADE_MODE", "public").strip().lower()
if MODE not in ("public", "private"):
    raise RuntimeError("TRADE_MODE must be 'public' or 'private'")

# (method, compiled path) pairs a customer may use on the public instance.
_PUBLIC = [(m, re.compile(p)) for m, p in [
    ("GET", r"^/$"),
    ("GET", r"^/healthz$"),
    ("GET", r"^/(manifest\.webmanifest|sw\.js)$"),
    ("GET", r"^/static/(?!.*\.\.)[\w./-]+$"),
    ("POST", r"^/rooms$"),
    ("GET", r"^/trade/[A-Za-z0-9]+$"),
    ("GET", r"^/catalog/(ips|factions|units|search)$"),
    ("GET", r"^/commissions/[A-Za-z0-9_-]+$"),
    ("GET", r"^/commissions/[A-Za-z0-9_-]+/print$"),
]]


def public_allows(method: str, path: str) -> bool:
    return any(m == method and rx.match(path) for m, rx in _PUBLIC)


class RoomLimiter:
    """Sliding window: at most `limit` new trade rooms per client per hour (the public form is otherwise a free DB-filler)."""

    def __init__(self, limit: int = 20, window: float = 3600.0):
        self.limit, self.window, self.hits = limit, window, {}

    def allow(self, client: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        recent = [t for t in self.hits.get(client, []) if now - t < self.window]
        ok = len(recent) < self.limit
        if ok:
            recent.append(now)
        self.hits[client] = recent
        if len(self.hits) > 5000:     # bound memory: drop clients with no recent hits
            self.hits = {k: v for k, v in self.hits.items() if v and now - v[-1] < self.window}
        return ok


def client_ip(headers, peer: str | None) -> str:
    # Behind the Cloudflare tunnel the real caller is in CF-Connecting-IP; locally it is the socket peer.
    return headers.get("cf-connecting-ip") or (headers.get("x-forwarded-for") or "").split(",")[0].strip() or peer or "?"
