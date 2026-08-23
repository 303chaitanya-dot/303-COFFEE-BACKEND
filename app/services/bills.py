import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BillUpload, User
from app.services.inventory import receive_named_purchase


def _parse_plain_text(text: str) -> dict:
    lines = []
    supplier = None
    invoice = None
    for raw in text.splitlines():
        row = raw.strip()
        if not row:
            continue
        lower = row.lower()
        if lower.startswith("supplier:"):
            supplier = row.split(":", 1)[1].strip()
            continue
        if lower.startswith("invoice:"):
            invoice = row.split(":", 1)[1].strip()
            continue
        parts = [part.strip() for part in row.replace("\t", "|").split("|")]
        if len(parts) < 3:
            parts = row.split(",")
        if len(parts) < 3:
            continue
        name, quantity, price, *rest = [part.strip() for part in parts]
        entry = {"name": name, "quantity": quantity, "price": price, "unit": "pcs", "category": "other"}
        if rest:
            entry["unit"] = rest[0] or "pcs"
        if len(rest) > 1 and rest[1]:
            entry["serving_size"] = rest[1]
        lines.append(entry)
    return {"supplier_name": supplier, "invoice_number": invoice, "lines": lines, "notes": None}


def _parse_with_openai(filename: str, content: bytes, content_type: str | None) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    import base64

    encoded = base64.b64encode(content).decode("ascii")
    media = content_type or "image/jpeg"
    prompt = (
        "Read this cafe supplier bill. Return JSON only with keys "
        "supplier_name, invoice_number, notes, and lines. Each line has "
        "name, quantity, price (unit price), unit (g, kg, ml, l, or pcs), "
        "category, and serving_size if printed. Use Indian cafe grocery language."
    )
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": f"data:{media};base64,{encoded}"},
                ],
            }
        ],
    )
    text = response.output_text
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        raise HTTPException(status_code=422, detail="Could not read a bill from that file")
    return json.loads(text[start : end + 1])


def extract_bill(filename: str, content: bytes, content_type: str | None) -> dict:
    if filename.lower().endswith(".txt") or (content_type or "").startswith("text/"):
        return _parse_plain_text(content.decode("utf-8", errors="ignore"))
    if settings.openai_api_key:
        return _parse_with_openai(filename, content, content_type)
    raise HTTPException(
        status_code=422,
        detail="Upload a .txt bill, or set OPENAI_API_KEY so photo bills can be read",
    )


def store_extraction(db: Session, bill: BillUpload, extracted: dict) -> BillUpload:
    bill.supplier_name = extracted.get("supplier_name")
    bill.invoice_number = extracted.get("invoice_number")
    bill.notes = extracted.get("notes")
    bill.extracted_json = json.dumps(extracted)
    bill.status = "pending_review"
    db.flush()
    return bill


def confirm_bill(db: Session, bill: BillUpload, user: User | None = None) -> BillUpload:
    if bill.status == "confirmed" and bill.purchase_id:
        raise HTTPException(status_code=400, detail="Bill already posted")
    if not bill.extracted_json:
        raise HTTPException(status_code=400, detail="Bill has no extracted lines yet")
    extracted = json.loads(bill.extracted_json)
    lines = extracted.get("lines") or []
    if not lines:
        raise HTTPException(status_code=400, detail="No line items to post")
    purchase = receive_named_purchase(
        db,
        supplier_name=bill.supplier_name or extracted.get("supplier_name"),
        invoice_number=bill.invoice_number or extracted.get("invoice_number"),
        purchased_at=None,
        paid=False,
        notes=bill.notes or extracted.get("notes") or f"From bill {bill.filename}",
        lines=lines,
    )
    bill.purchase_id = purchase.id
    bill.status = "confirmed"
    if user:
        bill.created_by_id = user.id
    return bill


def extracted_lines(bill: BillUpload) -> list[dict]:
    if not bill.extracted_json:
        return []
    return json.loads(bill.extracted_json).get("lines") or []
