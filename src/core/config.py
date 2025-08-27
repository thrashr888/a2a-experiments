import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://a2a_user:a2a_password@localhost:5432/a2a_lab"
    redis_url: str = "redis://localhost:6379/0"
    
    host: str = "0.0.0.0"
    port: int = 8080
    
    log_level: str = "INFO"
    log_file: Optional[str] = "logs/a2a-lab.log"
    
    # A2A Protocol settings
    a2a_host: str = "localhost"
    a2a_port: int = 8081
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()