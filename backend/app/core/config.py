from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Aimentum"
    app_env: str = "development"
    log_level: str = "info"
    app_token: str = ""
    database_url: str = "postgresql+psycopg://aimentum:aimentum@localhost:5432/aimentum"
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    tick_secret: str = ""

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:aidinthr82@gmail.com"

    anthropic_api_key: str = ""
    anthropic_model_daily: str = "claude-haiku-4-5-20251001"
    anthropic_model_retro: str = "claude-sonnet-4-6"
    anthropic_max_tokens: int = 1024
    anthropic_max_retries: int = 2

    google_cloud_project: str = ""
    google_application_credentials_json: str = ""
    stt_language_codes: str = "en-US"

    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_refresh_token: str = ""
    gcal_calendar_id: str = ""
    gcal_calendar_name: str = "Aimentum"


settings = Settings()
