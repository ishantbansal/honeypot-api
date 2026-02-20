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
    max_conversation_turns: int = 10
    scam_confidence_threshold: float = 0.5
    min_messages_before_callback: int = 2

    # Human Behavior Simulation
    enable_human_delay: bool = False  # Set to True to enable human-like delays

    # Dashboard Configuration
    dashboard_password: str = "admin123"  # Change in .env for production

    # Debug Configuration
    debug: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
