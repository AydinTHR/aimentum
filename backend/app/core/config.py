from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Aimentum"
    app_env: str = "development"
    log_level: str = "info"
    app_token: str = ""
    database_url: str = "postgresql+psycopg://aimentum:aimentum@localhost:5432/aimentum"


settings = Settings()
