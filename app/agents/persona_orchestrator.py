"""Persona Orchestrator - Selects appropriate persona based on scam confidence."""

from typing import Dict, List
from app.agents.normal_user_persona import NormalUserPersona
from app.agents.skeptical_user_persona import SkepticalUserPersona
from app.agents.honeypot_persona import HoneypotPersona
from app.agents.base_persona import BasePersonaAgent
from app.utils.llm_client import BaseLLMClient


class PersonaOrchestrator:
    """
    Orchestrates between different persona agents based on scam detection confidence.

    Confidence Ranges:
    - 0.0 - 0.60: Normal User (confused, concerned, not suspicious)
    - 0.60 - 0.80: Skeptical User (questioning but not accusatory)
    - 0.80 - 1.0: Honeypot Mode (active intelligence extraction)
    """

    # Confidence thresholds
    SKEPTICAL_THRESHOLD = 0.60
    HONEYPOT_THRESHOLD = 0.80

    def __init__(self, llm_client: BaseLLMClient):
        """
        Initialize persona orchestrator.

        Args:
            llm_client: Model-agnostic LLM client
        """
        self.llm_client = llm_client

        # Initialize all persona agents
        self.normal_persona = NormalUserPersona(llm_client)
        self.skeptical_persona = SkepticalUserPersona(llm_client)
        self.honeypot_persona = HoneypotPersona(llm_client)

    def select_persona(self, confidence: float) -> BasePersonaAgent:
        """
        Select appropriate persona based on scam confidence score.

        Args:
            confidence: Scam detection confidence (0.0 to 1.0)

        Returns:
            Selected persona agent
        """
        if confidence < self.SKEPTICAL_THRESHOLD:
            return self.normal_persona
        elif confidence < self.HONEYPOT_THRESHOLD:
            return self.skeptical_persona
        else:
            return self.honeypot_persona

    async def generate_response(
        self,
        latest_message: str,
        conversation_history: List[Dict[str, str]],
        scam_confidence: float,
        scam_details: Dict = None
    ) -> tuple[str, str]:
        """
        Generate response using appropriate persona.

        Args:
            latest_message: Latest message from scammer
            conversation_history: Full conversation history
            scam_confidence: Current scam confidence score
            scam_details: Optional scam detection details

        Returns:
            Tuple of (response_text, persona_name)
        """
        # Select persona based on confidence
        persona = self.select_persona(scam_confidence)

        # Generate response
        response = await persona.generate_response(
            latest_message=latest_message,
            conversation_history=conversation_history,
            scam_details=scam_details
        )

        return response, persona.get_persona_name()

    def generate_response_sync(
        self,
        latest_message: str,
        conversation_history: List[Dict[str, str]],
        scam_confidence: float,
        scam_details: Dict = None
    ) -> tuple[str, str]:
        """Synchronous version of generate_response."""
        persona = self.select_persona(scam_confidence)

        response = persona.generate_response_sync(
            latest_message=latest_message,
            conversation_history=conversation_history,
            scam_details=scam_details
        )

        return response, persona.get_persona_name()

    def get_persona_description(self, confidence: float) -> str:
        """
        Get description of which persona would be used for given confidence.

        Args:
            confidence: Scam confidence score

        Returns:
            Description string
        """
        persona = self.select_persona(confidence)
        name = persona.get_persona_name()

        descriptions = {
            "Normal User": "Acting as concerned but unsuspicious user",
            "Skeptical User": "Acting cautiously skeptical, asking verification questions",
            "Honeypot": "Active intelligence extraction mode"
        }

        return descriptions.get(name, "Unknown persona")
