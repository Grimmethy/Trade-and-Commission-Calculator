"""Private-mode bridge to the inventory plugin (read-only). The calculator never writes inventory data; a finished deal is
recorded in the inventory plugin's own Trades tab."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()
INVENTORY_URL = os.environ.get("INVENTORY_URL", "http://127.0.0.1:7460").rstrip("/")


def _get(path: str) -> dict:
    try:
        with urllib.request.urlopen(INVENTORY_URL + path, timeout=5) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise HTTPException(502, f"inventory plugin not reachable at {INVENTORY_URL}: {e}")


STOCK_STATUSES = ("in_stock", "listed")   # both are physically on the shelf; "listed" only means a live listing exists
_KEEP = ("code", "name", "grade", "status", "quantity", "owner", "msrp", "listed_on")


def _fetch(q: str, status: str, limit: int) -> dict:
    params = {"limit": limit, "status": status}
    if q:
        params["q"] = q
    return _get("/api/items?" + urllib.parse.urlencode(params))


def search_stock(q: str, status: str, limit: int) -> dict:
    """status 'any' = everything on the shelf (in_stock plus listed, never sold or out); the plugin only matches one status
    per call, so 'any' asks twice and merges by code."""
    if status != "any":
        data = _fetch(q, status, limit)
        return {"total": data.get("total", 0), "items": [{k: i.get(k) for k in _KEEP} for i in data.get("items", [])]}
    merged, total = {}, 0
    for st in STOCK_STATUSES:
        data = _fetch(q, st, limit)
        total += data.get("total", 0)
        for i in data.get("items", []):
            merged[i["code"]] = {k: i.get(k) for k in _KEEP}
    return {"total": total, "items": sorted(merged.values(), key=lambda i: i["code"])[:limit]}


def listed_price(listed_on: str | None) -> float | None:
    """First '$12.34' in the plugin's listed_on text ('square $58.50, ebay $60.00'), else None."""
    m = re.search(r"\$([0-9]+(?:\.[0-9]{1,2})?)", listed_on or "")
    return float(m.group(1)) if m else None


def lookup_stock(code: str) -> dict | None:
    """The one shelf item with exactly this inventory code (case-insensitive), or None."""
    wanted = code.strip().upper()
    if not wanted:
        return None
    for i in search_stock(wanted, "any", 50)["items"]:
        if i["code"].upper() == wanted:
            return i
    return None


@router.get("/api/inventory/items")
def items(q: str = Query("", max_length=80), status: str = "in_stock", limit: int = Query(25, ge=1, le=100)):
    return search_stock(q, status, limit)


@router.get("/api/inventory/status")
def status():
    try:
        return {"ok": True, "summary": _get("/api/summary")}
    except HTTPException as e:
        return {"ok": False, "error": e.detail}
