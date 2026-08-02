from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import catalog as catalog_service

router = APIRouter()


class ModelsPerBoxUpdate(BaseModel):
    models_per_box: int = Field(gt=0)


@router.get("/catalog/ips")
async def ips():
    return {"ips": await catalog_service.list_ips()}


@router.get("/catalog/factions")
async def factions(ip: str):
    return {"factions": await catalog_service.list_factions(ip)}


@router.get("/catalog/units")
async def units(ip: str, faction: str):
    items = await catalog_service.list_units(ip, faction)
    return {"units": [i.to_dict() for i in items]}


@router.patch("/catalog/units/{catalog_item_id}/models-per-box")
async def set_models_per_box(catalog_item_id: int, body: ModelsPerBoxUpdate):
    catalog_item = await catalog_service.get_catalog_item(catalog_item_id)
    if catalog_item is None:
        raise HTTPException(status_code=404, detail="Catalog item not found")
    await catalog_service.set_models_per_box(catalog_item_id, body.models_per_box)
    updated = await catalog_service.get_catalog_item(catalog_item_id)
    return updated.to_dict()


@router.get("/catalog/kit-size-gaps")
async def kit_size_gaps():
    """Items someone has tried to trade with an unknown kit size, queued for the
    next browser-assisted scrape pass — ranked by how often people have hit it."""
    return {"gaps": await catalog_service.list_kit_size_gaps()}


@router.get("/catalog/search")
async def search(q: str = ""):
    if not q or len(q) < 2:
        return {"results": []}
    items = await catalog_service.search_catalog(q)
    return {"results": [i.to_dict() for i in items]}
