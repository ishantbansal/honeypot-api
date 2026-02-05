"""Base class for persona agents."""

from abc import ABC, abstractmethod
from typing import List, Dict
from app.utils.llm_client import BaseLLMClient, LLMMessage


class BasePersonaAgent(ABC):
    """Abstract base class for persona agents."""

    def __init__(self, llm_client: BaseLLMClient):
        """
        Initialize persona agent.

        Args:
            llm_client: Model-agnostic LLM client
        """
        self.llm_client = llm_client

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this persona."""
        pass

    @abstractmethod
    def get_persona_name(self) -> str:
        """Get the name of this persona."""
        pass

    async def generate_response(
        self,
        latest_message: str,
        conversation_history: List[Dict[str, str]],
        scam_details: Dict = None
    ) -> str:
        """
        Generate a response as this persona.

        Args:
            latest_message: The latest message from the scammer
            conversation_history: Full conversation history
            scam_details: Optional scam detection details for context

        Returns:
            Generated response text
        """
        # Build conversation context
        messages = [
            LLMMessage("system", self.get_system_prompt())
        ]

        # Add conversation history
        for msg in conversation_history[-10:]:  # Last 10 messages for context
            sender = msg.get("sender", "unknown")
            text = msg.get("text", "")

            if sender == "scammer":
                messages.append(LLMMessage("user", text))
            elif sender == "user":
                messages.append(LLMMessage("assistant", text))

        # Add latest message
        messages.append(LLMMessage("user", latest_message))

        # Add scam context if available
        if scam_details:
            context_hint = self._build_context_hint(scam_details)
            if context_hint:
                messages[-1].content += f"\n\n[Internal context: {context_hint}]"

        # Generate response
        response = await self.llm_client.generate(
            messages=messages,
            temperature=0.8,  # Higher temperature for natural variation
            max_tokens=300
        )

        return response.strip()

    def generate_response_sync(
        self,
        latest_message: str,
        conversation_history: List[Dict[str, str]],
        scam_details: Dict = None
    ) -> str:
        """Synchronous version of generate_response."""
        messages = [
            LLMMessage("system", self.get_system_prompt())
        ]

        for msg in conversation_history[-10:]:
            sender = msg.get("sender", "unknown")
            text = msg.get("text", "")

            if sender == "scammer":
                messages.append(LLMMessage("user", text))
            elif sender == "user":
                messages.append(LLMMessage("assistant", text))

        messages.append(LLMMessage("user", latest_message))

        if scam_details:
            context_hint = self._build_context_hint(scam_details)
            if context_hint:
                messages[-1].content += f"\n\n[Internal context: {context_hint}]"

        response = self.llm_client.generate_sync(
            messages=messages,
            temperature=0.8,
            max_tokens=300
        )

        return response.strip()

    def _build_context_hint(self, scam_details: Dict) -> str:
        """Build context hint from scam detection details."""
        hints = []

        scam_type = scam_details.get("scam_type")
        if scam_type:
            hints.append(f"This appears to be a {scam_type} scam")

        threat_indicators = scam_details.get("threat_indicators", [])
        if threat_indicators:
            hints.append(f"Threats detected: {', '.join(threat_indicators[:3])}")

        return "; ".join(hints) if hints else None
