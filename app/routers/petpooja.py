from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.config import settings
from app.db import get_db
from app.models import MenuItem, PetPoojaMapping, PetPoojaOrder, User
from app.presenters import present_mapping, present_petpooja_order
from app.schemas import PetPoojaMapIn, PetPoojaMapOut, PetPoojaOrderOut
from app.services.petpooja import ingest_order

router = APIRouter()


def _check_secret(secret: str | None) -> None:
    if settings.petpooja_webhook_secret and secret != settings.petpooja_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid Pet Pooja secret")


@router.post("/integrations/petpooja/orders", response_model=PetPoojaOrderOut)
def receive_petpooja_order(
    payload: dict,
    db: Session = Depends(get_db),
    x_petpooja_secret: str | None = Header(default=None),
) -> PetPoojaOrderOut:
    _check_secret(x_petpooja_secret)
    record = ingest_order(db, payload)
    db.commit()
    db.refresh(record)
    return present_petpooja_order(record)


@router.get("/petpooja/orders", response_model=list[PetPoojaOrderOut])
def list_petpooja_orders(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[PetPoojaOrderOut]:
    rows = db.scalars(select(PetPoojaOrder).order_by(PetPoojaOrder.created_at.desc())).all()
    return [present_petpooja_order(row) for row in rows]


@router.get("/petpooja/mappings", response_model=list[PetPoojaMapOut])
def list_mappings(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[PetPoojaMapOut]:
    rows = db.scalars(select(PetPoojaMapping).options(selectinload(PetPoojaMapping.menu_item))).all()
    return [present_mapping(row) for row in rows]


@router.post("/petpooja/mappings", response_model=PetPoojaMapOut, status_code=201)
def create_mapping(
    payload: PetPoojaMapIn, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> PetPoojaMapOut:
    if db.get(MenuItem, payload.menu_item_id) is None:
        raise HTTPException(status_code=404, detail="Menu item not found")
    mapping = PetPoojaMapping(
        external_item_id=payload.external_item_id,
        external_name=payload.external_name,
        menu_item_id=payload.menu_item_id,
    )
    db.add(mapping)
    db.commit()
    mapping = db.scalar(
        select(PetPoojaMapping).options(selectinload(PetPoojaMapping.menu_item)).where(PetPoojaMapping.id == mapping.id)
    )
    return present_mapping(mapping)
