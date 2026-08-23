from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "303 Coffee"
    database_url: str = f"sqlite:///{DATA_DIR / 'cafe.db'}"
    currency_code: str = "INR"
    currency_symbol: str = "₹"
    secret_key: str = "dev-only-change-me"
    admin_email: str = "admin@303coffee.local"
    admin_password: str = "change-me"
    admin_name: str = "Owner"
    openai_api_key: str = ""
    petpooja_app_key: str = ""
    petpooja_app_secret: str = ""
    petpooja_access_token: str = ""
    petpooja_rest_id: str = ""
    petpooja_webhook_secret: str = ""

    @property
    def sqlalchemy_url(self) -> str:
        return normalize_database_url(self.database_url)


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "bills").mkdir(parents=True, exist_ok=True)
