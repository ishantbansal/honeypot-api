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
    - 0.0 - 0.50: Normal User (confused, concerned, not suspicious)
    - 0.50 - 0.85: Skeptical User (questioning but not accusatory)
    - 0.85 - 1.0: Honeypot Mode (active intelligence extraction)
    """

    # Confidence thresholds
    SKEPTICAL_THRESHOLD = 0.50
    HONEYPOT_THRESHOLD = 0.85

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
        extracted_intelligence: Dict = None,
        detected_red_flags: list = None
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
        if scam_confidence >= self.SKEPTICAL_THRESHOLD and extracted_intelligence:
            extraction_context = self._build_extraction_context(
                extracted_intelligence, detected_red_flags or []
            )

        # Generate response with context
        response = await persona.generate_response(
            latest_message=latest_message,
            conversation_history=conversation_history,
            scam_details=scam_details,
            extraction_context=extraction_context
        )

        return response, persona.get_persona_name()

    def _build_extraction_context(self, extracted_intelligence: Dict, detected_red_flags: list = None) -> str:
        """
        Build context about what intelligence is still needed, guided by detected red flags.

        Args:
            extracted_intelligence: Current extracted intelligence
            detected_red_flags: Red flags detected so far (maps to specific intel targets)

        Returns:
            Context string for persona
        """
        missing = []

        if not extracted_intelligence.get('bankAccounts'):
            missing.append("bank account number")
        if not extracted_intelligence.get('upiIds'):
            missing.append("UPI ID")
        if not extracted_intelligence.get('phishingLinks'):
            missing.append("website/link")
        if not extracted_intelligence.get('phoneNumbers'):
            missing.append("phone number")
        if not extracted_intelligence.get('emailAddresses'):
            missing.append("email address")
        if not extracted_intelligence.get('caseIds'):
            missing.append("case/reference ID")
        if not extracted_intelligence.get('policyNumbers'):
            missing.append("policy number")
        if not extracted_intelligence.get('orderNumbers'):
            missing.append("order/transaction ID")

        # Map detected red flags to priority extraction targets
        priority = []
        flags_lower = [f.lower() for f in (detected_red_flags or [])]
        if any(w in f for f in flags_lower for w in ["fee", "pay", "transfer", "amount"]):
            if "UPI ID" in missing:
                priority.append("UPI ID (they're asking for payment)")
            if "bank account number" in missing:
                priority.append("bank account (payment target)")
        if any(w in f for f in flags_lower for w in ["employee", "agent", "officer", "staff"]):
            if "case/reference ID" in missing:
                priority.append("employee/case ID (verify their identity)")
        if any(w in f for f in flags_lower for w in ["link", "url", "click", "verify", "website"]):
            if "website/link" in missing:
                priority.append("the exact link/URL they want you to click")

        if not missing:
            return "All critical intel extracted. Keep probing: ask for supervisor name, company address, or alternate contact."

        context = f"Still need: {', '.join(missing[:4])}."
        if priority:
            context += f" PRIORITY based on red flags: {', '.join(priority[:2])}."
        return context

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
