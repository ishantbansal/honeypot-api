"""Configuration management using Pydantic Settings."""

from pydantic_settings import BaseSettings
from typing import Literal, Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    api_key: str

    # LLM Provider Configuration
    llm_provider: Literal["openai", "azure_openai", "anthropic"] = "openai"
    llm_model: str = "gpt-4o"

    # OpenAI Configuration
    openai_api_key: Optional[str] = None

    # Azure OpenAI Configuration
    azure_openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_deployment_name: Optional[str] = None

    # Anthropic Configuration
    anthropic_api_key: Optional[str] = None

    # GUVI Configuration
    guvi_callback_url: str = "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"

    # Agent Configuration
    max_conversation_turns: int = 20
    scam_confidence_threshold: float = 0.7
    min_messages_before_callback: int = 5

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
