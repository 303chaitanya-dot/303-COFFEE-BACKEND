from sqlalchemy import inspect, text


def _run(engine, statement: str) -> None:
    try:
        with engine.begin() as connection:
            connection.execute(text(statement))
    except Exception as exc:
        print(f"migrate skipped ({statement[:80]}): {exc}")


def ensure_columns(engine) -> None:
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
    except Exception as exc:
        print(f"migrate inspect failed: {exc}")
        return

    if "items" in tables:
        cols = {column["name"] for column in inspector.get_columns("items")}
        if "serving_size" not in cols:
            _run(engine, "ALTER TABLE items ADD COLUMN serving_size NUMERIC(16, 4) DEFAULT 1")
        if "serving_unit" not in cols:
            _run(engine, "ALTER TABLE items ADD COLUMN serving_unit VARCHAR(8) DEFAULT 'pcs'")
        if "expiry_date" not in cols:
            _run(engine, "ALTER TABLE items ADD COLUMN expiry_date DATE")
        if "qty_per_unit" not in cols:
            _run(engine, "ALTER TABLE items ADD COLUMN qty_per_unit NUMERIC(16, 4) DEFAULT 1")
        if "units_on_hand" not in cols:
            _run(engine, "ALTER TABLE items ADD COLUMN units_on_hand NUMERIC(16, 4) DEFAULT 0")
        if "total_price" not in cols:
            _run(engine, "ALTER TABLE items ADD COLUMN total_price NUMERIC(14, 2) DEFAULT 0")
        inspector = inspect(engine)
        cols = {column["name"] for column in inspector.get_columns("items")}
        if {"qty_per_unit", "units_on_hand", "total_price"} <= cols:
            _run(
                engine,
                """
                UPDATE items
                SET qty_per_unit = COALESCE(qty_per_unit, 1),
                    units_on_hand = COALESCE(units_on_hand, quantity_on_hand),
                    total_price = COALESCE(total_price, quantity_on_hand * unit_cost)
                WHERE qty_per_unit IS NULL OR units_on_hand IS NULL OR total_price IS NULL
                """,
            )

    if "menu_items" in tables:
        cols = {column["name"] for column in inspector.get_columns("menu_items")}
        if "petpooja_item_id" not in cols:
            _run(engine, "ALTER TABLE menu_items ADD COLUMN petpooja_item_id VARCHAR(80)")

    if "recipe_lines" in tables:
        cols = {column["name"] for column in inspector.get_columns("recipe_lines")}
        if "sauce_id" not in cols:
            _run(engine, "ALTER TABLE recipe_lines ADD COLUMN sauce_id INTEGER")
        if "unit" not in cols:
            _run(engine, "ALTER TABLE recipe_lines ADD COLUMN unit VARCHAR(8)")

    if "inventory_sheets" in tables:
        cols = {column["name"] for column in inspector.get_columns("inventory_sheets")}
        if "kind" not in cols:
            _run(engine, "ALTER TABLE inventory_sheets ADD COLUMN kind VARCHAR(20) DEFAULT 'inventory'")
            _run(engine, "UPDATE inventory_sheets SET kind = 'inventory' WHERE kind IS NULL OR kind = ''")

    try:
        tables = set(inspect(engine).get_table_names())
        if "stock_lots" not in tables:
            return
        with engine.begin() as connection:
            lot_count = connection.execute(text("SELECT COUNT(*) FROM stock_lots")).scalar() or 0
            if lot_count == 0:
                connection.execute(
                    text(
                        """
                        INSERT INTO stock_lots (item_id, quantity, expiry_date, received_at)
                        SELECT id, quantity_on_hand, expiry_date, COALESCE(created_at, CURRENT_TIMESTAMP)
                        FROM items
                        WHERE quantity_on_hand IS NOT NULL AND quantity_on_hand > 0
                        """
                    )
                )
    except Exception as exc:
        print(f"stock lot backfill skipped: {exc}")
