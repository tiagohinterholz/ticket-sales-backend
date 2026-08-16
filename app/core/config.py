from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    JWT_SECRET: str
    QR_SECRET_KEY: str
    TMDB_API_KEY: str
    SEAT_HOLD_MINUTES: int = 5
    TRANSFER_EXPIRY_HOURS: int = 24
    CANCEL_WINDOW_HOURS: int = 2
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]


settings = Settings()
