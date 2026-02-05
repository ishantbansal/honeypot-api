"""LLM-based intelligence extraction from scammer conversations."""

import json
import re
from typing import List, Dict
from app.utils.llm_client import BaseLLMClient, LLMMessage
from app.models.schemas import ExtractedIntelligence


class IntelligenceExtractor:
    """Extracts intelligence from scammer messages using LLM + regex."""

    EXTRACTION_PROMPT = """You are a cybersecurity analyst extracting intelligence from a scammer conversation.

Analyze the conversation and extract ALL instances of:
1. Bank account numbers (Indian format: 9-18 digits)
2. UPI IDs (format: username@bankname)
3. Phishing links/URLs
4. Phone numbers (Indian format: +91 or 10 digits starting with 6-9)
5. Suspicious keywords and tactics used

Conversation:
{conversation}

Respond in JSON format:
{{
  "bank_accounts": ["account1", "account2"],
  "upi_ids": ["user@paytm", "user@googlepay"],
  "phishing_links": ["http://fake-site.com"],
  "phone_numbers": ["+919876543210"],
  "suspicious_keywords": ["urgent", "verify", "blocked"],
  "scammer_tactics": ["urgency", "authority_impersonation", "threat"]
}}

Extraction:"""

    def __init__(self, llm_client: BaseLLMClient):
        """
        Initialize intelligence extractor.

        Args:
            llm_client: Model-agnostic LLM client
        """
        self.llm_client = llm_client

        # Regex patterns as fallback
        self.upi_pattern = re.compile(r'\b[\w.-]+@[\w.-]+\b')
        self.phone_pattern = re.compile(r'(\+91|91)?[\s-]?[6-9]\d{9}\b')
        self.url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        )
        self.account_pattern = re.compile(r'\b\d{9,18}\b')

    async def extract_intelligence(
        self,
        conversation_history: List[Dict[str, str]]
    ) -> ExtractedIntelligence:
        """
        Extract intelligence from conversation using LLM + regex.

        Args:
            conversation_history: Full conversation history

        Returns:
            ExtractedIntelligence object with all extracted data
        """
        # Format conversation for analysis
        formatted_conversation = self._format_conversation(conversation_history)

        # Try LLM-based extraction first
        try:
            llm_intel = await self._llm_extraction(formatted_conversation)
        except Exception as e:
            print(f"LLM extraction error: {e}")
            llm_intel = ExtractedIntelligence()

        # Also do regex extraction as backup/supplement
        regex_intel = self._regex_extraction(formatted_conversation)

        # Merge both results (union of findings)
        merged_intel = self._merge_intelligence(llm_intel, regex_intel)

        return merged_intel

    async def _llm_extraction(self, conversation: str) -> ExtractedIntelligence:
        """Use LLM to extract intelligence."""
        prompt = self.EXTRACTION_PROMPT.format(conversation=conversation)

        messages = [
            LLMMessage("system", "You are a cybersecurity analyst. Always respond with valid JSON."),
            LLMMessage("user", prompt)
        ]

        response = await self.llm_client.generate(
            messages=messages,
            temperature=0.2,  # Low temperature for consistent extraction
            max_tokens=800,
            json_mode=True
        )

        # Parse JSON response
        data = json.loads(response)

        return ExtractedIntelligence(
            bankAccounts=data.get("bank_accounts", []),
            upiIds=data.get("upi_ids", []),
            phishingLinks=data.get("phishing_links", []),
            phoneNumbers=data.get("phone_numbers", []),
            suspiciousKeywords=data.get("suspicious_keywords", [])
        )

    def _regex_extraction(self, conversation: str) -> ExtractedIntelligence:
        """Fallback regex-based extraction."""
        return ExtractedIntelligence(
            bankAccounts=self._extract_accounts(conversation),
            upiIds=self._extract_upi_ids(conversation),
            phishingLinks=self._extract_urls(conversation),
            phoneNumbers=self._extract_phone_numbers(conversation),
            suspiciousKeywords=[]
        )

    def _extract_upi_ids(self, text: str) -> List[str]:
        """Extract UPI IDs from text."""
        matches = self.upi_pattern.findall(text)
        # Filter to valid UPI patterns (common banks)
        upi_banks = ['paytm', 'phonepe', 'googlepay', 'gpay', 'ybl', 'okaxis', 'okicici', 'oksbi']
        return [m for m in matches if any(bank in m.lower() for bank in upi_banks)]

    def _extract_phone_numbers(self, text: str) -> List[str]:
        """Extract Indian phone numbers."""
        matches = self.phone_pattern.findall(text)
        # Normalize format
        normalized = []
        for match in matches:
            if isinstance(match, tuple):
                match = ''.join(match)
            # Clean up
            digits = re.sub(r'[^\d]', '', match)
            if len(digits) == 10:
                normalized.append(f"+91{digits}")
            elif len(digits) == 12 and digits.startswith('91'):
                normalized.append(f"+{digits}")
        return list(set(normalized))

    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text."""
        matches = self.url_pattern.findall(text)
        return list(set(matches))

    def _extract_accounts(self, text: str) -> List[str]:
        """Extract potential bank account numbers."""
        matches = self.account_pattern.findall(text)
        # Filter out numbers that are too common (like dates, prices)
        # Bank accounts are typically 11-18 digits
        return [m for m in matches if 11 <= len(m) <= 18]

    def _format_conversation(self, history: List[Dict[str, str]]) -> str:
        """Format conversation for LLM analysis."""
        formatted = []
        for msg in history:
            sender = msg.get("sender", "unknown")
            text = msg.get("text", "")
            formatted.append(f"{sender}: {text}")
        return "\n".join(formatted)

    def _merge_intelligence(
        self,
        llm_intel: ExtractedIntelligence,
        regex_intel: ExtractedIntelligence
    ) -> ExtractedIntelligence:
        """Merge LLM and regex extraction results."""
        return ExtractedIntelligence(
            bankAccounts=list(set(llm_intel.bankAccounts + regex_intel.bankAccounts)),
            upiIds=list(set(llm_intel.upiIds + regex_intel.upiIds)),
            phishingLinks=list(set(llm_intel.phishingLinks + regex_intel.phishingLinks)),
            phoneNumbers=list(set(llm_intel.phoneNumbers + regex_intel.phoneNumbers)),
            suspiciousKeywords=list(set(llm_intel.suspiciousKeywords))
        )

    def extract_intelligence_sync(
        self,
        conversation_history: List[Dict[str, str]]
    ) -> ExtractedIntelligence:
        """Synchronous version of extract_intelligence."""
        formatted_conversation = self._format_conversation(conversation_history)

        try:
            prompt = self.EXTRACTION_PROMPT.format(conversation=formatted_conversation)
            messages = [
                LLMMessage("system", "You are a cybersecurity analyst. Always respond with valid JSON."),
                LLMMessage("user", prompt)
            ]

            response = self.llm_client.generate_sync(
                messages=messages,
                temperature=0.2,
                max_tokens=800,
                json_mode=True
            )

            data = json.loads(response)
            llm_intel = ExtractedIntelligence(
                bankAccounts=data.get("bank_accounts", []),
                upiIds=data.get("upi_ids", []),
                phishingLinks=data.get("phishing_links", []),
                phoneNumbers=data.get("phone_numbers", []),
                suspiciousKeywords=data.get("suspicious_keywords", [])
            )
        except Exception as e:
            print(f"LLM extraction error: {e}")
            llm_intel = ExtractedIntelligence()

        regex_intel = self._regex_extraction(formatted_conversation)
        return self._merge_intelligence(llm_intel, regex_intel)
