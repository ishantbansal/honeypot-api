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
        scam_details: Dict = None,
        extracted_intelligence: Dict = None
    ) -> tuple[str, str]:
        """
        Generate response using appropriate persona with dynamic targeting.

        Args:
            latest_message: Latest message from scammer
            conversation_history: Full conversation history
            scam_confidence: Current scam confidence score
            scam_details: Optional scam detection details
            extracted_intelligence: What we've extracted so far (to guide targeting)

        Returns:
            Tuple of (response_text, persona_name)
        """
        # Select persona based on confidence
        persona = self.select_persona(scam_confidence)

        # Build extraction context for honeypot persona
        extraction_context = None
        if scam_confidence >= self.HONEYPOT_THRESHOLD and extracted_intelligence:
            extraction_context = self._build_extraction_context(extracted_intelligence)

        # Generate response with context
        response = await persona.generate_response(
            latest_message=latest_message,
            conversation_history=conversation_history,
            scam_details=scam_details,
            extraction_context=extraction_context
        )

        return response, persona.get_persona_name()

    def _build_extraction_context(self, extracted_intelligence: Dict) -> str:
        """
        Build context about what intelligence is still needed.

        Args:
            extracted_intelligence: Current extracted intelligence

        Returns:
            Context string for persona
        """
        missing = []

        if not extracted_intelligence.get('bankAccounts') or len(extracted_intelligence['bankAccounts']) == 0:
            missing.append("bank account")
        if not extracted_intelligence.get('upiIds') or len(extracted_intelligence['upiIds']) == 0:
            missing.append("UPI ID")
        if not extracted_intelligence.get('phishingLinks') or len(extracted_intelligence['phishingLinks']) == 0:
            missing.append("website/link")
        if not extracted_intelligence.get('phoneNumbers') or len(extracted_intelligence['phoneNumbers']) == 0:
            missing.append("phone number")

        if not missing:
            return "All critical intelligence extracted. Confirm/verify details."
        elif len(missing) == 4:
            return "Extract: bank account, UPI ID, website link, and phone number."
        else:
            return f"Still need: {', '.join(missing)}. Focus extraction on these."

    def generate_response_sync(
        self,
        latest_message: str,
        conversation_history: List[Dict[str, str]],
        scam_confidence: float,
        scam_details: Dict = None,
        extracted_intelligence: Dict = None
    ) -> tuple[str, str]:
        """Synchronous version of generate_response."""
        persona = self.select_persona(scam_confidence)

        # Build extraction context for honeypot
        extraction_context = None
        if scam_confidence >= self.HONEYPOT_THRESHOLD and extracted_intelligence:
            extraction_context = self._build_extraction_context(extracted_intelligence)

        response = persona.generate_response_sync(
            latest_message=latest_message,
            conversation_history=conversation_history,
            scam_details=scam_details,
            extraction_context=extraction_context
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
