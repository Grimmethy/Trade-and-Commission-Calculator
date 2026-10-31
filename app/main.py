from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.db import lifespan
from app import mode
from app.routers import catalog, commissions, gaps, inventory_link, rooms, ws

app = FastAPI(title="Trade Calculator", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(rooms.router)
app.include_router(ws.router)
app.include_router(catalog.router)
app.include_router(gaps.router)
app.include_router(commissions.router)
# The in-app inventory was removed: the inventory plugin is the one inventory system (private mode reads it, see inventory_link).
if mode.MODE == "private":
    app.include_router(inventory_link.router)

_limiter = mode.RoomLimiter()


@app.middleware("http")
async def gate(request: Request, call_next):
    if mode.MODE == "public":
        if not mode.public_allows(request.method, request.url.path):
            return PlainTextResponse("Not found", status_code=404)
        if request.method == "POST" and request.url.path == "/rooms":
            who = mode.client_ip(request.headers, request.client.host if request.client else None)
            if not _limiter.allow(who):
                return PlainTextResponse("Too many new trades from this connection; try again later.", status_code=429)
    resp = await call_next(request)
    if mode.MODE == "public":
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
    return resp


@app.get("/healthz")
async def healthz():
    return {"ok": True, "mode": mode.MODE}


@app.get("/manifest.webmanifest")
async def manifest():
    return JSONResponse({
        "name": "Screaming Goat Trade Calculator", "short_name": "Trade Calc", "start_url": "/", "scope": "/",
        "display": "standalone", "background_color": "#111111", "theme_color": "#111111",
        "icons": [{"src": "/static/branding/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/static/branding/icon-512.png", "sizes": "512x512", "type": "image/png"}]},
        media_type="application/manifest+json")


@app.get("/sw.js")
async def service_worker():
    # Network-first; the app is live-synced so nothing is cached for offline use. The worker exists so phones offer "install".
    return FileResponse("app/static/sw.js", media_type="application/javascript")
