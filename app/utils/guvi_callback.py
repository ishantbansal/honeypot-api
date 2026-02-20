"""GUVI callback handler for sending final results."""

import httpx
import time
from typing import Dict, Any
from app.models.schemas import SessionState, GUVICallbackPayload, ExtractedIntelligence, EngagementMetrics


class GUVICallbackHandler:
    """Handles callbacks to GUVI evaluation endpoint."""

    def __init__(self, callback_url: str, timeout: int = 10):
        """
        Initialize GUVI callback handler.

        Args:
            callback_url: GUVI evaluation endpoint URL
            timeout: Request timeout in seconds
        """
        self.callback_url = callback_url
        self.timeout = timeout

    async def send_final_result(self, session_state: SessionState) -> Dict[str, Any]:
        """
        Send final result to GUVI evaluation endpoint.

        Args:
            session_state: Session state containing conversation data

        Returns:
            Response data from GUVI API
        """
        # Build agent notes summary
        agent_notes = self._build_agent_notes(session_state)

        # Build engagement metrics
        engagement_duration = int(time.time() - session_state.created_at)
        engagement_metrics = EngagementMetrics(
            engagementDurationSeconds=engagement_duration,
            messagesExchanged=session_state.message_count,
            totalTurns=session_state.message_count // 2
        )

        # Create payload
        payload = GUVICallbackPayload(
            sessionId=session_state.session_id,
            scamDetected=session_state.scam_detected,
            totalMessagesExchanged=session_state.message_count,
            extractedIntelligence=session_state.extracted_intelligence,
            agentNotes=agent_notes,
            engagementMetrics=engagement_metrics
        )

        # Log payload for verification
        print(f"\n[GUVI CALLBACK PAYLOAD] Sending to {self.callback_url}:")
        print(payload.model_dump_json(indent=2))
        print("-" * 50 + "\n")

        # Send POST request
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.callback_url,
                    json=payload.model_dump(),
                    headers={"Content-Type": "application/json"}
                )

                response.raise_for_status()

                return {
                    "success": True,
                    "status_code": response.status_code,
                    "response": response.json() if response.text else None,
                    "message": "Callback sent successfully"
                }

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "status_code": e.response.status_code,
                "error": str(e),
                "message": f"HTTP error: {e.response.status_code}"
            }

        except httpx.RequestError as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Request error: {str(e)}"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Unexpected error: {str(e)}"
            }

    def send_final_result_sync(self, session_state: SessionState) -> Dict[str, Any]:
        """Synchronous version of send_final_result."""
        agent_notes = self._build_agent_notes(session_state)

        engagement_duration = int(time.time() - session_state.created_at)
        engagement_metrics = EngagementMetrics(
            engagementDurationSeconds=engagement_duration,
            messagesExchanged=session_state.message_count,
            totalTurns=session_state.message_count // 2
        )

        payload = GUVICallbackPayload(
            sessionId=session_state.session_id,
            scamDetected=session_state.scam_detected,
            totalMessagesExchanged=session_state.message_count,
            extractedIntelligence=session_state.extracted_intelligence,
            agentNotes=agent_notes,
            engagementMetrics=engagement_metrics
        )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.callback_url,
                    json=payload.model_dump(),
                    headers={"Content-Type": "application/json"}
                )

                response.raise_for_status()

                return {
                    "success": True,
                    "status_code": response.status_code,
                    "response": response.json() if response.text else None,
                    "message": "Callback sent successfully"
                }

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "status_code": e.response.status_code,
                "error": str(e),
                "message": f"HTTP error: {e.response.status_code}"
            }

        except httpx.RequestError as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Request error: {str(e)}"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Unexpected error: {str(e)}"
            }

    def _build_agent_notes(self, session_state: SessionState) -> str:
        """
        Build comprehensive agent notes from session data.

        Args:
            session_state: Session state

        Returns:
            Formatted agent notes string
        """
        notes = []

        # Scam confidence and phase
        notes.append(
            f"Scam confidence: {session_state.scam_confidence:.2f}, "
            f"Engagement phase: {session_state.engagement_phase}"
        )

        # Intelligence summary
        intel = session_state.extracted_intelligence
        intel_summary = []
        if intel.bankAccounts:
            intel_summary.append(f"{len(intel.bankAccounts)} bank accounts")
        if intel.upiIds:
            intel_summary.append(f"{len(intel.upiIds)} UPI IDs")
        if intel.phishingLinks:
            intel_summary.append(f"{len(intel.phishingLinks)} phishing links")
        if intel.phoneNumbers:
            intel_summary.append(f"{len(intel.phoneNumbers)} phone numbers")

        if intel_summary:
            notes.append(f"Extracted: {', '.join(intel_summary)}")

        # Add stored agent notes
        if session_state.agent_notes:
            notes.extend(session_state.agent_notes[-5:])  # Last 5 notes

        return ". ".join(notes)


def create_guvi_callback_handler(callback_url: str) -> GUVICallbackHandler:
    """
    Factory function to create GUVI callback handler.

    Args:
        callback_url: GUVI evaluation endpoint URL

    Returns:
        Initialized GUVICallbackHandler
    """
    return GUVICallbackHandler(callback_url=callback_url)
