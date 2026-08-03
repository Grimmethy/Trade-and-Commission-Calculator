from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import rooms as rooms_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "home.html")


@router.post("/rooms")
async def create_room():
    room = await rooms_service.create_room()
    return RedirectResponse(url=f"/trade/{room.code}", status_code=303)


@router.get("/trade/{code}", response_class=HTMLResponse)
async def trade_room(request: Request, code: str):
    room = await rooms_service.get_room(code)
    if room is None:
        raise HTTPException(status_code=404, detail="Trade room not found")
    return templates.TemplateResponse(
        request, "trade_room.html", {"room_code": code}
    )


@router.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    rooms = await rooms_service.list_rooms()
    return templates.TemplateResponse(request, "history.html", {"rooms": rooms})


@router.post("/rooms/{code}/rename")
async def rename_room(code: str, new_name: str = Form(...)):
    room = await rooms_service.get_room(code)
    if room is None:
        raise HTTPException(status_code=404, detail="Trade room not found")
    new_code = await rooms_service.rename_room_code(room.id, new_name)
    if new_code is None:
        raise HTTPException(status_code=400, detail="That name doesn't produce a usable room code")
    return RedirectResponse(url=f"/trade/{new_code}", status_code=303)


@router.post("/rooms/{code}/delete")
async def delete_room(code: str):
    deleted = await rooms_service.remove_room(code)
    if not deleted:
        raise HTTPException(status_code=404, detail="Trade room not found")
    return RedirectResponse(url="/history", status_code=303)
