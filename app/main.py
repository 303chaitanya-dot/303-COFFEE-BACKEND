from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db as database
from app.auth import ensure_admin_user, get_current_user
from app.config import settings
from app.models import ItemCategory, MenuCategory, PaymentMethod, Unit
from app.routers import auth, bills, catalog, operations, petpooja, recipes, reports, sheets
from app.schemas import MetaOut
from app.migrate import ensure_columns
from app.seed import seed_if_empty

STATIC_DIR = Path(__file__).resolve().parent / "static"
AUTH = [Depends(get_current_user)]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        database.Base.metadata.create_all(bind=database.engine)
        ensure_columns(database.engine)
        db = database.SessionLocal()
        try:
            seed_if_empty(db)
            ensure_admin_user(db)
        finally:
            db.close()
    except Exception as exc:
        print(f"startup migration warning: {exc}")
    yield


app = FastAPI(title=f"{settings.app_name} Inventory", lifespan=lifespan)
app.include_router(auth.router, prefix="/api")
app.include_router(catalog.router, prefix="/api", dependencies=AUTH)
app.include_router(recipes.router, prefix="/api", dependencies=AUTH)
app.include_router(operations.router, prefix="/api", dependencies=AUTH)
app.include_router(reports.router, prefix="/api", dependencies=AUTH)
app.include_router(bills.router, prefix="/api", dependencies=AUTH)
app.include_router(petpooja.router, prefix="/api")
app.include_router(sheets.router, prefix="/api", dependencies=AUTH)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/meta", response_model=MetaOut, dependencies=AUTH)
def meta() -> MetaOut:
    return MetaOut(
        app_name=settings.app_name,
        currency_code=settings.currency_code,
        currency_symbol=settings.currency_symbol,
        item_categories=[item.value for item in ItemCategory],
        menu_categories=[item.value for item in MenuCategory],
        units=[item.value for item in Unit],
        payment_methods=[item.value for item in PaymentMethod],
        roles=["owner", "manager", "staff"],
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.png")
