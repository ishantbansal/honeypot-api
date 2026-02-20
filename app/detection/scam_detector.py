"""LLM-based scam detection using AI intelligence."""

import json
from typing import Tuple, List, Dict
from app.utils.llm_client import BaseLLMClient, LLMMessage
from app.utils.logger import logger


class ScamDetector:
    """Detects scam messages using LLM intelligence."""

    DETECTION_PROMPT = """You are a fraud detection expert analyzing messages for scam indicators.

Analyze the following message and determine if it's a scam attempt.

Consider these scam indicators:
- Urgency and threats (account blocked, immediate action required)
- Authority impersonation (bank, government, police, tech support)
- Financial requests (money transfer, account details, OTP, passwords)
- Suspicious links or phone numbers
- Too-good-to-be-true offers (prizes, lottery, cashback)
- Emotional manipulation (fear, greed, curiosity)
- Poor grammar or unusual phrasing
- Requests for sensitive information

Respond in JSON format:
{{
  "is_scam": true/false,
  "confidence": 0.0-1.0,
  "scam_type": "phishing" | "banking_fraud" | "romance" | "investment" | "tech_support" | "prize" | "other" | null,
  "reasoning": "Brief explanation of why this is/isn't a scam",
  "suspicious_keywords": ["list", "of", "suspicious", "words"],
  "threat_indicators": ["specific", "threats", "detected"]
}}

Message to analyze:
"{message}"

Analysis:"""

    def __init__(self, llm_client: BaseLLMClient):
        """
        Initialize scam detector with LLM client.

        Args:
            llm_client: Model-agnostic LLM client
        """
        self.llm_client = llm_client

    async def detect_scam(
        self,
        message: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> Tuple[bool, float, Dict]:
        """
        Detect if a message is a scam using LLM intelligence.

        Args:
            message: The message text to analyze
            conversation_history: Optional previous messages for context

        Returns:
            Tuple of (is_scam, confidence_score, details_dict)
        """
        # Build context-aware prompt
        prompt = self._build_detection_prompt(message, conversation_history)

        messages = [
            LLMMessage("system", "You are a fraud detection expert. Always respond with valid JSON."),
            LLMMessage("user", prompt)
        ]

        try:
            # Get LLM analysis
            response = await self.llm_client.generate(
                messages=messages,
                temperature=0.3,  # Lower temperature for consistent analysis
                max_tokens=500,
                json_mode=True
            )

            # Parse JSON response
            analysis = json.loads(response)

            is_scam = analysis.get("is_scam", False)
            confidence = analysis.get("confidence", 0.0)

            # Return detailed analysis
            details = {
                "scam_type": analysis.get("scam_type"),
                "reasoning": analysis.get("reasoning", ""),
                "suspicious_keywords": analysis.get("suspicious_keywords", []),
                "threat_indicators": analysis.get("threat_indicators", [])
            }

            return is_scam, confidence, details

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in scam detection: {e}")
            return self._fallback_detection(message)
        except Exception as e:
            logger.error(f"Scam detection error: {e}")
            return self._fallback_detection(message)

    def _build_detection_prompt(
        self,
        message: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> str:
        """Build context-aware detection prompt."""
        base_prompt = self.DETECTION_PROMPT.format(message=message)

        # Add conversation context if available
        if conversation_history and len(conversation_history) > 0:
            context = "\n\nPrevious conversation context:\n"
            for msg in conversation_history[-3:]:  # Last 3 messages for context
                sender = msg.get("sender", "unknown")
                text = msg.get("text", "")
                context += f"{sender}: {text}\n"

            base_prompt = base_prompt + context

        return base_prompt

    def _fallback_detection(self, message: str) -> Tuple[bool, float, Dict]:
        """Fallback pattern-based detection if LLM fails."""
        message_lower = message.lower()

        # Simple keyword-based detection
        scam_keywords = [
            "blocked", "suspended", "verify", "urgent", "immediately",
            "click here", "bank account", "upi", "otp", "password",
            "won", "prize", "lottery", "congratulations", "claim"
        ]

        matches = sum(1 for keyword in scam_keywords if keyword in message_lower)
        confidence = min(matches * 0.15, 0.9)
        is_scam = confidence >= 0.5

        return is_scam, confidence, {
            "scam_type": "unknown",
            "reasoning": f"Fallback detection: found {matches} suspicious keywords",
            "suspicious_keywords": [kw for kw in scam_keywords if kw in message_lower],
            "threat_indicators": []
        }

    def detect_scam_sync(
        self,
        message: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> Tuple[bool, float, Dict]:
        """
        Synchronous version of detect_scam.

        Args:
            message: The message text to analyze
            conversation_history: Optional previous messages for context

        Returns:
            Tuple of (is_scam, confidence_score, details_dict)
        """
        prompt = self._build_detection_prompt(message, conversation_history)

        messages = [
            LLMMessage("system", "You are a fraud detection expert. Always respond with valid JSON."),
            LLMMessage("user", prompt)
        ]

        try:
            response = self.llm_client.generate_sync(
                messages=messages,
                temperature=0.3,
                max_tokens=500,
                json_mode=True
            )

            analysis = json.loads(response)

            is_scam = analysis.get("is_scam", False)
            confidence = analysis.get("confidence", 0.0)

            details = {
                "scam_type": analysis.get("scam_type"),
                "reasoning": analysis.get("reasoning", ""),
                "suspicious_keywords": analysis.get("suspicious_keywords", []),
                "threat_indicators": analysis.get("threat_indicators", [])
            }

            return is_scam, confidence, details

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Scam detection error: {e}")
            return self._fallback_detection(message)
