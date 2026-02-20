"""Session state management for honeypot conversations."""

from typing import Dict, Optional
import threading
from app.models.schemas import SessionState, Message, ExtractedIntelligence


class SessionManager:
    """Manages session state for ongoing honeypot conversations."""

    def __init__(self):
        """Initialize session manager with in-memory storage."""
        self._sessions: Dict[str, SessionState] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()  # Protects _locks dict

    def _get_session_lock(self, session_id: str) -> threading.Lock:
        """Get or create a lock for a specific session.

        Args:
            session_id: Session identifier

        Returns:
            Thread lock for this session
        """
        with self._global_lock:
            if session_id not in self._locks:
                self._locks[session_id] = threading.Lock()
            return self._locks[session_id]

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
        scam_type: str = None,
        extracted_intel: ExtractedIntelligence = None,
        agent_note: str = None,
        engagement_phase: str = None,
        persona_used: str = None,
        red_flags: list = None
    ) -> SessionState:
        """
        Update session state with new information.

        Thread-safe: Uses session-specific lock to prevent race conditions.

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
        # Acquire lock for this specific session
        with self._get_session_lock(session_id):
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

            if scam_type is not None:
                session.scam_type = scam_type

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

            # Accumulate red flags (deduplicated)
            if red_flags:
                for flag in red_flags:
                    if flag and flag not in session.detected_red_flags:
                        session.detected_red_flags.append(flag)

            # Store persona context
            if persona_used:
                session.persona_context = persona_used
                # Track personas used
                if persona_used not in session.personas_used:
                    session.personas_used.append(persona_used)

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
            emailAddresses=list(set(existing.emailAddresses + new.emailAddresses)),
            suspiciousKeywords=list(set(existing.suspiciousKeywords + new.suspiciousKeywords)),
            caseIds=list(set(existing.caseIds + new.caseIds)),
            policyNumbers=list(set(existing.policyNumbers + new.policyNumbers)),
            orderNumbers=list(set(existing.orderNumbers + new.orderNumbers)),
        )

    def should_trigger_callback(
        self,
        session_id: str,
        min_messages: int = 5,
        max_messages: int = 20
    ) -> bool:
        """
        Determine if GUVI callback should be triggered.

        STRATEGY: Send callback on every turn once scam is confirmed so the
        final callback always reflects the most complete conversation state.
        GUVI evaluates the last submitted result after all turns complete.

        Args:
            session_id: Session identifier
            min_messages: Minimum messages before first callback
            max_messages: Force callback even if scam not confirmed

        Returns:
            True if callback should be triggered
        """
        session = self.get_session(session_id)
        if not session:
            return False

        # Send on every turn once scam is confirmed and min threshold reached
        if session.scam_detected and session.message_count >= min_messages:
            return True

        # Safety: force callback at max messages even if scam not confirmed
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

        Thread-safe: Uses session lock during deletion.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        with self._get_session_lock(session_id):
            if session_id in self._sessions:
                del self._sessions[session_id]
                # Clean up lock
                with self._global_lock:
                    if session_id in self._locks:
                        del self._locks[session_id]
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
