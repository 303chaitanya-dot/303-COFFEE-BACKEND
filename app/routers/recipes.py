from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Item, MenuCategory, MenuItem, RecipeLine, Sauce, SauceLine
from app.presenters import present_menu_item, present_sauce
from app.schemas import MenuItemIn, MenuItemOut, SauceIn, SauceOut

router = APIRouter()


def _replace_sauce_recipe(db: Session, sauce: Sauce, recipe: list) -> None:
    sauce.lines.clear()
    db.flush()
    for line in recipe:
        if db.get(Item, line.item_id) is None:
            raise HTTPException(status_code=400, detail="Ingredient not found")
        db.add(SauceLine(sauce_id=sauce.id, item_id=line.item_id, quantity=line.quantity))


def _replace_dish_recipe(db: Session, menu_item: MenuItem, recipe: list) -> None:
    menu_item.recipe_lines.clear()
    db.flush()
    for line in recipe:
        if line.sauce_id and db.get(Sauce, line.sauce_id) is None:
            raise HTTPException(status_code=400, detail="Sauce not found")
        if line.item_id and db.get(Item, line.item_id) is None:
            raise HTTPException(status_code=400, detail="Ingredient not found")
        db.add(
            RecipeLine(
                menu_item_id=menu_item.id,
                item_id=line.item_id,
                sauce_id=line.sauce_id,
                quantity=line.quantity,
            )
        )


@router.get("/sauces", response_model=list[SauceOut])
def list_sauces(db: Session = Depends(get_db)) -> list[SauceOut]:
    rows = db.scalars(select(Sauce).options(selectinload(Sauce.lines)).order_by(Sauce.name)).all()
    return [present_sauce(db, row) for row in rows]


@router.post("/sauces", response_model=SauceOut, status_code=201)
def create_sauce(payload: SauceIn, db: Session = Depends(get_db)) -> SauceOut:
    if db.scalar(select(Sauce).where(Sauce.name == payload.name)):
        raise HTTPException(status_code=409, detail="Sauce already exists")
    sauce = Sauce(name=payload.name, active=payload.active)
    db.add(sauce)
    db.flush()
    _replace_sauce_recipe(db, sauce, payload.recipe)
    db.commit()
    sauce = db.scalar(select(Sauce).options(selectinload(Sauce.lines)).where(Sauce.id == sauce.id))
    return present_sauce(db, sauce)


@router.put("/sauces/{sauce_id}", response_model=SauceOut)
def update_sauce(sauce_id: int, payload: SauceIn, db: Session = Depends(get_db)) -> SauceOut:
    sauce = db.scalar(select(Sauce).options(selectinload(Sauce.lines)).where(Sauce.id == sauce_id))
    if sauce is None:
        raise HTTPException(status_code=404, detail="Sauce not found")
    sauce.name = payload.name
    sauce.active = payload.active
    _replace_sauce_recipe(db, sauce, payload.recipe)
    db.commit()
    sauce = db.scalar(select(Sauce).options(selectinload(Sauce.lines)).where(Sauce.id == sauce_id))
    return present_sauce(db, sauce)


@router.get("/menu", response_model=list[MenuItemOut])
def list_menu(db: Session = Depends(get_db)) -> list[MenuItemOut]:
    rows = db.scalars(
        select(MenuItem).options(selectinload(MenuItem.recipe_lines)).order_by(MenuItem.category, MenuItem.name)
    ).all()
    return [present_menu_item(db, row) for row in rows]


@router.post("/menu", response_model=MenuItemOut, status_code=201)
def create_menu_item(payload: MenuItemIn, db: Session = Depends(get_db)) -> MenuItemOut:
    if payload.category not in {item.value for item in MenuCategory}:
        raise HTTPException(status_code=400, detail="Invalid menu category")
    if db.scalar(select(MenuItem).where(MenuItem.name == payload.name)):
        raise HTTPException(status_code=409, detail="Menu item already exists")
    menu_item = MenuItem(name=payload.name, category=payload.category, price=payload.price, active=payload.active)
    db.add(menu_item)
    db.flush()
    _replace_dish_recipe(db, menu_item, payload.recipe)
    db.commit()
    menu_item = db.scalar(select(MenuItem).options(selectinload(MenuItem.recipe_lines)).where(MenuItem.id == menu_item.id))
    return present_menu_item(db, menu_item)


@router.put("/menu/{menu_item_id}", response_model=MenuItemOut)
def update_menu_item(menu_item_id: int, payload: MenuItemIn, db: Session = Depends(get_db)) -> MenuItemOut:
    menu_item = db.scalar(
        select(MenuItem).options(selectinload(MenuItem.recipe_lines)).where(MenuItem.id == menu_item_id)
    )
    if menu_item is None:
        raise HTTPException(status_code=404, detail="Menu item not found")
    if payload.category not in {item.value for item in MenuCategory}:
        raise HTTPException(status_code=400, detail="Invalid menu category")
    menu_item.name = payload.name
    menu_item.category = payload.category
    menu_item.price = payload.price
    menu_item.active = payload.active
    _replace_dish_recipe(db, menu_item, payload.recipe)
    db.commit()
    menu_item = db.scalar(select(MenuItem).options(selectinload(MenuItem.recipe_lines)).where(MenuItem.id == menu_item_id))
    return present_menu_item(db, menu_item)
