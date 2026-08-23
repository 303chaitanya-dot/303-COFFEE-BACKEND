from collections.abc import Generator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, configure_database
from app.models import Item, MenuItem, RecipeLine, Supplier
from app.services.ledger import ensure_chart_of_accounts


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, future=True)

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()
    ensure_chart_of_accounts(session)
    yield session
    session.close()


@pytest.fixture
def cafe(db: Session) -> dict:
    supplier = Supplier(name="Test Roaster")
    beans = Item(sku="BEAN", name="Espresso beans", category="coffee", unit="g", reorder_point=100)
    milk = Item(sku="MILK", name="Milk", category="dairy", unit="ml", reorder_point=500)
    cup = Item(sku="CUP", name="Cup", category="packaging", unit="pcs", reorder_point=10)
    db.add_all([supplier, beans, milk, cup])
    db.flush()
    latte = MenuItem(name="Latte", category="espresso", price=Decimal("220.00"), active=True)
    db.add(latte)
    db.flush()
    db.add_all(
        [
            RecipeLine(menu_item_id=latte.id, item_id=beans.id, quantity=Decimal("18")),
            RecipeLine(menu_item_id=latte.id, item_id=milk.id, quantity=Decimal("220")),
            RecipeLine(menu_item_id=latte.id, item_id=cup.id, quantity=Decimal("1")),
        ]
    )
    db.flush()
    return {"supplier": supplier, "beans": beans, "milk": milk, "cup": cup, "latte": latte}


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    configure_database(f"sqlite:///{tmp_path / 'test.db'}")
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
