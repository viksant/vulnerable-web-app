"""Application configuration loaded from environment variables."""

from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """VulnShop application settings.

    Loads configuration from environment variables or .env file.
    Intentionally stores secrets as plain env vars for lab environment.

    Attributes:
        DB_HOST: PostgreSQL hostname (Docker service name).
        DB_PORT: PostgreSQL port.
        DB_USER: Database user.
        DB_PASSWORD: Database password.
        DB_NAME: Database name.
        JWT_SECRET: Secret key for signing access tokens.
        JWT_RESET_SECRET: Secret key for password reset tokens.
        AWS_ACCESS_KEY_ID: Fake AWS key for SSRF/credential exposure labs.
        AWS_SECRET_ACCESS_KEY: Fake AWS secret for SSRF/credential exposure labs.
        DEBUG: Enables stack trace exposure in error responses.
        DIFFICULTY: Controls vulnerability difficulty level.
    """

    DB_HOST: str = "postgres"
    DB_PORT: int = 5432
    DB_USER: str = "vulnshop"
    DB_PASSWORD: str = "vulnsh0p_db!"
    DB_NAME: str = "vulnshop"

    JWT_SECRET: str = "vulnshop_jwt_s3cret"
    JWT_RESET_SECRET: str = "reset123"

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    DEBUG: bool = False
    DIFFICULTY: Literal["easy", "medium", "hard"] = "easy"

    @property
    def DATABASE_URL(self) -> str:
        """Build async PostgreSQL connection URL from individual components."""
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
