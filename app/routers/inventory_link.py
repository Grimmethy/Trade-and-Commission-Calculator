"""Private-mode bridge to the inventory plugin (read-only). The calculator never writes inventory data; a finished deal is
recorded in the inventory plugin's own Trades tab."""
import json
import os
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


@router.get("/api/inventory/items")
def items(q: str = Query("", max_length=80), status: str = "in_stock", limit: int = Query(25, ge=1, le=100)):
    params = {"limit": limit, "status": status}
    if q:
        params["q"] = q
    data = _get("/api/items?" + urllib.parse.urlencode(params))
    keep = ("code", "name", "grade", "status", "quantity", "owner", "msrp", "listed_on")
    return {"total": data.get("total", 0), "items": [{k: i.get(k) for k in keep} for i in data.get("items", [])]}


@router.get("/api/inventory/status")
def status():
    try:
        return {"ok": True, "summary": _get("/api/summary")}
    except HTTPException as e:
        return {"ok": False, "error": e.detail}
