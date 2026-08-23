from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "303 Coffee"
    database_url: str = f"sqlite:///{DATA_DIR / 'cafe.db'}"
    currency_code: str = "INR"
    currency_symbol: str = "₹"


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
