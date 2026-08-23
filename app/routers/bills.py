import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import BillUpload, User
from app.presenters import present_bill
from app.schemas import BillOut, BillReviewIn
from app.services.bills import confirm_bill, extract_bill, store_extraction
from app.auth import get_current_user

router = APIRouter()


@router.get("/bills", response_model=list[BillOut])
def list_bills(db: Session = Depends(get_db)) -> list[BillOut]:
    rows = db.scalars(select(BillUpload).order_by(BillUpload.created_at.desc())).all()
    return [present_bill(row) for row in rows]


@router.post("/bills", response_model=BillOut, status_code=201)
def upload_bill(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BillOut:
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    extracted = extract_bill(file.filename or "bill", content, file.content_type)
    bill = BillUpload(
        filename=file.filename or "bill",
        content_type=file.content_type,
        created_by_id=user.id,
    )
    db.add(bill)
    db.flush()
    store_extraction(db, bill, extracted)
    db.commit()
    db.refresh(bill)
    return present_bill(bill)


@router.put("/bills/{bill_id}", response_model=BillOut)
def review_bill(bill_id: int, payload: BillReviewIn, db: Session = Depends(get_db)) -> BillOut:
    bill = db.get(BillUpload, bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    extracted = {
        "supplier_name": payload.supplier_name,
        "invoice_number": payload.invoice_number,
        "notes": payload.notes,
        "lines": [line.model_dump(mode="json") for line in payload.lines],
    }
    bill.extracted_json = json.dumps(extracted)
    bill.supplier_name = payload.supplier_name
    bill.invoice_number = payload.invoice_number
    bill.notes = payload.notes
    db.commit()
    db.refresh(bill)
    return present_bill(bill)


@router.post("/bills/{bill_id}/confirm", response_model=BillOut)
def post_bill(bill_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> BillOut:
    bill = db.get(BillUpload, bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    confirm_bill(db, bill, user)
    db.commit()
    db.refresh(bill)
    return present_bill(bill)
