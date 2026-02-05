"""Session state management for honeypot conversations."""

from typing import Dict, Optional
from app.models.schemas import SessionState, Message, ExtractedIntelligence


class SessionManager:
    """Manages session state for ongoing honeypot conversations."""

    def __init__(self):
        """Initialize session manager with in-memory storage."""
        self._sessions: Dict[str, SessionState] = {}

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        Get session state by ID.

        Args:
            session_id: Unique session identifier

        Returns:
            SessionState or None if not found
        """
        return self._sessions.get(session_id)

    def create_session(self, session_id: str) -> SessionState:
        """
        Create new session state.

        Args:
            session_id: Unique session identifier

        Returns:
            Created SessionState
        """
        session = SessionState(session_id=session_id)
        self._sessions[session_id] = session
        return session

    def get_or_create_session(self, session_id: str) -> SessionState:
        """
        Get existing session or create new one.

        Args:
            session_id: Unique session identifier

        Returns:
            SessionState (existing or newly created)
        """
        session = self.get_session(session_id)
        if session is None:
            session = self.create_session(session_id)
        return session

    def update_session(
        self,
        session_id: str,
        message: Optional[Message] = None,
        scam_detected: bool = None,
        scam_confidence: float = None,
        extracted_intel: ExtractedIntelligence = None,
        agent_note: str = None,
        engagement_phase: str = None,
        persona_used: str = None
    ) -> SessionState:
        """
        Update session state with new information.

        Args:
            session_id: Session identifier
            message: New message to add to history (optional)
            scam_detected: Update scam detection status
            scam_confidence: Update confidence score
            extracted_intel: Update extracted intelligence
            agent_note: Add agent observation note
            engagement_phase: Update engagement phase
            persona_used: Track which persona was used

        Returns:
            Updated SessionState
        """
        session = self.get_or_create_session(session_id)

        # Add message to history if provided
        if message:
            session.conversation_history.append(message)
            session.message_count += 1

        # Update scam detection
        if scam_detected is not None:
            session.scam_detected = scam_detected

        if scam_confidence is not None:
            session.scam_confidence = scam_confidence

        # Update extracted intelligence
        if extracted_intel:
            session.extracted_intelligence = self._merge_intelligence(
                session.extracted_intelligence,
                extracted_intel
            )

        # Add agent notes
        if agent_note:
            session.agent_notes.append(agent_note)

        # Update engagement phase
        if engagement_phase:
            session.engagement_phase = engagement_phase

        # Store persona context
        if persona_used:
            session.persona_context = persona_used

        return session

    def _merge_intelligence(
        self,
        existing: ExtractedIntelligence,
        new: ExtractedIntelligence
    ) -> ExtractedIntelligence:
        """Merge new intelligence with existing (union)."""
        return ExtractedIntelligence(
            bankAccounts=list(set(existing.bankAccounts + new.bankAccounts)),
            upiIds=list(set(existing.upiIds + new.upiIds)),
            phishingLinks=list(set(existing.phishingLinks + new.phishingLinks)),
            phoneNumbers=list(set(existing.phoneNumbers + new.phoneNumbers)),
            suspiciousKeywords=list(set(existing.suspiciousKeywords + new.suspiciousKeywords))
        )

    def should_trigger_callback(
        self,
        session_id: str,
        min_messages: int = 5,
        max_messages: int = 20
    ) -> bool:
        """
        Determine if GUVI callback should be triggered.

        Triggers if:
        1. Critical intelligence extracted AND minimum messages met
        2. Maximum messages reached
        3. High confidence scam detected with some intelligence

        Args:
            session_id: Session identifier
            min_messages: Minimum messages before callback
            max_messages: Maximum messages before forcing callback

        Returns:
            True if callback should be triggered
        """
        session = self.get_session(session_id)
        if not session:
            return False

        # Don't trigger if not confirmed scam
        if not session.scam_detected or session.scam_confidence < 0.7:
            return False

        intel = session.extracted_intelligence

        # Check if we have critical intelligence
        has_critical_intel = (
            len(intel.bankAccounts) > 0 or
            len(intel.upiIds) > 0 or
            len(intel.phishingLinks) > 0 or
            len(intel.phoneNumbers) > 0
        )

        # Check if we have substantial intelligence (multiple pieces)
        intel_count = (
            len(intel.bankAccounts) +
            len(intel.upiIds) +
            len(intel.phishingLinks) +
            len(intel.phoneNumbers)
        )
        has_substantial_intel = intel_count >= 2

        # Trigger conditions
        if has_substantial_intel and session.message_count >= min_messages:
            return True

        if has_critical_intel and session.message_count >= min_messages * 1.5:
            return True

        if session.message_count >= max_messages:
            return True

        return False

    def get_session_summary(self, session_id: str) -> Optional[str]:
        """
        Get human-readable summary of session.

        Args:
            session_id: Session identifier

        Returns:
            Summary string or None
        """
        session = self.get_session(session_id)
        if not session:
            return None

        intel = session.extracted_intelligence
        summary_parts = []

        summary_parts.append(f"Session: {session_id}")
        summary_parts.append(f"Messages: {session.message_count}")
        summary_parts.append(f"Scam Detected: {session.scam_detected} (confidence: {session.scam_confidence:.2f})")
        summary_parts.append(f"Phase: {session.engagement_phase}")

        if intel.bankAccounts:
            summary_parts.append(f"Bank Accounts: {len(intel.bankAccounts)}")
        if intel.upiIds:
            summary_parts.append(f"UPI IDs: {len(intel.upiIds)}")
        if intel.phishingLinks:
            summary_parts.append(f"Phishing Links: {len(intel.phishingLinks)}")
        if intel.phoneNumbers:
            summary_parts.append(f"Phone Numbers: {len(intel.phoneNumbers)}")

        return " | ".join(summary_parts)

    def delete_session(self, session_id: str) -> bool:
        """
        Delete session from storage.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def get_all_sessions(self) -> Dict[str, SessionState]:
        """Get all active sessions."""
        return self._sessions.copy()

    def get_session_count(self) -> int:
        """Get count of active sessions."""
        return len(self._sessions)


# Global session manager instance
session_manager = SessionManager()
