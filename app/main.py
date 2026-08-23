from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db as database
from app.config import settings
from app.models import ItemCategory, MenuCategory, PaymentMethod, Unit
from app.routers import catalog, operations, reports
from app.schemas import MetaOut
from app.seed import seed_if_empty

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    database.Base.metadata.create_all(bind=database.engine)
    db = database.SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(title=f"{settings.app_name} Inventory", lifespan=lifespan)
app.include_router(catalog.router, prefix="/api")
app.include_router(operations.router, prefix="/api")
app.include_router(reports.router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/meta", response_model=MetaOut)
def meta() -> MetaOut:
    return MetaOut(
        app_name=settings.app_name,
        currency_code=settings.currency_code,
        currency_symbol=settings.currency_symbol,
        item_categories=[item.value for item in ItemCategory],
        menu_categories=[item.value for item in MenuCategory],
        units=[item.value for item in Unit],
        payment_methods=[item.value for item in PaymentMethod],
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
