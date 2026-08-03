import os
from datetime import date

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app import exports as exports_service
from app import inventory as inventory_service
from app import labels as labels_service
from app import photos as photos_service
from app import sku_codes

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/inventory", response_class=HTMLResponse)
async def inventory_list(request: Request, status: str | None = None):
    items = await inventory_service.list_items(status)
    return templates.TemplateResponse(
        request, "inventory_list.html", {"items": items, "status_filter": status}
    )


@router.get("/inventory/next-sku")
async def next_sku(ip: str | None = None, faction: str | None = None, condition: str = "assembled"):
    """Preview the SKU that would be generated for a given ip/faction/condition
    combo, without creating anything — lets the UI show it before submit.
    Must be registered before /inventory/{item_id} — otherwise "next-sku"
    gets matched as an attempted (invalid) item_id."""
    prefix = sku_codes.build_sku_prefix(ip, faction, condition)
    return {"sku": await inventory_service.generate_sku(prefix), "prefix": prefix}


@router.get("/inventory/{item_id}", response_class=HTMLResponse)
async def inventory_detail(request: Request, item_id: int):
    item = await inventory_service.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return templates.TemplateResponse(request, "inventory_item.html", {"item": item})


class CreateItemBody(BaseModel):
    name: str
    ip: str | None = None
    faction: str | None = None
    source: str = "manual"
    catalog_item_id: int | None = None
    box_price: float | None = None
    models_per_box: int | None = None
    qty: int = 1
    condition: str = "assembled"
    notes: str | None = None


@router.post("/inventory")
async def create_item(body: CreateItemBody):
    prefix = sku_codes.build_sku_prefix(body.ip, body.faction, body.condition)
    sku = await inventory_service.generate_sku(prefix)
    item_id = await inventory_service.create_item(
        sku=sku,
        name=body.name,
        ip=body.ip,
        faction=body.faction,
        source=body.source,
        catalog_item_id=body.catalog_item_id,
        box_price=body.box_price,
        models_per_box=body.models_per_box,
        qty=body.qty,
        condition=body.condition,
        notes=body.notes,
    )
    item = await inventory_service.get_item(item_id)
    return item.to_dict()


class EditItemBody(BaseModel):
    name: str | None = None
    qty: int | None = None
    condition: str | None = None
    notes: str | None = None


@router.patch("/inventory/{item_id}")
async def edit_item(item_id: int, body: EditItemBody):
    if await inventory_service.get_item(item_id) is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    await inventory_service.edit_item(
        item_id, name=body.name, qty=body.qty, condition=body.condition, notes=body.notes
    )
    item = await inventory_service.get_item(item_id)
    return item.to_dict()


class PricingBody(BaseModel):
    third_party_price: float


@router.post("/inventory/{item_id}/pricing")
async def set_pricing(item_id: int, body: PricingBody):
    if await inventory_service.get_item(item_id) is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    await inventory_service.set_pricing(item_id, body.third_party_price)
    item = await inventory_service.get_item(item_id)
    return item.to_dict()


class StatusBody(BaseModel):
    status: str


@router.post("/inventory/{item_id}/status")
async def set_status(item_id: int, body: StatusBody):
    if await inventory_service.get_item(item_id) is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    await inventory_service.set_status(item_id, body.status)
    item = await inventory_service.get_item(item_id)
    return item.to_dict()


class SoldBody(BaseModel):
    sell_price: float
    date_sold: str | None = None


@router.post("/inventory/{item_id}/sold")
async def mark_sold(item_id: int, body: SoldBody):
    if await inventory_service.get_item(item_id) is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    date_sold = body.date_sold or date.today().isoformat()
    await inventory_service.mark_sold(item_id, body.sell_price, date_sold)
    item = await inventory_service.get_item(item_id)
    return item.to_dict()


@router.delete("/inventory/{item_id}")
async def remove_item(item_id: int):
    if await inventory_service.get_item(item_id) is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    await inventory_service.remove_item(item_id)
    return {"ok": True}


@router.post("/inventory/{item_id}/photos")
async def upload_photos(item_id: int, files: list[UploadFile] = File(...)):
    item = await inventory_service.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    saved = []
    for upload in files:
        try:
            filename, content_type = await photos_service.save_upload(item.sku, upload)
        except photos_service.InvalidPhotoUpload as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        photo_id = await inventory_service.add_photo(item_id, filename, upload.filename, content_type)
        saved.append(photo_id)
    updated = await inventory_service.get_item(item_id)
    return {"photo_ids": saved, "item": updated.to_dict()}


@router.post("/inventory/{item_id}/photos/{photo_id}/primary")
async def set_primary_photo(item_id: int, photo_id: int):
    photo = await inventory_service.get_photo(photo_id)
    if photo is None or photo.inventory_item_id != item_id:
        raise HTTPException(status_code=404, detail="Photo not found on this item")
    await inventory_service.set_primary_photo(item_id, photo_id)
    item = await inventory_service.get_item(item_id)
    return item.to_dict()


@router.delete("/inventory/{item_id}/photos/{photo_id}")
async def remove_photo(item_id: int, photo_id: int):
    photo = await inventory_service.get_photo(photo_id)
    if photo is None or photo.inventory_item_id != item_id:
        raise HTTPException(status_code=404, detail="Photo not found on this item")
    item = await inventory_service.get_item(item_id)
    photos_service.delete_photo_file(item.sku, photo.filename)
    await inventory_service.remove_photo(photo_id)
    updated = await inventory_service.get_item(item_id)
    return updated.to_dict()


@router.post("/inventory/{item_id}/print-label")
async def print_label(item_id: int, dry_run: bool = False, price_override: float | None = None):
    item = await inventory_service.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    photo_path = None
    primary = item.primary_photo
    if primary is not None:
        photo_path = photos_service.photo_path(item.sku, primary.filename)

    zpl = labels_service.build_label_zpl(item, photo_path, price_override)

    if dry_run:
        return JSONResponse({"zpl": zpl})

    os.makedirs(labels_service.OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(labels_service.OUTPUT_DIR, f"{item.sku}.zpl")
    with open(out_path, "w") as f:
        f.write(zpl)

    ok, err = labels_service.send_to_printer(out_path)
    if not ok:
        raise HTTPException(status_code=502, detail=f"Print failed: {err}")
    return {"ok": True}


@router.get("/inventory/export/{platform}")
async def export_platform(platform: str):
    if platform not in exports_service.BUILDERS:
        raise HTTPException(status_code=404, detail=f"Unknown export platform {platform!r}")
    items = [i for i in await inventory_service.list_items() if i.status in ("in_stock", "listed")]
    zip_path = exports_service.write_export(platform, items)
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=zip_path.name,
        headers={
            "X-Export-Note": "Photos are not auto-attached - see photos/ in this archive for a manual upload pass."
        },
    )
