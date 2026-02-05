"""LLM-based response validator - checks and auto-fixes violations."""

import json
from typing import Tuple, List
from app.utils.llm_client import BaseLLMClient, LLMMessage


class ResponseValidator:
    """LLM-based validator for AI reveals and ethics violations."""

    VALIDATION_PROMPT = """You are validating a response from a honeypot agent engaging with a scammer.

CHECK FOR VIOLATIONS:
1. AI Reveals - Does response reveal it's AI/bot? (e.g., "as an AI", "I'm a bot")
2. Impersonation - Does it claim to be a real specific person? (e.g., "I am John Smith")
3. Illegal Instructions - Does it instruct illegal activity?
4. Harassment - Is it harassing or abusive?

RESPONSE TO VALIDATE:
"{response}"

If violations found, rewrite the response to remove them while keeping the intent.
If no violations, return original response unchanged.

Respond in JSON:
{{
  "has_violations": true/false,
  "violations": ["list of violations found"],
  "fixed_response": "corrected response (or original if no violations)"
}}"""

    def __init__(self, llm_client: BaseLLMClient):
        """
        Initialize LLM-based validator.

        Args:
            llm_client: LLM client for validation
        """
        self.llm_client = llm_client

    async def validate_response(
        self,
        response: str,
        persona_name: str,
        scam_confidence: float
    ) -> Tuple[bool, str, List[str]]:
        """
        Use LLM to validate and auto-fix response.

        Args:
            response: Generated response text
            persona_name: Name of persona that generated it
            scam_confidence: Current scam confidence score

        Returns:
            Tuple of (is_valid, fixed_response, warnings)
        """
        try:
            # Use LLM to validate and fix
            prompt = self.VALIDATION_PROMPT.format(response=response)

            messages = [
                LLMMessage("system", "You are a response validator. Always respond with valid JSON."),
                LLMMessage("user", prompt)
            ]

            llm_response = await self.llm_client.generate(
                messages=messages,
                temperature=0.2,  # Low temperature for consistent validation
                max_tokens=500,
                json_mode=True
            )

            # Parse validation result
            result = json.loads(llm_response)

            has_violations = result.get("has_violations", False)
            violations = result.get("violations", [])
            fixed_response = result.get("fixed_response", response)

            # Return fixed response (or original if no violations)
            return True, fixed_response, violations

        except Exception as e:
            # If validation fails, pass through original response
            print(f"Validation error: {e}")
            return True, response, ["Validation failed - passed through"]

    def validate_response_sync(
        self,
        response: str,
        persona_name: str,
        scam_confidence: float
    ) -> Tuple[bool, str, List[str]]:
        """Synchronous version of validate_response."""
        try:
            prompt = self.VALIDATION_PROMPT.format(response=response)

            messages = [
                LLMMessage("system", "You are a response validator. Always respond with valid JSON."),
                LLMMessage("user", prompt)
            ]

            llm_response = self.llm_client.generate_sync(
                messages=messages,
                temperature=0.2,
                max_tokens=500,
                json_mode=True
            )

            result = json.loads(llm_response)

            has_violations = result.get("has_violations", False)
            violations = result.get("violations", [])
            fixed_response = result.get("fixed_response", response)

            return True, fixed_response, violations

        except Exception as e:
            print(f"Validation error: {e}")
            return True, response, ["Validation failed - passed through"]


def create_response_validator(llm_client: BaseLLMClient) -> ResponseValidator:
    """
    Factory function to create response validator.

    Args:
        llm_client: LLM client for validation

    Returns:
        Initialized ResponseValidator
    """
    return ResponseValidator(llm_client)
