from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    BOT_TOKEN: str
    CHANNEL_ID: str
    
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_HOST: str = "db"
    DB_PORT: int = 5432
    DB_NAME: str = "autobot"
    
    # Full database URL override (for Render/managed PostgreSQL).
    # If set, takes precedence over individual DB_* fields.
    DATABASE_URL: str | None = None
    
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    
    MAX_PRICE_USD: int = 10000
    CHECK_INTERVAL_SECONDS: int = 45

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()