"""Tests for SessionManager — session CRUD, intelligence merging, callback trigger logic."""

import pytest
from app.utils.session_manager import SessionManager
from app.models.schemas import Message, ExtractedIntelligence


@pytest.fixture
def manager():
    """Fresh SessionManager for each test."""
    return SessionManager()


@pytest.fixture
def scammer_msg():
    return Message(sender="scammer", text="Send OTP now!", timestamp=1000)


# ── Session CRUD ──────────────────────────────────────────────────────

class TestSessionCRUD:
    def test_create_and_get(self, manager):
        session = manager.create_session("sess-1")
        assert session.session_id == "sess-1"
        assert manager.get_session("sess-1") is session

    def test_get_missing_returns_none(self, manager):
        assert manager.get_session("nonexistent") is None

    def test_get_or_create_creates_new(self, manager):
        session = manager.get_or_create_session("new-sess")
        assert session.session_id == "new-sess"
        assert manager.get_session_count() == 1

    def test_get_or_create_returns_existing(self, manager):
        s1 = manager.create_session("sess-x")
        s2 = manager.get_or_create_session("sess-x")
        assert s1 is s2

    def test_delete_session(self, manager):
        manager.create_session("to-delete")
        assert manager.delete_session("to-delete") is True
        assert manager.get_session("to-delete") is None

    def test_delete_missing_returns_false(self, manager):
        assert manager.delete_session("ghost") is False

    def test_session_count(self, manager):
        manager.create_session("a")
        manager.create_session("b")
        assert manager.get_session_count() == 2


# ── Session Updates ───────────────────────────────────────────────────

class TestSessionUpdate:
    def test_message_increments_count(self, manager, scammer_msg):
        session = manager.update_session("s1", message=scammer_msg)
        assert session.message_count == 1
        assert len(session.conversation_history) == 1

    def test_scam_detection_update(self, manager):
        session = manager.update_session("s1", scam_detected=True, scam_confidence=0.92)
        assert session.scam_detected is True
        assert session.scam_confidence == pytest.approx(0.92)

    def test_agent_note_appended(self, manager):
        manager.update_session("s1", agent_note="Scam type: UPI fraud")
        session = manager.update_session("s1", agent_note="Phase: extraction")
        assert len(session.agent_notes) == 2

    def test_engagement_phase_update(self, manager):
        session = manager.update_session("s1", engagement_phase="extraction")
        assert session.engagement_phase == "extraction"

    def test_persona_tracked(self, manager):
        manager.update_session("s1", persona_used="honeypot")
        session = manager.update_session("s1", persona_used="skeptical")
        assert "honeypot" in session.personas_used
        assert "skeptical" in session.personas_used

    def test_persona_not_duplicated(self, manager):
        manager.update_session("s1", persona_used="normal")
        session = manager.update_session("s1", persona_used="normal")
        assert session.personas_used.count("normal") == 1


# ── Intelligence Merging ──────────────────────────────────────────────

class TestMergeIntelligence:
    def test_merge_deduplicates(self, manager):
        intel1 = ExtractedIntelligence(phoneNumbers=["+919876543210"])
        intel2 = ExtractedIntelligence(phoneNumbers=["+919876543210", "+918765432109"])
        manager.update_session("s1", extracted_intel=intel1)
        session = manager.update_session("s1", extracted_intel=intel2)
        assert len(session.extracted_intelligence.phoneNumbers) == 2

    def test_merge_accumulates_all_fields(self, manager):
        intel1 = ExtractedIntelligence(bankAccounts=["1234567890123456"])
        intel2 = ExtractedIntelligence(
            upiIds=["fraud@paytm"],
            phishingLinks=["http://fake.com"],
            emailAddresses=["x@fake.com"],
        )
        manager.update_session("s1", extracted_intel=intel1)
        session = manager.update_session("s1", extracted_intel=intel2)
        intel = session.extracted_intelligence
        assert len(intel.bankAccounts) == 1
        assert len(intel.upiIds) == 1
        assert len(intel.phishingLinks) == 1
        assert len(intel.emailAddresses) == 1

    def test_email_addresses_not_dropped(self, manager):
        """Regression: emailAddresses was silently dropped on each merge."""
        intel = ExtractedIntelligence(emailAddresses=["scam@fake.com"])
        manager.update_session("s1", extracted_intel=intel)
        # Merge again with empty intel
        session = manager.update_session("s1", extracted_intel=ExtractedIntelligence())
        assert "scam@fake.com" in session.extracted_intelligence.emailAddresses


# ── Callback Trigger Logic ────────────────────────────────────────────

class TestCallbackTrigger:
    def _setup_scam_session(self, manager, n_messages=5, intel=None):
        """Helper: create confirmed scam session with n messages."""
        manager.update_session("s1", scam_detected=True, scam_confidence=0.9)
        msg = Message(sender="scammer", text="test", timestamp=1000)
        for _ in range(n_messages):
            manager.update_session("s1", message=msg)
        if intel:
            manager.update_session("s1", extracted_intel=intel)

    def test_no_trigger_if_not_scam(self, manager):
        msg = Message(sender="scammer", text="hello", timestamp=1000)
        for _ in range(10):
            manager.update_session("s1", message=msg)
        assert manager.should_trigger_callback("s1") is False

    def test_no_trigger_below_min_messages(self, manager):
        self._setup_scam_session(manager, n_messages=3,
                                  intel=ExtractedIntelligence(upiIds=["x@paytm"]))
        assert manager.should_trigger_callback("s1", min_messages=5) is False

    def test_triggers_with_intel_and_min_messages(self, manager):
        self._setup_scam_session(manager, n_messages=5,
                                  intel=ExtractedIntelligence(upiIds=["x@paytm"]))
        assert manager.should_trigger_callback("s1", min_messages=5) is True

    def test_triggers_at_max_messages_even_without_intel(self, manager):
        self._setup_scam_session(manager, n_messages=20)
        assert manager.should_trigger_callback("s1", max_messages=20) is True

    def test_no_duplicate_callback_after_completed(self, manager):
        """Once completed, should never trigger again."""
        self._setup_scam_session(manager, n_messages=5,
                                  intel=ExtractedIntelligence(phoneNumbers=["+919876543210"]))
        manager.update_session("s1", engagement_phase="completed")
        assert manager.should_trigger_callback("s1") is False

    def test_returns_false_for_missing_session(self, manager):
        assert manager.should_trigger_callback("ghost-session") is False
