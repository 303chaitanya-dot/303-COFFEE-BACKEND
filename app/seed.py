from sqlalchemy.orm import Session

from app.services.ledger import ensure_chart_of_accounts


def seed_if_empty(db: Session) -> None:
    ensure_chart_of_accounts(db)
    db.commit()
