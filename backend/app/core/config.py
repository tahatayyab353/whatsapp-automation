import json
from typing import List, Optional, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Configuration
    APP_NAME: str = "AI Receptionist API"
    APP_VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Frontend / CORS Configuration
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str) and v.startswith("["):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except Exception:
                pass
        return v  # type: ignore

    # JWT Authentication Configuration (32+ character default for development)
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_DEVELOPMENT_AT_LEAST_32_BYTES_LONG!"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.ENVIRONMENT.lower() == "production":
            insecure_keys = [
                "",
                "CHANGE_ME_IN_DEVELOPMENT_AT_LEAST_32_BYTES_LONG!",
                "secret",
                "changeme",
                "password",
            ]
            if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY in insecure_keys or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "Production deployment requires a strong, random JWT_SECRET_KEY (minimum 32 characters)."
                )
        return self

    # Database Configuration
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ai_receptionist"

    # AI Engine Configuration (CHUNK 5)
    AI_PROVIDER: str = "gemini"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.6-flash"

    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "qwen/qwen3.8-27b"

    AI_TEMPERATURE: float = 0.2
    AI_MAX_OUTPUT_TOKENS: int = 500
    AI_REQUEST_TIMEOUT_SECONDS: float = 20.0

    # Knowledge & Context Boundaries (Cost & Performance Control)
    MAX_KNOWLEDGE_DOCUMENTS: int = 10
    MAX_KNOWLEDGE_CHARS: int = 12000
    RECENT_MESSAGE_LIMIT: int = 20

    # Meta / WhatsApp Cloud API Configuration (CHUNK 6)
    WHATSAPP_API_VERSION: str = "v20.0"
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_VERIFY_TOKEN: Optional[str] = None
    WHATSAPP_APP_SECRET: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
