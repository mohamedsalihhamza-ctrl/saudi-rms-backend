from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    app_name: str = "SaudiRMS"
    environment: str = "development"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://rms_user:rms_pass@localhost:5432/saudi_rms"
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "dev-secret-key-change-in-production"
    access_token_expire_minutes: int = 1440

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_basic_price_id: str = "price_basic"
    stripe_pro_price_id: str = "price_pro"
    stripe_enterprise_price_id: str = "price_enterprise"

    openai_api_key: str = ""

    payment_provider: str = "mock"
    moyasar_secret_key: str = ""
    moyasar_publishable_key: str = ""

    google_client_id: str = ""
    apple_client_id: str = ""

    zatca_api_url: str = ""
    zatca_api_key: str = ""

    ml_forecast_horizon_days: int = 365
    ml_retrain_interval_hours: int = 24
    ml_price_update_interval_minutes: int = 15

    sentry_dsn: str = ""


@lru_cache()
def get_settings() -> Settings:
    return Settings()
