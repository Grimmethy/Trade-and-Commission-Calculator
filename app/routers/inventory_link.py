"""Private-mode bridge to the inventory plugin (read-only). The calculator never writes inventory data; a finished deal is
recorded in the inventory plugin's own Trades tab."""
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()
logger = logging.getLogger(__name__)
INVENTORY_URL = os.environ.get("INVENTORY_URL", "http://127.0.0.1:7460").rstrip("/")


def _get(path: str, timeout: float = 5) -> dict:
    try:
        with urllib.request.urlopen(INVENTORY_URL + path, timeout=timeout) as r:
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


PRICE_FLAGS = ('msrp_disagrees', 'shared_sku', 'no_code', 'duplicate_code')
_DETAIL_MAX = 25
_DETAIL_TIMEOUT = 3


def _fetch_detail(code) -> dict | None:
    """Plugin detail for one code via GET /api/item/<code>; None on any failure. Never raises."""
    if not code:
        return None
    try:
        d = _get("/api/item/" + urllib.parse.quote(str(code), safe=""), timeout=_DETAIL_TIMEOUT)
    except Exception:
        return None
    return d if isinstance(d, dict) else None


def _open_flag_kinds(detail: dict) -> list | None:
    """Kinds of the detail's flags whose status is 'open' ([] when none; None if the shape is unusable)."""
    flags = detail.get("flags")
    if flags is None:
        return []
    if not isinstance(flags, list):
        return None
    return [f["kind"] for f in flags if isinstance(f, dict) and f.get("status") == "open" and "kind" in f]


def project_item(item: dict, detail: dict | None) -> dict:
    """Pure projection of a list item plus its (possibly missing) plugin detail; no network access."""
    out = {k: item.get(k) for k in _KEEP}
    if not isinstance(detail, dict):
        out.update(flags=None, location=None, msrp_source=item.get("msrp_source"), verified=False)
        return out
    flags = _open_flag_kinds(detail)
    msrp_source = detail.get("msrp_source")
    if msrp_source is None:
        msrp_source = item.get("msrp_source")
    out["flags"] = flags
    out["location"] = detail.get("location")
    out["msrp_source"] = msrp_source
    out["verified"] = bool(out.get("msrp")) and isinstance(flags, list) and not any(k in PRICE_FLAGS for k in flags)
    return out


def enrich_items(items: list, fetch_detail=_fetch_detail) -> list:
    """Project items with detail data; only the first _DETAIL_MAX get a detail call, the rest get flags=None."""
    head, tail = items[:_DETAIL_MAX], items[_DETAIL_MAX:]
    details = []
    if head:
        def safe(code):
            try:
                return fetch_detail(code)
            except Exception:
                return None
        with ThreadPoolExecutor(max_workers=8) as ex:
            details = list(ex.map(safe, [i.get("code") for i in head]))
    return [project_item(i, d) for i, d in zip(head, details)] + [project_item(i, None) for i in tail]


@router.get("/api/inventory/items")
def items(q: str = Query("", max_length=80), status: str = "in_stock", limit: int = Query(25, ge=1, le=100)):
    data = search_stock(q, status, limit)
    return {**data, "items": enrich_items(data["items"])}


@router.get("/api/inventory/status")
def status():
    try:
        return {"ok": True, "summary": _get("/api/summary")}
    except HTTPException as e:
        return {"ok": False, "error": e.detail}
    except Exception as exc:
        logger.exception("inventory status: unexpected error fetching /api/summary")
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
