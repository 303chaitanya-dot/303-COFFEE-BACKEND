# 303 Coffee — inventory & accounts

Cafe back office for **303 Coffee**: logins, stock, sauces, dishes, purchases, bill uploads, Pet Pooja order deductions, and a double-entry ledger.

## Run locally

Python 3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

Default login (change immediately):

- Email: `admin@303coffee.local`
- Password: `change-me`

First start creates `data/cafe.db` and seeds a working cafe. If you already had an older local database, delete `data/cafe.db` once so the new tables can be created.

## What you can do

- **Profiles** — owner, manager, and staff logins. Owners can add people.
- **Purchases** — type item name, price, quantity, unit, and the serving size used in recipes. New items are created as you type.
- **Sauces & dishes** — a sauce is ingredients per serving. A dish can use ingredients and sauces. **Price used** is the cost of that portion at current weighted-average cost.
- **Bills** — upload a supplier bill. A `.txt` file is parsed immediately. Photo bills need `OPENAI_API_KEY`. Review the lines, then post stock.
- **Pet Pooja** — map their item names to your dishes. When Pet Pooja sends a billed order to `POST /api/integrations/petpooja/orders`, recipes fire and inventory drops.
- **Ledger** — purchases, sales, waste, and adjustments stay on the books.

## Deploy on Render

The repo includes `render.yaml`:

1. Push this project to GitHub (not the LAZYFILMS account).
2. In Render: **New → Blueprint** and point it at the repo.
3. Set `ADMIN_EMAIL` / `ADMIN_PASSWORD` and, if you want photo bills, `OPENAI_API_KEY`.
4. After deploy, give Pet Pooja this webhook:

`https://<your-service>.onrender.com/api/integrations/petpooja/orders`

Optional header: `X-Petpooja-Secret` matching `PETPOOJA_WEBHOOK_SECRET`.

Ask Pet Pooja (`support@petpooja.com`) to push billed POS orders to that URL. Public Pet Pooja docs cover sending *online* orders into the POS; restaurant outbound order webhooks are enabled per store.

## Tests

```bash
source .venv/bin/activate
pytest -q
```
