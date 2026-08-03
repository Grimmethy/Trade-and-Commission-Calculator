from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import lifespan
from app.photos import PHOTOS_DIR
from app.routers import catalog, gaps, inventory, rooms, ws

app = FastAPI(title="Trade Calculator", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/photos", StaticFiles(directory=str(PHOTOS_DIR)), name="photos")

app.include_router(rooms.router)
app.include_router(ws.router)
app.include_router(catalog.router)
app.include_router(gaps.router)
app.include_router(inventory.router)
