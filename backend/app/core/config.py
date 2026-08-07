from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Aimentum"
    app_env: str = "development"
    log_level: str = "info"
    app_token: str = ""
    database_url: str = "postgresql+psycopg://aimentum:aimentum@localhost:5432/aimentum"

    anthropic_api_key: str = ""
    anthropic_model_daily: str = "claude-haiku-4-5-20251001"
    anthropic_model_retro: str = "claude-sonnet-4-6"
    anthropic_max_tokens: int = 1024
    anthropic_max_retries: int = 2

    google_cloud_project: str = ""
    google_application_credentials_json: str = ""
    stt_language_codes: str = "en-US"


settings = Settings()
