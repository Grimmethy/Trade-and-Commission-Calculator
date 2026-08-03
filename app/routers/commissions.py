from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import catalog as catalog_service
from app import commissions as commissions_service
from app.pricing import compute_painting_totals, derive_per_model_price

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/commissions", response_class=HTMLResponse)
async def commissions_list(request: Request):
    commissions = await commissions_service.list_commissions()
    return templates.TemplateResponse(request, "commissions_list.html", {"commissions": commissions})


@router.post("/commissions")
async def create_commission(painter_name: str = Form(...)):
    commission = await commissions_service.create_commission(painter_name)
    return RedirectResponse(url=f"/commissions/{commission.code}", status_code=303)


@router.get("/commissions/{code}", response_class=HTMLResponse)
async def commission_detail(request: Request, code: str):
    commission = await commissions_service.get_commission(code)
    if commission is None:
        raise HTTPException(status_code=404, detail="Commission not found")
    totals = compute_painting_totals(commission)
    return templates.TemplateResponse(request, "commission_detail.html", {"commission": commission, "totals": totals})


@router.post("/commissions/{code}/rename")
async def rename_commission(code: str, new_name: str = Form(...)):
    commission = await commissions_service.get_commission(code)
    if commission is None:
        raise HTTPException(status_code=404, detail="Commission not found")
    new_code = await commissions_service.rename_commission_code(commission.id, new_name)
    if new_code is None:
        raise HTTPException(status_code=400, detail="That name doesn't produce a usable commission code")
    return RedirectResponse(url=f"/commissions/{new_code}", status_code=303)


@router.post("/commissions/{code}/delete")
async def delete_commission(code: str):
    deleted = await commissions_service.remove_commission(code)
    if not deleted:
        raise HTTPException(status_code=404, detail="Commission not found")
    return RedirectResponse(url="/commissions", status_code=303)


@router.get("/commissions/{code}/print", response_class=HTMLResponse)
async def commission_print(request: Request, code: str):
    commission = await commissions_service.get_commission(code)
    if commission is None:
        raise HTTPException(status_code=404, detail="Commission not found")
    totals = compute_painting_totals(commission)
    return templates.TemplateResponse(request, "commission_print.html", {"commission": commission, "totals": totals})


@router.post("/commissions/{code}/items")
async def add_commission_item_route(
    code: str,
    side: str = Form(...),
    name: str = Form(None),
    qty: int = Form(1),
    unit_price: float = Form(None),
    catalog_item_id: int = Form(None),
):
    commission = await commissions_service.get_commission(code)
    if commission is None:
        raise HTTPException(status_code=404, detail="Commission not found")

    if catalog_item_id is not None:
        catalog_item = await catalog_service.get_catalog_item(catalog_item_id)
        if catalog_item is None:
            raise HTTPException(status_code=404, detail="Catalog item not found")
        box_price = catalog_item.box_price
        models_per_box = catalog_item.models_per_box
        if unit_price is None:
            unit_price = derive_per_model_price(box_price, models_per_box) if models_per_box else box_price
        name = catalog_item.item_name
        source = "catalog"
    else:
        source = "manual"
        box_price = None
        models_per_box = None
        if not name or unit_price is None:
            raise HTTPException(status_code=400, detail="name and unit_price are required for a manual item")

    await commissions_service.add_commission_item(
        commission.id, side, name, qty, unit_price, source, catalog_item_id, box_price, models_per_box
    )
    return RedirectResponse(url=f"/commissions/{code}", status_code=303)


@router.post("/commissions/{code}/items/{item_id}/delete")
async def delete_commission_item(code: str, item_id: int):
    await commissions_service.remove_commission_item(item_id)
    return RedirectResponse(url=f"/commissions/{code}", status_code=303)


@router.post("/commissions/{code}/items/{item_id}/verify")
async def verify_commission_item(code: str, item_id: int, verified: bool = Form(False), note: str = Form(None)):
    await commissions_service.set_item_verification(item_id, verified, note)
    return RedirectResponse(url=f"/commissions/{code}", status_code=303)


@router.post("/commissions/{code}/status")
async def update_commission_status(code: str, status: str = Form(...)):
    commission = await commissions_service.get_commission(code)
    if commission is None:
        raise HTTPException(status_code=404, detail="Commission not found")
    await commissions_service.set_commission_status(commission.id, status)
    return RedirectResponse(url=f"/commissions/{code}", status_code=303)


@router.post("/commissions/{code}/settings")
async def update_commission_settings(
    code: str, painter_name: str = Form(...), commission_rate: float = Form(...), cash_amount: float = Form(...)
):
    commission = await commissions_service.get_commission(code)
    if commission is None:
        raise HTTPException(status_code=404, detail="Commission not found")
    await commissions_service.set_painter_name(commission.id, painter_name)
    await commissions_service.set_commission_rate(commission.id, commission_rate / 100)
    await commissions_service.set_cash_amount(commission.id, cash_amount)
    return RedirectResponse(url=f"/commissions/{code}", status_code=303)
