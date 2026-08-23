from sqlalchemy import inspect, text


def ensure_columns(engine) -> None:
    try:
        _ensure_columns(engine)
    except Exception as exc:
        print(f"ensure_columns skipped: {exc}")


def _ensure_columns(engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    statements = []
    if "items" in tables:
        cols = {column["name"] for column in inspector.get_columns("items")}
        if "serving_size" not in cols:
            statements.append("ALTER TABLE items ADD COLUMN serving_size NUMERIC(16, 4) DEFAULT 1")
        if "serving_unit" not in cols:
            statements.append("ALTER TABLE items ADD COLUMN serving_unit VARCHAR(8) DEFAULT 'pcs'")
        if "expiry_date" not in cols:
            statements.append("ALTER TABLE items ADD COLUMN expiry_date DATE")
        if "qty_per_unit" not in cols:
            statements.append("ALTER TABLE items ADD COLUMN qty_per_unit NUMERIC(16, 4) DEFAULT 1")
        if "units_on_hand" not in cols:
            statements.append("ALTER TABLE items ADD COLUMN units_on_hand NUMERIC(16, 4) DEFAULT 0")
        if "total_price" not in cols:
            statements.append("ALTER TABLE items ADD COLUMN total_price NUMERIC(14, 2) DEFAULT 0")
    if "menu_items" in tables:
        cols = {column["name"] for column in inspector.get_columns("menu_items")}
        if "petpooja_item_id" not in cols:
            statements.append("ALTER TABLE menu_items ADD COLUMN petpooja_item_id VARCHAR(80)")
    if "recipe_lines" in tables:
        cols = {column["name"] for column in inspector.get_columns("recipe_lines")}
        if "sauce_id" not in cols:
            statements.append("ALTER TABLE recipe_lines ADD COLUMN sauce_id INTEGER")
        if "unit" not in cols:
            statements.append("ALTER TABLE recipe_lines ADD COLUMN unit VARCHAR(8)")
    if "inventory_sheets" in tables:
        cols = {column["name"] for column in inspector.get_columns("inventory_sheets")}
        if "kind" not in cols:
            statements.append("ALTER TABLE inventory_sheets ADD COLUMN kind VARCHAR(20) DEFAULT 'inventory'")
            statements.append("UPDATE inventory_sheets SET kind = 'inventory' WHERE kind IS NULL OR kind = ''")
    tables = set(inspect(engine).get_table_names())
    if "stock_lots" in tables:
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
    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
            if any("qty_per_unit" in statement or "units_on_hand" in statement or "total_price" in statement for statement in statements):
                connection.execute(
                    text(
                        """
                        UPDATE items
                        SET qty_per_unit = 1,
                            units_on_hand = quantity_on_hand,
                            total_price = quantity_on_hand * unit_cost
                        """
                    )
                )
