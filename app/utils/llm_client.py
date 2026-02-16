"""Model-agnostic LLM client supporting OpenAI, Azure OpenAI, and Anthropic."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import json
from enum import Enum
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type
)

try:
    from openai import OpenAI, AzureOpenAI, RateLimitError, APITimeoutError, APIConnectionError
except ImportError:
    OpenAI = None
    AzureOpenAI = None
    RateLimitError = Exception
    APITimeoutError = Exception
    APIConnectionError = Exception

try:
    from anthropic import Anthropic, RateLimitError as AnthropicRateLimitError
except ImportError:
    Anthropic = None
    AnthropicRateLimitError = Exception


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"


class LLMMessage:
    """Standardized message format across providers."""

    def __init__(self, role: str, content: str):
        self.role = role  # "system", "user", "assistant"
        self.content = content

    def to_openai(self) -> Dict[str, str]:
        """Convert to OpenAI message format."""
        return {"role": self.role, "content": self.content}

    def to_anthropic(self) -> Dict[str, str]:
        """Convert to Anthropic message format."""
        # Anthropic uses same format as OpenAI
        return {"role": self.role, "content": self.content}


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 500,
        json_mode: bool = False
    ) -> str:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    @retry(
        stop=stop_after_attempt(6),
        wait=wait_random_exponential(min=1, max=60),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
        reraise=True
    )
    def generate_sync(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 500,
        json_mode: bool = False
    ) -> str:
        """
        Synchronous version of generate with retry logic.

        Automatically retries on rate limits (429), timeouts, and connection errors.
        """
        pass


class OpenAIClient(BaseLLMClient):
    """OpenAI API client with automatic retry on rate limits."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        if OpenAI is None:
            raise ImportError("openai package not installed. Run: pip install openai")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    @retry(
        stop=stop_after_attempt(6),
        wait=wait_random_exponential(min=1, max=60),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
        reraise=True
    )
    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 500,
        json_mode: bool = False
    ) -> str:
        """
        Generate response using OpenAI API.

        Automatically retries on rate limits (429), timeouts, and connection errors.
        Uses exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s (up to 60s max).
        """
        openai_messages = [msg.to_openai() for msg in messages]

        kwargs = {
            "model": self.model,
            "messages": openai_messages,
        }

        # GPT-5 models only support temperature=1 (default)
        # Don't set temperature for GPT-5, use default
        if "gpt-5" not in self.model and "o1" not in self.model and "o3" not in self.model:
            kwargs["temperature"] = temperature

        # Use max_completion_tokens for newer models, max_tokens for older
        if "gpt-5" in self.model or "gpt-4.1" in self.model or "o1" in self.model or "o3" in self.model:
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**kwargs)

            # Validate response structure
            if not response or not response.choices or len(response.choices) == 0:
                raise ValueError("Empty response from OpenAI API")

            content = response.choices[0].message.content

            # Return empty string if content is None (better than crashing)
            return content if content is not None else ""

        except Exception as e:
            print(f"[LLM ERROR] OpenAI API call failed: {type(e).__name__} - {str(e)}")
            raise  # Re-raise so calling code can handle it

    def generate_sync(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 500,
        json_mode: bool = False
    ) -> str:
        """Synchronous version - OpenAI SDK is sync by default."""
        openai_messages = [msg.to_openai() for msg in messages]

        kwargs = {
            "model": self.model,
            "messages": openai_messages,
        }

        # GPT-5 models only support temperature=1 (default)
        if "gpt-5" not in self.model and "o1" not in self.model and "o3" not in self.model:
            kwargs["temperature"] = temperature

        # Use max_completion_tokens for newer models, max_tokens for older
        if "gpt-5" in self.model or "gpt-4.1" in self.model or "o1" in self.model or "o3" in self.model:
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**kwargs)

            # Validate response structure
            if not response or not response.choices or len(response.choices) == 0:
                raise ValueError("Empty response from OpenAI API")

            content = response.choices[0].message.content

            # Return empty string if content is None (better than crashing)
            return content if content is not None else ""

        except Exception as e:
            print(f"[LLM ERROR] OpenAI API call failed: {type(e).__name__} - {str(e)}")
            raise  # Re-raise so calling code can handle it


class AzureOpenAIClient(BaseLLMClient):
    """Azure OpenAI API client with automatic retry."""

    def __init__(
        self,
        api_key: str,
        azure_endpoint: str,
        api_version: str = "2024-02-15-preview",
        deployment_name: str = "gpt-4o"
    ):
        if AzureOpenAI is None:
            raise ImportError("openai package not installed. Run: pip install openai")

        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=azure_endpoint
        )
        self.deployment_name = deployment_name

    @retry(
        stop=stop_after_attempt(6),
        wait=wait_random_exponential(min=1, max=60),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
        reraise=True
    )
    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 500,
        json_mode: bool = False
    ) -> str:
        """Generate response using Azure OpenAI API with retry."""
        openai_messages = [msg.to_openai() for msg in messages]

        kwargs = {
            "model": self.deployment_name,
            "messages": openai_messages,
        }

        # GPT-5 and reasoning models only support temperature=1
        if "gpt-5" not in self.deployment_name and "o1" not in self.deployment_name and "o3" not in self.deployment_name:
            kwargs["temperature"] = temperature

        # Use appropriate token parameter based on model
        if "gpt-5" in self.deployment_name or "gpt-4.1" in self.deployment_name or "o1" in self.deployment_name or "o3" in self.deployment_name:
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**kwargs)

            if not response or not response.choices or len(response.choices) == 0:
                raise ValueError("Empty response from Azure OpenAI API")

            content = response.choices[0].message.content
            return content if content is not None else ""

        except Exception as e:
            print(f"[LLM ERROR] Azure OpenAI API call failed: {type(e).__name__} - {str(e)}")
            raise

    def generate_sync(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 500,
        json_mode: bool = False
    ) -> str:
        """Synchronous version."""
        openai_messages = [msg.to_openai() for msg in messages]

        kwargs = {
            "model": self.deployment_name,
            "messages": openai_messages,
        }

        if "gpt-5" not in self.deployment_name and "o1" not in self.deployment_name and "o3" not in self.deployment_name:
            kwargs["temperature"] = temperature

        if "gpt-5" in self.deployment_name or "gpt-4.1" in self.deployment_name or "o1" in self.deployment_name or "o3" in self.deployment_name:
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**kwargs)

            if not response or not response.choices or len(response.choices) == 0:
                raise ValueError("Empty response from Azure OpenAI API")

            content = response.choices[0].message.content
            return content if content is not None else ""

        except Exception as e:
            print(f"[LLM ERROR] Azure OpenAI API call failed: {type(e).__name__} - {str(e)}")
            raise


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude API client with automatic retry."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4.5-20241022"):
        if Anthropic is None:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
        self.client = Anthropic(api_key=api_key)
        self.model = model

    @retry(
        stop=stop_after_attempt(6),
        wait=wait_random_exponential(min=1, max=60),
        retry=retry_if_exception_type((AnthropicRateLimitError,)),
        reraise=True
    )
    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 500,
        json_mode: bool = False
    ) -> str:
        """Generate response using Anthropic API with retry."""
        # Separate system message from conversation messages
        system_message = None
        conversation_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                conversation_messages.append(msg.to_anthropic())

        kwargs = {
            "model": self.model,
            "messages": conversation_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system_message:
            kwargs["system"] = system_message

        try:
            response = self.client.messages.create(**kwargs)

            if not response or not response.content or len(response.content) == 0:
                raise ValueError("Empty response from Anthropic API")

            content = response.content[0].text
            return content if content is not None else ""

        except Exception as e:
            print(f"[LLM ERROR] Anthropic API call failed: {type(e).__name__} - {str(e)}")
            raise

    def generate_sync(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 500,
        json_mode: bool = False
    ) -> str:
        """Synchronous version."""
        return self.generate(messages, temperature, max_tokens, json_mode)


class LLMClientFactory:
    """Factory for creating LLM clients based on configuration."""

    @staticmethod
    def create_client(
        provider: LLMProvider,
        api_key: str,
        model: Optional[str] = None,
        azure_endpoint: Optional[str] = None,
        azure_api_version: Optional[str] = None,
        azure_deployment_name: Optional[str] = None
    ) -> BaseLLMClient:
        """
        Create an LLM client based on provider type.

        Args:
            provider: The LLM provider to use
            api_key: API key for the provider
            model: Model name (for OpenAI/Anthropic)
            azure_endpoint: Azure OpenAI endpoint URL
            azure_api_version: Azure API version
            azure_deployment_name: Azure deployment name

        Returns:
            Initialized LLM client
        """
        if provider == LLMProvider.OPENAI:
            return OpenAIClient(
                api_key=api_key,
                model=model or "gpt-4o"
            )

        elif provider == LLMProvider.AZURE_OPENAI:
            if not azure_endpoint:
                raise ValueError("azure_endpoint required for Azure OpenAI")

            return AzureOpenAIClient(
                api_key=api_key,
                azure_endpoint=azure_endpoint,
                api_version=azure_api_version or "2024-02-15-preview",
                deployment_name=azure_deployment_name or model or "gpt-4o"
            )

        elif provider == LLMProvider.ANTHROPIC:
            return AnthropicClient(
                api_key=api_key,
                model=model or "claude-sonnet-4.5-20241022"
            )

        else:
            raise ValueError(f"Unsupported provider: {provider}")


# Convenience function for quick client creation
def create_llm_client(
    provider: str,
    api_key: str,
    **kwargs
) -> BaseLLMClient:
    """
    Quick way to create an LLM client.

    Example:
        client = create_llm_client("openai", api_key="sk-...")
        client = create_llm_client("azure_openai", api_key="...", azure_endpoint="https://...")
        client = create_llm_client("anthropic", api_key="sk-ant-...")
    """
    provider_enum = LLMProvider(provider)
    return LLMClientFactory.create_client(provider_enum, api_key, **kwargs)
