# 303 Coffee — inventory

Stock room for **303 Coffee**: items with price, serving size, reorder/par, and expiry. Sauces and waste stay; dishes, purchases, sales, bills, suppliers, and Pet Pooja are hidden for now.

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

First start creates `data/cafe.db` with an empty stock room (admin login only). Older databases drop sample items once on upgrade.

## What you can do

- **Inventory** — name, quantity, price per stock unit, serving size (number + unit), reorder point, par level, expiry. Price per serving is calculated from serving size.
- **Sauces** — ingredients per serving, costed from current item prices.
- **Waste** — write off spoilage.
- **Profile** — your login. Team accounts come later.

## Deploy on Render

The repo includes `render.yaml`:

1. Push this project to GitHub (not the LAZYFILMS account).
2. In Render: **New → Blueprint** and point it at the repo.
3. Set `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

## Tests

```bash
source .venv/bin/activate
pytest -q
```
