# 303 Coffee — inventory & accounts

Cafe back office for **303 Coffee**: stock, recipes, purchasing, sales, waste, and a double-entry ledger. A FastAPI backend plus a local operator UI.

## What it does

- Tracks ingredients and packaging with reorder points and inventory value
- Builds menu items from recipes, then deducts stock when a drink is sold
- Receives supplier purchases and recalculates **weighted average cost**
- Posts every purchase, sale, waste write-off, and count adjustment to the ledger
- Shows cash, accounts payable, today's sales, low stock, and a period P&L

Amounts default to **INR**. Change `CURRENCY_CODE` / `CURRENCY_SYMBOL` in `.env` if needed.

## Run it

Python 3.12:

```bash
cd "/Users/sarang/303 COFFEE"
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The first start creates `data/cafe.db` and seeds a working cafe (beans, milk, menu, opening cash, and a sample ticket).

API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Tests

```bash
source .venv/bin/activate
pytest -q
```

## How the numbers stay honest

| Event | Inventory | Ledger |
| --- | --- | --- |
| Receive purchase | Qty up, WAC updated | Dr Inventory / Cr Accounts Payable |
| Pay supplier | — | Dr Accounts Payable / Cr Cash |
| Sale | Recipe qty down | Dr Cash / Cr Sales, and Dr COGS / Cr Inventory |
| Waste | Qty down | Dr Waste Expense / Cr Inventory |
| Count adjustment | Qty up or down | Inventory vs Inventory Adjustments |

New catalog items start at zero on-hand. Stock only enters through purchases or a counted adjustment.

## API map

- `GET /api/dashboard` — cash, AP, inventory value, today's sales, low stock
- `GET/POST /api/items`, `/api/menu`, `/api/suppliers`
- `GET/POST /api/purchases` and `POST /api/purchases/{id}/pay`
- `GET/POST /api/sales`, `/api/waste`, `/api/adjustments`
- `GET /api/accounts`, `/api/ledger`, `/api/reports/profit-loss`, `/api/reports/valuation`
