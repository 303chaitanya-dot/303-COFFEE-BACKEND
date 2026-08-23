import csv
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import InventorySheet, Item, MenuCategory, MenuItem, RecipeLine, utcnow
from app.services.inventory import upsert_named_item
from app.services.ledger import money

HEADER_ALIASES = {
    "name": {"name", "item", "item name", "product"},
    "category": {"category"},
    "unit": {"unit", "stock unit", "stock"},
    "qty_per_unit": {"qty per unit", "qty_per_unit", "pack", "pack size", "qty/unit"},
    "units_on_hand": {"units", "units on hand", "units_on_hand", "bottles", "packs"},
    "price": {"price", "total price", "total spent", "amount"},
    "serving_size": {"serving", "serving size", "serving_size"},
    "serving_unit": {"serving unit", "serving_unit"},
    "reorder_point": {"reorder", "reorder point", "reorder_point"},
    "expiry_date": {"expiry", "expiry date", "expires", "expiry_date"},
}

TEMPLATE_HEADERS = [
    "name",
    "category",
    "unit",
    "qty_per_unit",
    "units_on_hand",
    "price",
    "serving_size",
    "serving_unit",
    "reorder_point",
    "expiry",
]


def sheet_export_url(raw: str) -> str:
    url = (raw or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="Paste a Google Sheet link")
    if "output=csv" in url or "export?format=csv" in url or "tqx=out:csv" in url:
        return url
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        raise HTTPException(status_code=400, detail="That does not look like a Google Sheet link")
    sheet_id = match.group(1)
    gid_match = re.search(r"[#&?]gid=([0-9]+)", url)
    gid = gid_match.group(1) if gid_match else "0"
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def map_headers(headers: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for index, header in enumerate(headers):
        label = _norm(header)
        for field, aliases in HEADER_ALIASES.items():
            if label in aliases and field not in found:
                found[field] = index
    if "name" not in found:
        raise HTTPException(
            status_code=400,
            detail="The sheet needs a Name column. Use: name, category, unit, qty_per_unit, units_on_hand, price, serving_size, serving_unit, reorder_point, expiry",
        )
    return found


def parse_expiry(value: str) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", raw)
    if iso:
        return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    indian = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$", raw)
    if indian:
        day, month, year = int(indian.group(1)), int(indian.group(2)), int(indian.group(3))
        return date(year, month, day)
    raise ValueError("expiry should look like 23/08/2026")


def parse_number(value: str, default: str = "0") -> Decimal:
    raw = (value or "").strip().replace(",", "").replace("₹", "")
    if not raw:
        raw = default
    try:
        return Decimal(raw)
    except InvalidOperation as error:
        raise ValueError(f"not a number: {value}") from error


def parse_sheet_csv(text: str) -> list[dict]:
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="The sheet is empty")
    mapping = map_headers(rows[0])
    parsed = []
    for number, raw in enumerate(rows[1:], start=2):
        if not raw or not any(cell.strip() for cell in raw):
            continue

        def cell(field: str, default: str = "") -> str:
            index = mapping.get(field)
            if index is None or index >= len(raw):
                return default
            return raw[index].strip()

        name = cell("name")
        if not name:
            continue
        try:
            parsed.append(
                {
                    "name": name,
                    "category": cell("category", "other") or "other",
                    "unit": cell("unit", "pcs") or "pcs",
                    "qty_per_unit": parse_number(cell("qty_per_unit"), "1"),
                    "units_on_hand": parse_number(cell("units_on_hand"), "0"),
                    "price": parse_number(cell("price"), "0"),
                    "serving_size": parse_number(cell("serving_size"), "1"),
                    "serving_unit": cell("serving_unit") or None,
                    "reorder_point": parse_number(cell("reorder_point"), "0"),
                    "expiry_date": parse_expiry(cell("expiry_date")),
                    "row": number,
                }
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=f"Row {number} ({name}): {error}") from error
    if not parsed:
        raise HTTPException(status_code=400, detail="No item rows found under the header")
    return parsed


def fetch_sheet_csv(url: str) -> str:
    export = sheet_export_url(url)
    try:
        response = httpx.get(export, follow_redirects=True, timeout=20.0)
    except httpx.HTTPError as error:
        raise HTTPException(status_code=400, detail="Could not reach Google Sheets") from error
    content_type = response.headers.get("content-type", "")
    body = response.text
    if response.status_code >= 400 or "text/html" in content_type or body.lstrip().startswith("<"):
        raise HTTPException(
            status_code=400,
            detail="Could not read the sheet. In Google Sheets: Share → Anyone with the link → Viewer.",
        )
    return body


def get_or_create_sheet(db: Session, kind: str = "inventory") -> InventorySheet:
    sheet = db.scalar(select(InventorySheet).where(InventorySheet.kind == kind))
    if sheet:
        return sheet
    sheet = InventorySheet(kind=kind, url="")
    db.add(sheet)
    db.flush()
    return sheet


def save_sheet_url(db: Session, url: str, kind: str = "inventory") -> InventorySheet:
    sheet_export_url(url)
    sheet = get_or_create_sheet(db, kind)
    sheet.url = url.strip()
    db.commit()
    db.refresh(sheet)
    return sheet


def _finish_sync(db: Session, sheet: InventorySheet, source: str, created: int, updated: int, errors: list[str]) -> dict:
    sheet.url = source
    sheet.last_synced_at = utcnow()
    if errors and not created and not updated:
        db.rollback()
        raise HTTPException(status_code=400, detail=errors[0])
    sheet.last_message = f"Added {created}, updated {updated}" + (f", {len(errors)} skipped" if errors else "")
    db.commit()
    return {
        "created": created,
        "updated": updated,
        "skipped": len(errors),
        "errors": errors[:8],
        "last_synced_at": sheet.last_synced_at,
        "last_message": sheet.last_message,
        "url": sheet.url,
    }


def sync_sheet(db: Session, url: str | None = None, kind: str = "inventory") -> dict:
    sheet = get_or_create_sheet(db, kind)
    source = (url or sheet.url or "").strip()
    if not source:
        raise HTTPException(status_code=400, detail="Link a Google Sheet first")
    rows = parse_sheet_csv(fetch_sheet_csv(source))
    created = updated = 0
    errors: list[str] = []
    for row in rows:
        try:
            _item, action = upsert_named_item(db, row)
            if action == "created":
                created += 1
            else:
                updated += 1
        except HTTPException as error:
            errors.append(f"Row {row['row']} ({row['name']}): {error.detail}")
    return _finish_sync(db, sheet, source, created, updated, errors)


def current_sheet(db: Session, kind: str = "inventory") -> InventorySheet | None:
    return db.scalar(select(InventorySheet).where(InventorySheet.kind == kind))


MENU_HEADER_ALIASES = {
    "dish": {"dish", "menu", "menu item", "item", "name", "product"},
    "category": {"category", "menu category"},
    "price": {"price", "sell price", "selling price", "mrp"},
    "ingredient": {"ingredient", "stock item", "raw", "item name"},
    "qty": {"qty", "quantity", "amount", "recipe qty"},
    "unit": {"unit", "ingredient unit"},
}

MENU_TEMPLATE_HEADERS = ["dish", "category", "price", "ingredient", "qty", "unit"]


def map_named_headers(headers: list[str], aliases: dict[str, set[str]], required: str, hint: str) -> dict[str, int]:
    found: dict[str, int] = {}
    for index, header in enumerate(headers):
        label = _norm(header)
        for field, names in aliases.items():
            if label in names and field not in found:
                found[field] = index
    if required not in found:
        raise HTTPException(status_code=400, detail=hint)
    return found


def parse_menu_csv(text: str) -> list[dict]:
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="The menu sheet is empty")
    mapping = map_named_headers(
        rows[0],
        MENU_HEADER_ALIASES,
        "dish",
        "The menu sheet needs a Dish column. Use: dish, category, price, ingredient, qty, unit",
    )
    if "ingredient" not in mapping or "qty" not in mapping:
        raise HTTPException(status_code=400, detail="The menu sheet needs ingredient and qty columns")
    parsed = []
    for number, raw in enumerate(rows[1:], start=2):
        if not raw or not any(cell.strip() for cell in raw):
            continue

        def cell(field: str, default: str = "") -> str:
            index = mapping.get(field)
            if index is None or index >= len(raw):
                return default
            return raw[index].strip()

        dish = cell("dish")
        ingredient = cell("ingredient")
        if not dish or not ingredient:
            continue
        parsed.append(
            {
                "dish": dish,
                "category": cell("category", "other") or "other",
                "price": parse_number(cell("price"), "0"),
                "ingredient": ingredient,
                "qty": parse_number(cell("qty"), "0"),
                "unit": (cell("unit") or "").lower() or None,
                "row": number,
            }
        )
    if not parsed:
        raise HTTPException(status_code=400, detail="No recipe rows found under the header")
    return parsed


def upsert_menu_from_rows(db: Session, rows: list[dict]) -> tuple[int, int, list[str]]:
    grouped: dict[str, dict] = {}
    errors: list[str] = []
    for row in rows:
        if row["qty"] <= 0:
            errors.append(f"Row {row['row']} ({row['dish']}): qty must be greater than zero")
            continue
        ingredient = db.scalar(select(Item).where(func.lower(Item.name) == row["ingredient"].lower()))
        if ingredient is None:
            errors.append(f"Row {row['row']}: '{row['ingredient']}' is not in inventory yet")
            continue
        key = row["dish"].strip().lower()
        dish = grouped.setdefault(
            key,
            {"name": row["dish"].strip(), "category": row["category"], "price": row["price"], "lines": []},
        )
        if row["price"]:
            dish["price"] = row["price"]
        if row["category"]:
            dish["category"] = row["category"]
        dish["lines"].append((ingredient, row["qty"], row["unit"] or ingredient.unit))
    created = updated = 0
    allowed = {item.value for item in MenuCategory}
    for dish in grouped.values():
        if not dish["lines"]:
            continue
        category = dish["category"].strip().lower().replace(" ", "_")
        if category not in allowed:
            category = "other"
        menu_item = db.scalar(
            select(MenuItem)
            .options(selectinload(MenuItem.recipe_lines))
            .where(func.lower(MenuItem.name) == dish["name"].lower())
        )
        if menu_item is None:
            menu_item = MenuItem(name=dish["name"], category=category, price=money(dish["price"]), active=True)
            db.add(menu_item)
            db.flush()
            created += 1
        else:
            menu_item.category = category
            menu_item.price = money(dish["price"])
            menu_item.recipe_lines.clear()
            db.flush()
            updated += 1
        for ingredient, quantity, unit in dish["lines"]:
            db.add(
                RecipeLine(
                    menu_item_id=menu_item.id,
                    item_id=ingredient.id,
                    quantity=quantity,
                    unit=unit,
                )
            )
    return created, updated, errors


def sync_menu_sheet(db: Session, url: str | None = None) -> dict:
    sheet = get_or_create_sheet(db, "menu")
    source = (url or sheet.url or "").strip()
    if not source:
        raise HTTPException(status_code=400, detail="Link a menu Google Sheet first")
    rows = parse_menu_csv(fetch_sheet_csv(source))
    created, updated, errors = upsert_menu_from_rows(db, rows)
    return _finish_sync(db, sheet, source, created, updated, errors)
