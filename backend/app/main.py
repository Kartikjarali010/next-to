import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import services
from .core import AppError
from .db import connect, init_db
from .routers import admin, auth, consumer, merchant

log = logging.getLogger("nextto")
DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


async def _scheduler():
    """Scheduled jobs: expire unpaid reservations / ended deals / old vouchers; reconcile lost webhooks."""
    n = 0
    while True:
        await asyncio.sleep(30)
        n += 1
        try:
            conn = connect()
            try:
                services.expire_pending(conn)
                if n % 10 == 0:
                    services.reconcile(conn)
            finally:
                conn.close()
        except Exception:  # never let the job loop die
            log.exception("scheduler error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = connect()
    init_db(conn)
    if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0:
        from .seed import seed
        seed(conn)
    conn.close()
    task = asyncio.create_task(_scheduler())
    yield
    task.cancel()


app = FastAPI(title="NextTo API", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for r in (auth.router, consumer.router, merchant.router, admin.router):
    app.include_router(r)


@app.exception_handler(AppError)
async def app_error(_: Request, e: AppError):
    return JSONResponse(status_code=e.status, content={"error": {"code": e.code, "message": e.message}})


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, e: RequestValidationError):
    first = e.errors()[0] if e.errors() else {}
    loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": f"{loc}: {first.get('msg', 'invalid')}".strip(": ")}})


@app.get("/api/health")
def health():
    return {"status": "ok"}


if DIST.exists():  # serve the built React app (single origin: nicer for phones on the LAN)
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        f = DIST / full_path
        if full_path and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
