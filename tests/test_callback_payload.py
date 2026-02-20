"""Tests for GUVI callback payload — verifies the final output matches scoring requirements."""

import time
import pytest
from app.utils.guvi_callback import GUVICallbackHandler
from app.models.schemas import SessionState, ExtractedIntelligence, EngagementMetrics


@pytest.fixture
def handler():
    return GUVICallbackHandler(callback_url="http://mock-guvi.test/api/result")


@pytest.fixture
def full_session():
    """Session with all intel types and confirmed scam."""
    session = SessionState(session_id="test-session-abc")
    session.scam_detected = True
    session.scam_confidence = 0.95
    session.message_count = 10
    session.engagement_phase = "extraction"
    session.extracted_intelligence = ExtractedIntelligence(
        bankAccounts=["1234567890123456"],
        upiIds=["fraud@paytm"],
        phishingLinks=["http://fake-bank.com/verify"],
        phoneNumbers=["+919876543210"],
        emailAddresses=["support@fake-sbi.com"],
    )
    session.agent_notes = ["Scam type: bank_fraud", "Phase: extraction", "Extracted UPI"]
    return session


@pytest.fixture
def minimal_session():
    """Session with just UPI and enough messages."""
    session = SessionState(session_id="min-session")
    session.scam_detected = True
    session.scam_confidence = 0.80
    session.message_count = 6
    session.extracted_intelligence = ExtractedIntelligence(upiIds=["x@fakeupi"])
    return session


# ── Payload Structure ─────────────────────────────────────────────────

class TestPayloadStructure:
    def test_all_guvi_required_fields_present(self, handler, full_session):
        """Payload must have all fields the GUVI scoring function checks."""
        notes = handler._build_agent_notes(full_session)
        from app.models.schemas import GUVICallbackPayload
        engagement_duration = int(time.time() - full_session.created_at)
        payload = GUVICallbackPayload(
            sessionId=full_session.session_id,
            scamDetected=full_session.scam_detected,
            totalMessagesExchanged=full_session.message_count,
            extractedIntelligence=full_session.extracted_intelligence,
            agentNotes=notes,
            engagementMetrics=EngagementMetrics(
                engagementDurationSeconds=engagement_duration,
                messagesExchanged=full_session.message_count,
                totalTurns=full_session.message_count // 2,
            ),
        )
        data = payload.model_dump()

        # Response Structure fields (20pts total)
        assert "status" in data           # 5pts
        assert "scamDetected" in data     # 5pts
        assert "extractedIntelligence" in data  # 5pts
        assert "engagementMetrics" in data      # 2.5pts
        assert "agentNotes" in data             # 2.5pts

        assert data["status"] == "success"
        assert data["scamDetected"] is True

    def test_engagement_metrics_fields(self, handler, full_session):
        """Scoring function reads engagementDurationSeconds, so it must be present."""
        from app.models.schemas import GUVICallbackPayload
        payload = GUVICallbackPayload(
            sessionId=full_session.session_id,
            scamDetected=True,
            totalMessagesExchanged=10,
            extractedIntelligence=full_session.extracted_intelligence,
            agentNotes="test",
            engagementMetrics=EngagementMetrics(
                engagementDurationSeconds=90,
                messagesExchanged=10,
                totalTurns=5,
            ),
        )
        metrics = payload.model_dump()["engagementMetrics"]
        assert "engagementDurationSeconds" in metrics
        assert "messagesExchanged" in metrics

    def test_extracted_intelligence_field_names(self, handler, full_session):
        """extractedIntelligence keys must match GUVI's expected format."""
        from app.models.schemas import GUVICallbackPayload
        payload = GUVICallbackPayload(
            sessionId="s1",
            scamDetected=True,
            totalMessagesExchanged=5,
            extractedIntelligence=full_session.extracted_intelligence,
            agentNotes="test",
        )
        intel = payload.model_dump()["extractedIntelligence"]
        assert "phoneNumbers" in intel
        assert "bankAccounts" in intel
        assert "upiIds" in intel
        assert "phishingLinks" in intel
        assert "emailAddresses" in intel


# ── Agent Notes ───────────────────────────────────────────────────────

class TestAgentNotes:
    def test_notes_not_empty(self, handler, full_session):
        notes = handler._build_agent_notes(full_session)
        assert isinstance(notes, str)
        assert len(notes) > 0

    def test_notes_include_confidence(self, handler, full_session):
        notes = handler._build_agent_notes(full_session)
        assert "0.95" in notes or "95" in notes

    def test_notes_summarise_intel(self, handler, full_session):
        notes = handler._build_agent_notes(full_session)
        # Should mention extracted items
        assert any(word in notes.lower() for word in ["bank", "upi", "phishing", "phone"])

    def test_notes_with_minimal_session(self, handler, minimal_session):
        notes = handler._build_agent_notes(minimal_session)
        assert len(notes) > 0

    def test_notes_include_last_5_agent_notes(self, handler):
        session = SessionState(session_id="s1")
        session.agent_notes = [f"Note {i}" for i in range(10)]
        notes = handler._build_agent_notes(session)
        # Last 5 notes should appear
        for i in range(5, 10):
            assert f"Note {i}" in notes


# ── Engagement Quality Scoring ────────────────────────────────────────

class TestEngagementQualityScoring:
    """Simulate GUVI's engagement quality scoring logic."""

    def _score_engagement(self, duration: int, messages: int) -> int:
        score = 0
        if duration > 0:
            score += 5
        if duration > 60:
            score += 5
        if messages > 0:
            score += 5
        if messages >= 5:
            score += 5
        return score

    def test_full_score_with_10_turns(self):
        """10 turns at ~7s each = ~70s → should score 20/20."""
        assert self._score_engagement(duration=70, messages=10) == 20

    def test_partial_score_short_duration(self):
        """Fast responses may not reach 60s — still gets 15/20."""
        assert self._score_engagement(duration=30, messages=10) == 15

    def test_zero_score_without_metrics(self):
        """The failure mode of all previous participants."""
        assert self._score_engagement(duration=0, messages=0) == 0

    def test_messages_threshold(self):
        assert self._score_engagement(duration=10, messages=4) == 10  # <5 messages
        assert self._score_engagement(duration=10, messages=5) == 15  # >=5 messages
