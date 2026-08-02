from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import lifespan
from app.routers import catalog, gaps, rooms, ws

app = FastAPI(title="Trade Calculator", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(rooms.router)
app.include_router(ws.router)
app.include_router(catalog.router)
app.include_router(gaps.router)
