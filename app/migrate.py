from sqlalchemy import inspect, text


def ensure_columns(engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    statements = []
    if "items" in tables:
        cols = {column["name"] for column in inspector.get_columns("items")}
        if "serving_size" not in cols:
            statements.append("ALTER TABLE items ADD COLUMN serving_size NUMERIC(16, 4) DEFAULT 1")
    if "menu_items" in tables:
        cols = {column["name"] for column in inspector.get_columns("menu_items")}
        if "petpooja_item_id" not in cols:
            statements.append("ALTER TABLE menu_items ADD COLUMN petpooja_item_id VARCHAR(80)")
    if "recipe_lines" in tables:
        cols = {column["name"] for column in inspector.get_columns("recipe_lines")}
        if "sauce_id" not in cols:
            statements.append("ALTER TABLE recipe_lines ADD COLUMN sauce_id INTEGER")
    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
