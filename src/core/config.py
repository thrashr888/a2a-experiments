import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_model: str = "gpt-5-mini"
    openai_api_key: str = ""

    host: str = "0.0.0.0"
    port: int = 8080

    log_level: str = "INFO"
    log_file: Optional[str] = "logs/a2a-lab.log"

    # A2A Protocol settings
    a2a_host: str = "localhost"
    a2a_port: int = 8081

    # AI Configuration
    ai_temperature: float = 0.1
    max_tokens: int = 2000
    a2a_conversation_timeout: int = 3600
    a2a_max_history_length: int = 20
    a2a_enable_reasoning_logs: bool = True

    # Python path setting
    pythonpath: Optional[str] = None

    # Database persistence
    data_dir: str = "data"
    sqlite_db_path: Optional[str] = (
        None  # Will be set to data_dir/agent_sessions.db if None
    )

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields like pghost, pgport


settings = Settings()
