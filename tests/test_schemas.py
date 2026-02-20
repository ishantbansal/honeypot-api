"""Tests for Pydantic schema models — verifies all GUVI-scored fields are present."""

import time
import pytest
from app.models.schemas import (
    ExtractedIntelligence,
    EngagementMetrics,
    HoneypotResponse,
    HoneypotRequest,
    GUVICallbackPayload,
    SessionState,
    Message,
    Metadata,
)


# ── ExtractedIntelligence ─────────────────────────────────────────────

class TestExtractedIntelligence:
    def test_default_empty(self):
        intel = ExtractedIntelligence()
        assert intel.bankAccounts == []
        assert intel.upiIds == []
        assert intel.phishingLinks == []
        assert intel.phoneNumbers == []
        assert intel.emailAddresses == []
        assert intel.suspiciousKeywords == []

    def test_all_fields_populated(self):
        intel = ExtractedIntelligence(
            bankAccounts=["1234567890123456"],
            upiIds=["scammer@paytm"],
            phishingLinks=["http://fake-bank.com"],
            phoneNumbers=["+919876543210"],
            emailAddresses=["fraud@fake.com"],
            suspiciousKeywords=["urgent", "OTP"],
        )
        assert len(intel.bankAccounts) == 1
        assert len(intel.upiIds) == 1
        assert len(intel.phishingLinks) == 1
        assert len(intel.phoneNumbers) == 1
        assert len(intel.emailAddresses) == 1

    def test_serialization_keys(self):
        """Field names must match GUVI's expected format."""
        data = ExtractedIntelligence(phoneNumbers=["+919876543210"]).model_dump()
        assert "phoneNumbers" in data
        assert "bankAccounts" in data
        assert "upiIds" in data
        assert "phishingLinks" in data
        assert "emailAddresses" in data


# ── EngagementMetrics ─────────────────────────────────────────────────

class TestEngagementMetrics:
    def test_defaults(self):
        m = EngagementMetrics()
        assert m.engagementDurationSeconds == 0
        assert m.messagesExchanged == 0
        assert m.totalTurns == 0

    def test_populated(self):
        m = EngagementMetrics(engagementDurationSeconds=90, messagesExchanged=10, totalTurns=5)
        assert m.engagementDurationSeconds == 90
        assert m.messagesExchanged == 10

    def test_serialization_key(self):
        """GUVI scoring function reads engagementDurationSeconds."""
        data = EngagementMetrics(engagementDurationSeconds=65).model_dump()
        assert "engagementDurationSeconds" in data
        assert data["engagementDurationSeconds"] == 65


# ── HoneypotResponse ──────────────────────────────────────────────────

class TestHoneypotResponse:
    def test_all_guvi_scored_fields_present(self):
        """Response must include all fields the GUVI scoring function checks."""
        resp = HoneypotResponse(
            reply="Hello, how can I help?",
            scamDetected=True,
            totalMessagesExchanged=5,
            extractedIntelligence=ExtractedIntelligence(phoneNumbers=["+919876543210"]),
            agentNotes="Scam confidence: 85%",
            engagementMetrics=EngagementMetrics(engagementDurationSeconds=75, messagesExchanged=5),
        )
        data = resp.model_dump()
        assert data["status"] == "success"           # 5pts Response Structure
        assert data["scamDetected"] is True          # 5pts Response Structure
        assert data["extractedIntelligence"] is not None  # 5pts Response Structure
        assert data["engagementMetrics"] is not None  # 2.5pts Response Structure
        assert data["agentNotes"] != ""              # 2.5pts Response Structure

    def test_status_defaults_to_success(self):
        resp = HoneypotResponse(reply="test")
        assert resp.status == "success"

    def test_engagement_metrics_duration_over_60(self):
        """Duration > 60s scores 5 extra engagement quality points."""
        metrics = EngagementMetrics(engagementDurationSeconds=90, messagesExchanged=10)
        resp = HoneypotResponse(reply="test", engagementMetrics=metrics)
        assert resp.engagementMetrics.engagementDurationSeconds > 60

    def test_messages_at_least_5(self):
        """messagesExchanged >= 5 scores engagement quality points."""
        metrics = EngagementMetrics(messagesExchanged=10)
        resp = HoneypotResponse(reply="test", engagementMetrics=metrics)
        assert resp.engagementMetrics.messagesExchanged >= 5


# ── GUVICallbackPayload ───────────────────────────────────────────────

class TestGUVICallbackPayload:
    def test_all_required_fields(self):
        payload = GUVICallbackPayload(
            sessionId="test-session-123",
            scamDetected=True,
            totalMessagesExchanged=10,
            extractedIntelligence=ExtractedIntelligence(upiIds=["fraud@paytm"]),
            agentNotes="UPI fraud detected",
            engagementMetrics=EngagementMetrics(engagementDurationSeconds=80, messagesExchanged=10),
        )
        data = payload.model_dump()
        assert data["status"] == "success"
        assert data["sessionId"] == "test-session-123"
        assert data["scamDetected"] is True
        assert data["totalMessagesExchanged"] == 10
        assert data["extractedIntelligence"] is not None
        assert data["agentNotes"] == "UPI fraud detected"
        assert data["engagementMetrics"]["engagementDurationSeconds"] == 80

    def test_engagement_metrics_not_none(self):
        """The most common failure point — engagementMetrics must be present."""
        payload = GUVICallbackPayload(
            sessionId="s1",
            scamDetected=True,
            totalMessagesExchanged=5,
            extractedIntelligence=ExtractedIntelligence(),
            agentNotes="test",
            engagementMetrics=EngagementMetrics(engagementDurationSeconds=60, messagesExchanged=5),
        )
        assert payload.engagementMetrics is not None
        assert payload.engagementMetrics.engagementDurationSeconds >= 0


# ── SessionState ──────────────────────────────────────────────────────

class TestSessionState:
    def test_defaults(self):
        s = SessionState(session_id="abc")
        assert s.session_id == "abc"
        assert s.scam_detected is False
        assert s.scam_confidence == 0.0
        assert s.message_count == 0
        assert s.engagement_phase == "detection"

    def test_created_at_set(self):
        """created_at is needed to compute engagementDurationSeconds."""
        before = time.time()
        s = SessionState(session_id="abc")
        after = time.time()
        assert before <= s.created_at <= after

    def test_engagement_phase_values(self):
        for phase in ("detection", "engagement", "extraction", "completed"):
            s = SessionState(session_id="x", engagement_phase=phase)
            assert s.engagement_phase == phase


# ── HoneypotRequest ───────────────────────────────────────────────────

class TestHoneypotRequest:
    def test_basic_request(self):
        req = HoneypotRequest(
            sessionId="sess-001",
            message=Message(sender="scammer", text="Your account is blocked!", timestamp=1000),
        )
        assert req.sessionId == "sess-001"
        assert req.message.sender == "scammer"
        assert req.conversationHistory == []

    def test_metadata_defaults(self):
        req = HoneypotRequest(
            sessionId="sess-002",
            message=Message(sender="scammer", text="Test", timestamp=1000),
        )
        assert req.metadata.channel == "SMS"
        assert req.metadata.locale == "IN"
