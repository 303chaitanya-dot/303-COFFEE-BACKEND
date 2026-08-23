from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import (
    AppFlag,
    BillUpload,
    Item,
    JournalEntry,
    JournalLine,
    MenuItem,
    PetPoojaMapping,
    PetPoojaOrder,
    Purchase,
    PurchaseLine,
    RecipeLine,
    Sale,
    SaleLine,
    Sauce,
    SauceLine,
    StockMovement,
    Supplier,
    WasteEvent,
)
from app.services.ledger import ensure_chart_of_accounts


def wipe_operational_data(db: Session) -> None:
    if db.get(AppFlag, "sample_wiped"):
        return
    for model in (
        BillUpload,
        PetPoojaOrder,
        PetPoojaMapping,
        WasteEvent,
        SaleLine,
        Sale,
        PurchaseLine,
        Purchase,
        JournalLine,
        JournalEntry,
        StockMovement,
        RecipeLine,
        SauceLine,
        Sauce,
        MenuItem,
        Item,
        Supplier,
    ):
        db.execute(delete(model))
    db.add(AppFlag(key="sample_wiped", value="1"))
    db.commit()


def seed_if_empty(db: Session) -> None:
    wipe_operational_data(db)
    ensure_chart_of_accounts(db)
    db.commit()
