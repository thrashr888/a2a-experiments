import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://a2a_user:a2a_password@localhost:5432/a2a_lab"
    redis_url: str = "redis://localhost:6379/0"
    openai_model: str = "gpt-5"
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
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()