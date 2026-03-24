from pathlib import Path

from pydantic_settings import BaseSettings

# Find .env in project root (parent of backend/)
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://claude_stocks:claude_stocks_dev@localhost:5432/claude_stocks"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Data feeds
    twelve_data_api_key: str = ""
    oanda_account_id: str = ""
    oanda_access_token: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # Risk parameters
    max_risk_per_trade: float = 0.01
    max_daily_loss: float = 0.02
    min_signal_confidence: float = 0.60
    consecutive_sl_limit: int = 8

    # Brain / Ensemble
    ensemble_enabled: bool = True

    # A/B testing
    ab_testing_enabled: bool = False
    ab_variants: list[str] = ["baseline", "enhanced"]
    ab_default_variant: str = "baseline"

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
