"""LLM-based intelligence extraction from scammer conversations."""

import json
import re
from typing import List, Dict
from app.utils.llm_client import BaseLLMClient, LLMMessage
from app.models.schemas import ExtractedIntelligence
from app.utils.logger import logger


class IntelligenceExtractor:
    """Extracts intelligence from scammer messages using LLM + regex."""

    EXTRACTION_PROMPT = """Extract ALL scammer intelligence from this conversation.

Extract (be aggressive, include all variations):
1. Bank account numbers (any format: digits, spaces, dashes). Typically 9-18 digits.
   DO NOT confuse with phone numbers (phone numbers start with 6-9 or country code 91).
2. UPI IDs (username@bank format like xyz@paytm, abc@upi)
3. Phishing links/URLs (with or without http://)
4. Phone numbers (normalize to +91XXXXXXXXXX). Indian: 10 digits starting with 6-9.
5. Email addresses (any email like support@fake.com, offers@scam.in)
6. Suspicious keywords (urgency, threats, authority words)
7. Case/reference/ticket IDs (e.g. "CASE-12345", "REF-789", "TKT-001", any alphanumeric ID the scammer provides as a reference)
8. Policy numbers (e.g. "POL-987654", "LIC/987/654")
9. Order/transaction numbers (e.g. "ORD-123456", "TXN-789")

IMPORTANT: "918765432109" is a PHONE NUMBER (91 + 10 digits), NOT a bank account.

Conversation:
{conversation}

Respond in JSON:
{{
  "bank_accounts": [],
  "upi_ids": [],
  "phishing_links": [],
  "phone_numbers": [],
  "email_addresses": [],
  "suspicious_keywords": [],
  "case_ids": [],
  "policy_numbers": [],
  "order_numbers": []
}}"""

    def __init__(self, llm_client: BaseLLMClient):
        """
        Initialize intelligence extractor.

        Args:
            llm_client: Model-agnostic LLM client
        """
        self.llm_client = llm_client

        # Regex patterns as fallback (more aggressive to catch all variations)
        # UPI IDs: username@singleword (no dot in domain part, distinguishes from emails)
        self.upi_pattern = re.compile(r'\b[\w.-]+@[A-Za-z0-9]+\b')
        # Emails: user@domain.tld (has dot + TLD in domain part)
        self.email_pattern = re.compile(r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b')

        # Phone: handles +91, 91, spaces, dashes in various positions
        self.phone_pattern = re.compile(r'(?:\+91|91)?[\s-]?[6-9][\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d[\s-]?\d')

        # URL: matches both with and without http://
        self.url_pattern = re.compile(
            r'(?:http[s]?://)?(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}'
        )

        # Bank account: flexible pattern to catch numbers with spaces/dashes
        self.account_pattern = re.compile(r'\b\d[\d\s-]{8,20}\d\b')

    async def extract_intelligence(
        self,
        conversation_history: List[Dict[str, str]]
    ) -> ExtractedIntelligence:
        """
        Extract intelligence from conversation using LLM-primary approach.

        Uses LLM as primary extractor, regex as validation/supplement.
        LLM is smart enough to handle all variations and edge cases.

        Args:
            conversation_history: Full conversation history

        Returns:
            ExtractedIntelligence object with all extracted data
        """
        # Format conversation for analysis
        formatted_conversation = self._format_conversation(conversation_history)

        # PRIMARY: LLM-based extraction (intelligent, handles all variations)
        try:
            llm_intel = await self._llm_extraction(formatted_conversation)
        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            llm_intel = ExtractedIntelligence()

        # SUPPLEMENTARY: Regex extraction as safety net for structured data
        regex_intel = self._regex_extraction(formatted_conversation)
        return self._merge_intelligence(llm_intel, regex_intel)

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
            emailAddresses=data.get("email_addresses", []),
            suspiciousKeywords=data.get("suspicious_keywords", []),
            caseIds=data.get("case_ids", []),
            policyNumbers=data.get("policy_numbers", []),
            orderNumbers=data.get("order_numbers", []),
        )

    def _regex_extraction(self, conversation: str) -> ExtractedIntelligence:
        """Fallback regex-based extraction."""
        return ExtractedIntelligence(
            bankAccounts=self._extract_accounts(conversation),
            upiIds=self._extract_upi_ids(conversation),
            phishingLinks=self._extract_urls(conversation),
            phoneNumbers=self._extract_phone_numbers(conversation),
            emailAddresses=self._extract_emails(conversation),
            suspiciousKeywords=[]
        )

    def _extract_emails(self, text: str) -> List[str]:
        """Extract email addresses from text."""
        matches = self.email_pattern.findall(text)
        return list(set(matches))

    def _extract_upi_ids(self, text: str) -> List[str]:
        """Extract UPI IDs from text (username@singleword, no TLD)."""
        matches = self.upi_pattern.findall(text)
        return list(set(matches))

    def _extract_phone_numbers(self, text: str) -> List[str]:
        """Extract Indian phone numbers."""
        matches = self.phone_pattern.findall(text)
        # Normalize format
        normalized = []
        for match in matches:
            if isinstance(match, tuple):
                match = ''.join(match)
            # Clean up - remove all non-digits
            digits = re.sub(r'[^\d]', '', match)
            # Normalize to +91XXXXXXXXXX format
            if len(digits) == 10 and digits[0] in '6789':
                # 10 digits starting with 6-9
                normalized.append(f"+91{digits}")
            elif len(digits) == 11 and digits.startswith('0'):
                # 11 digits with leading 0 (remove 0)
                normalized.append(f"+91{digits[1:]}")
            elif len(digits) == 12 and digits.startswith('91'):
                # 12 digits starting with 91
                normalized.append(f"+{digits}")
            elif len(digits) == 13 and digits.startswith('091'):
                # 13 digits with 091
                normalized.append(f"+91{digits[3:]}")
        return list(set(normalized))

    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text."""
        matches = self.url_pattern.findall(text)
        return list(set(matches))

    def _extract_accounts(self, text: str) -> List[str]:
        """Extract potential bank account numbers."""
        matches = self.account_pattern.findall(text)
        cleaned = []
        for match in matches:
            # Remove spaces and dashes
            digits_only = re.sub(r'[^\d]', '', match)
            # Bank accounts are typically 9-18 digits (relaxed from 11-18)
            if 9 <= len(digits_only) <= 18:
                # Filter out phone numbers (Indian mobile patterns)
                is_phone = (
                    (len(digits_only) == 10 and digits_only[0] in '6789') or  # 10 digits starting with 6-9
                    (len(digits_only) == 12 and digits_only.startswith('91') and digits_only[2] in '6789')  # 91 + 10 digits
                )
                if not is_phone:
                    cleaned.append(digits_only)
        return list(set(cleaned))

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
            emailAddresses=list(set(llm_intel.emailAddresses + regex_intel.emailAddresses)),
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
                emailAddresses=data.get("email_addresses", []),
                suspiciousKeywords=data.get("suspicious_keywords", []),
                caseIds=data.get("case_ids", []),
                policyNumbers=data.get("policy_numbers", []),
                orderNumbers=data.get("order_numbers", []),
            )
        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            llm_intel = ExtractedIntelligence()

        regex_intel = self._regex_extraction(formatted_conversation)
        return self._merge_intelligence(llm_intel, regex_intel)
