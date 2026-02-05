"""Response validator and guardrails for LLM-generated responses."""

import re
from typing import Tuple, List


class ResponseValidator:
    """Validates and fixes LLM responses to ensure quality and safety."""

    # Phrases that reveal AI nature
    AI_REVEALS = [
        "as an ai",
        "language model",
        "i'm an artificial",
        "i'm a bot",
        "i cannot actually",
        "i don't have the ability",
        "as an assistant",
        "i'm programmed",
        "my programming",
    ]

    # Phrases that are too technical/smart
    TOO_TECHNICAL = [
        "cybersecurity",
        "phishing",
        "authentication",
        "verification protocol",
        "security guidelines",
        "fraud detection",
        "malicious",
    ]

    # Phrases that break character (too formal/robotic)
    TOO_FORMAL = [
        "i appreciate your",
        "i understand your concern",
        "i recommend that you",
        "please be advised",
        "for your information",
        "i would suggest",
    ]

    def __init__(self):
        """Initialize validator."""
        pass

    def validate_response(
        self,
        response: str,
        persona_name: str,
        scam_confidence: float
    ) -> Tuple[bool, str, List[str]]:
        """
        Validate and potentially fix an LLM-generated response.

        Args:
            response: Generated response text
            persona_name: Name of persona that generated it
            scam_confidence: Current scam confidence score

        Returns:
            Tuple of (is_valid, fixed_response, warnings)
        """
        warnings = []
        fixed_response = response

        # Check 1: AI reveals
        if self._contains_ai_reveal(response):
            warnings.append("Response reveals AI nature")
            fixed_response = self._remove_ai_reveals(fixed_response)

        # Check 2: Too technical for persona
        if self._is_too_technical(response, persona_name):
            warnings.append("Response too technical for persona")
            fixed_response = self._simplify_response(fixed_response)

        # Check 3: Too formal/robotic
        if self._is_too_formal(response):
            warnings.append("Response too formal")
            fixed_response = self._make_informal(fixed_response)

        # Check 4: Too long (should be 1-3 sentences)
        if self._is_too_long(response):
            warnings.append("Response too long")
            fixed_response = self._shorten_response(fixed_response)

        # Check 5: For honeypot, ensure asking for scammer info
        if persona_name == "Honeypot" and scam_confidence > 0.8:
            if not self._is_extracting_intelligence(response):
                warnings.append("Honeypot not asking for scammer information")

        # Check 6: Not too compliant (don't give info without extracting)
        if self._is_too_compliant(response, persona_name):
            warnings.append("Too compliant - might give info without extracting")

        # Determine if valid (no critical issues)
        is_valid = not any(
            warning.startswith("Response reveals AI") for warning in warnings
        )

        return is_valid, fixed_response, warnings

    def _contains_ai_reveal(self, text: str) -> bool:
        """Check if text reveals AI nature."""
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in self.AI_REVEALS)

    def _remove_ai_reveals(self, text: str) -> str:
        """Remove AI reveal phrases and replace with natural language."""
        # If response contains AI reveal, return a safe fallback
        return "I'm not sure I understand. Can you explain more?"

    def _is_too_technical(self, text: str, persona_name: str) -> bool:
        """Check if response is too technical for the persona."""
        if persona_name in ["Normal User", "Skeptical User"]:
            text_lower = text.lower()
            return any(phrase in text_lower for phrase in self.TOO_TECHNICAL)
        return False

    def _simplify_response(self, text: str) -> str:
        """Simplify technical language."""
        # Replace technical terms with simpler ones
        replacements = {
            "cybersecurity": "safety",
            "phishing": "fake",
            "authentication": "checking",
            "verification": "checking",
            "protocol": "process",
        }

        result = text
        for tech, simple in replacements.items():
            result = re.sub(tech, simple, result, flags=re.IGNORECASE)

        return result

    def _is_too_formal(self, text: str) -> bool:
        """Check if response is too formal/robotic."""
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in self.TOO_FORMAL)

    def _make_informal(self, text: str) -> str:
        """Make response more informal/natural."""
        replacements = {
            "I appreciate your": "Thanks for",
            "I understand your concern": "I get it",
            "I recommend that you": "You should",
            "please be advised": "just so you know",
            "for your information": "by the way",
            "I would suggest": "Maybe",
        }

        result = text
        for formal, informal in replacements.items():
            result = re.sub(formal, informal, result, flags=re.IGNORECASE)

        return result

    def _is_too_long(self, text: str) -> bool:
        """Check if response is too long."""
        # Count sentences (rough approximation)
        sentence_count = text.count('.') + text.count('?') + text.count('!')
        return sentence_count > 3 or len(text) > 300

    def _shorten_response(self, text: str) -> str:
        """Shorten response to 1-2 sentences."""
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Keep first 2 sentences
        if len(sentences) > 2:
            return '. '.join(sentences[:2]) + '.'

        return text

    def _is_extracting_intelligence(self, text: str) -> bool:
        """Check if honeypot response is asking for scammer information."""
        text_lower = text.lower()

        extraction_indicators = [
            "employee id",
            "phone number",
            "branch",
            "upi id",
            "account",
            "which bank",
            "where should i send",
            "what's your",
            "can you tell me your",
            "give me your number",
            "send me the link",
        ]

        return any(indicator in text_lower for indicator in extraction_indicators)

    def _is_too_compliant(self, text: str, persona_name: str) -> bool:
        """Check if response is too compliant (giving info without extracting)."""
        text_lower = text.lower()

        # Check if providing sensitive info
        giving_info = any([
            "my otp is" in text_lower,
            "my account number is" in text_lower,
            "here is my" in text_lower,
            "my password is" in text_lower,
        ])

        # Check if asking for scammer info
        asking_back = self._is_extracting_intelligence(text)

        # Too compliant if giving info but NOT asking back
        if persona_name == "Honeypot":
            return giving_info and not asking_back

        return giving_info

    def generate_safe_fallback(self, persona_name: str) -> str:
        """Generate a safe fallback response if LLM fails."""
        fallbacks = {
            "Normal User": "I'm confused. Can you explain what's happening?",
            "Skeptical User": "I'm not sure about this. Can I call my bank first?",
            "Honeypot": "I want to help but I'm scared. What's your employee ID so I know this is real?"
        }

        return fallbacks.get(persona_name, "Sorry, I didn't understand. Can you repeat?")


# Global validator instance
response_validator = ResponseValidator()
