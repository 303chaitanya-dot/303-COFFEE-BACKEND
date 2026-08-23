from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import SheetLinkIn, SheetLinkOut, SheetSyncIn, SheetSyncOut
from app.services.recipe_book import MASTER_SHEET_URL, import_recipe_book
from app.services.sheets import (
    MENU_TEMPLATE_HEADERS,
    TEMPLATE_HEADERS,
    current_sheet,
    save_sheet_url,
    sync_menu_sheet,
    sync_sheet,
)

router = APIRouter()


@router.get("/sheet", response_model=SheetLinkOut)
def get_sheet(db: Session = Depends(get_db)) -> SheetLinkOut:
    sheet = current_sheet(db)
    if sheet is None:
        return SheetLinkOut(url="", last_synced_at=None, last_message=None)
    return SheetLinkOut(url=sheet.url, last_synced_at=sheet.last_synced_at, last_message=sheet.last_message)


@router.put("/sheet", response_model=SheetLinkOut)
def link_sheet(payload: SheetLinkIn, db: Session = Depends(get_db)) -> SheetLinkOut:
    sheet = save_sheet_url(db, payload.url)
    return SheetLinkOut(url=sheet.url, last_synced_at=sheet.last_synced_at, last_message=sheet.last_message)


@router.post("/sheet/sync", response_model=SheetSyncOut)
def run_sheet_sync(payload: SheetSyncIn | None = None, db: Session = Depends(get_db)) -> SheetSyncOut:
    result = sync_sheet(db, payload.url if payload and payload.url else None)
    return SheetSyncOut(**result)


@router.get("/menu-sheet", response_model=SheetLinkOut)
def get_menu_sheet(db: Session = Depends(get_db)) -> SheetLinkOut:
    sheet = current_sheet(db, "menu")
    if sheet is None:
        return SheetLinkOut(url="", last_synced_at=None, last_message=None)
    return SheetLinkOut(url=sheet.url, last_synced_at=sheet.last_synced_at, last_message=sheet.last_message)


@router.put("/menu-sheet", response_model=SheetLinkOut)
def link_menu_sheet(payload: SheetLinkIn, db: Session = Depends(get_db)) -> SheetLinkOut:
    sheet = save_sheet_url(db, payload.url, "menu")
    return SheetLinkOut(url=sheet.url, last_synced_at=sheet.last_synced_at, last_message=sheet.last_message)


@router.post("/menu-sheet/sync", response_model=SheetSyncOut)
def run_menu_sheet_sync(payload: SheetSyncIn | None = None, db: Session = Depends(get_db)) -> SheetSyncOut:
    result = sync_menu_sheet(db, payload.url if payload and payload.url else None)
    return SheetSyncOut(**result)


@router.get("/menu-sheet/template")
def menu_sheet_template() -> PlainTextResponse:
    return PlainTextResponse(
        ",".join(MENU_TEMPLATE_HEADERS)
        + "\nLatte,espresso,220,Espresso beans,18,g\nLatte,espresso,220,Whole milk,200,ml\n",
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=303-menu-sheet.csv"},
    )


@router.get("/recipe-book", response_model=SheetLinkOut)
def get_recipe_book(db: Session = Depends(get_db)) -> SheetLinkOut:
    sheet = current_sheet(db, "recipe_book")
    if sheet is None:
        return SheetLinkOut(url=MASTER_SHEET_URL, last_synced_at=None, last_message=None)
    return SheetLinkOut(
        url=sheet.url or MASTER_SHEET_URL,
        last_synced_at=sheet.last_synced_at,
        last_message=sheet.last_message,
    )


@router.put("/recipe-book", response_model=SheetLinkOut)
def link_recipe_book(payload: SheetLinkIn, db: Session = Depends(get_db)) -> SheetLinkOut:
    sheet = save_sheet_url(db, payload.url, "recipe_book")
    return SheetLinkOut(url=sheet.url, last_synced_at=sheet.last_synced_at, last_message=sheet.last_message)


@router.post("/recipe-book/sync", response_model=SheetSyncOut)
def run_recipe_book_sync(payload: SheetSyncIn | None = None, db: Session = Depends(get_db)) -> SheetSyncOut:
    result = import_recipe_book(db, payload.url if payload and payload.url else None)
    return SheetSyncOut(**result)


@router.get("/sheet/template")
def sheet_template() -> PlainTextResponse:
    return PlainTextResponse(
        ",".join(TEMPLATE_HEADERS)
        + "\nSoy sauce,dry_goods,ml,250,4,200,15,ml,2,23/08/2028\nChicken,produce,kg,1,3,600,120,g,1,\n",
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=303-inventory-sheet.csv"},
    )
