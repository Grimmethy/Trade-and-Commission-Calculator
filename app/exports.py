"""CSV + photo-folder export for listing inventory on Square and eBay.

Neither platform's bulk CSV import can attach local photos inline — both only
accept a manually-uploaded photo (via their dashboard) or a publicly-reachable
photo URL they fetch at import time. Since photos here are stored locally with
no public hosting, this module produces (a) a CSV with every field it can
populate and (b) a same-batch, SKU-named photo folder — one manual
drag-and-drop upload pass per platform per export, not one-click
auto-posting-with-photos. That's a permanent constraint of both platforms'
CSV pipeline, not a gap to close later.

Square's and eBay's exact required columns vary by account/category and
aren't a fixed constant worth hardcoding forever, so both exporters are
template-driven: if the operator drops their platform's own downloaded
export/template at TEMPLATE_PATHS[platform], its header row becomes the
authoritative column set and known fields get filled in by name. With no
template present, a best-known static column list is used instead, so the
feature works out of the box before a template is supplied.
"""

import csv
import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from app.models import InventoryItem
from app.photos import item_photo_dir

EXPORTS_DIR = Path(os.environ.get("EXPORTS_DIR", "exports"))
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

TEMPLATE_PATHS = {
    "square": DATA_DIR / "square_template.csv",
    "ebay": DATA_DIR / "ebay_template.csv",
}

# --- Business config the operator needs to fill in — not derivable from our data. ---
# ip/faction -> eBay numeric category ID. Empty by default; export leaves
# Category blank for anything unmapped rather than guessing.
EBAY_CATEGORY_MAP_PATH = DATA_DIR / "ebay_category_map.json"

# Our condition enum -> eBay ConditionID. All four default to "Used" (3000):
# none of these represent a factory-sealed-new kit (they're assembled and/or
# painted), so "New" (1000) would be misleading even for `assembled`. Adjust
# per-category if eBay allows a more specific code once real listings exist.
EBAY_CONDITION_MAP = {
    "needs_repair": 3000,
    "assembled": 3000,
    "partial_paint": 3000,
    "showcase": 3000,
}

# Static shipping/location config for the eBay fallback template — business-specific,
# needs the operator's real policy. Placeholder values, safe to leave as-is until then.
EBAY_LOCATION = os.environ.get("EBAY_LOCATION", "")
EBAY_SHIPPING_TYPE = os.environ.get("EBAY_SHIPPING_TYPE", "Flat")
EBAY_SHIPPING_SERVICE = os.environ.get("EBAY_SHIPPING_SERVICE", "USPSGround")
EBAY_SHIPPING_COST = os.environ.get("EBAY_SHIPPING_COST", "0.00")
EBAY_DISPATCH_TIME_MAX = os.environ.get("EBAY_DISPATCH_TIME_MAX", "3")

SQUARE_STATIC_COLUMNS = [
    "Item Name",
    "Variation Name",
    "SKU",
    "Description",
    "Category",
    "Reporting Category",
    "Price",
    "New Quantity",
    "Enabled",
]

EBAY_STATIC_COLUMNS = [
    "Action(SiteID=US|Country=US|Currency=USD|Version=1193)",
    "Custom label (SKU)",
    "Category",
    "Title",
    "ConditionID",
    "PicURL",
    "Quantity",
    "Format",
    "Duration",
    "StartPrice",
    "Description",
    "Location",
    "ShippingType",
    "ShippingService-1:Option",
    "ShippingService-1:Cost",
    "DispatchTimeMax",
]


def _load_ebay_category_map() -> dict:
    if not EBAY_CATEGORY_MAP_PATH.exists():
        return {}
    return json.loads(EBAY_CATEGORY_MAP_PATH.read_text(encoding="utf-8"))


def read_template_headers(platform: str) -> list[str] | None:
    path = TEMPLATE_PATHS.get(platform)
    if not path or not path.exists():
        return None
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        return next(reader, None)


def _square_field(item: InventoryItem, header: str) -> str:
    header_lower = header.strip().lower()
    if header_lower == "item name":
        return item.name
    if header_lower == "variation name":
        return "Regular"
    if header_lower == "sku":
        return item.sku
    if header_lower == "description":
        return item.notes or ""
    if header_lower == "category":
        return item.ip or ""
    if header_lower == "reporting category":
        return item.faction or ""
    if header_lower == "price":
        return f"{item.label_price:.2f}"
    if header_lower == "new quantity":
        return str(item.qty)
    if header_lower.startswith("enabled"):
        return "Y"
    return ""


def _ebay_field(item: InventoryItem, header: str, category_map: dict) -> str:
    header_lower = header.strip().lower()
    if header_lower.startswith("action("):
        return "Add"
    if header_lower == "custom label (sku)":
        return item.sku
    if header_lower == "category":
        return str(category_map.get(f"{item.ip}|{item.faction}", ""))
    if header_lower == "title":
        return item.name[:80]  # eBay title limit
    if header_lower == "conditionid":
        return str(EBAY_CONDITION_MAP.get(item.condition, 3000))
    if header_lower == "picurl":
        return ""  # deliberately blank — see module docstring
    if header_lower == "quantity":
        return str(item.qty)
    if header_lower == "format":
        return "FixedPrice"
    if header_lower == "duration":
        return "GTC"
    if header_lower == "startprice":
        return f"{item.label_price:.2f}"
    if header_lower == "description":
        return item.notes or ""
    if header_lower == "location":
        return EBAY_LOCATION
    if header_lower == "shippingtype":
        return EBAY_SHIPPING_TYPE
    if header_lower == "shippingservice-1:option":
        return EBAY_SHIPPING_SERVICE
    if header_lower == "shippingservice-1:cost":
        return EBAY_SHIPPING_COST
    if header_lower == "dispatchtimemax":
        return EBAY_DISPATCH_TIME_MAX
    return ""


def build_square_rows(items: list[InventoryItem], headers: list[str] | None = None) -> list[dict]:
    headers = headers or SQUARE_STATIC_COLUMNS
    return [{h: _square_field(item, h) for h in headers} for item in items]


def build_ebay_rows(items: list[InventoryItem], headers: list[str] | None = None) -> list[dict]:
    headers = headers or EBAY_STATIC_COLUMNS
    category_map = _load_ebay_category_map()
    return [{h: _ebay_field(item, h, category_map) for h in headers} for item in items]


BUILDERS = {"square": build_square_rows, "ebay": build_ebay_rows}


def write_export(platform: str, items: list[InventoryItem]) -> Path:
    """Writes <platform>.csv plus a photos/<sku>/ folder (every photo, not
    just primary) for this batch, zips it, and returns the zip path. The
    unzipped folder is left alongside it under EXPORTS_DIR for inspection
    before the manual upload pass."""
    if platform not in BUILDERS:
        raise ValueError(f"Unknown export platform {platform!r}")

    headers = read_template_headers(platform)
    rows = BUILDERS[platform](items, headers)
    effective_headers = headers or (SQUARE_STATIC_COLUMNS if platform == "square" else EBAY_STATIC_COLUMNS)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_dir = EXPORTS_DIR / f"{platform}_{timestamp}"
    photos_dir = batch_dir / "photos"
    batch_dir.mkdir(parents=True, exist_ok=True)
    photos_dir.mkdir(exist_ok=True)

    csv_path = batch_dir / f"{platform}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=effective_headers)
        writer.writeheader()
        writer.writerows(rows)

    for item in items:
        src_dir = item_photo_dir(item.sku)
        if not src_dir.exists():
            continue
        dest_dir = photos_dir / item.sku
        dest_dir.mkdir(exist_ok=True)
        for photo in item.photos:
            src = src_dir / photo.filename
            if src.exists():
                shutil.copy2(src, dest_dir / photo.filename)

    zip_path = batch_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in batch_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(batch_dir.parent))

    return zip_path
