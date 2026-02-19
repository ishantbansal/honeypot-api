"""Pydantic models for API request/response schemas."""

import time
from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class Message(BaseModel):
    """A single message in the conversation."""
    sender: Literal["scammer", "user"]
    text: str
    timestamp: int


class Metadata(BaseModel):
    """Metadata about the conversation context."""
    channel: str = Field(default="SMS", description="Communication channel")
    language: str = Field(default="English", description="Language used")
    locale: str = Field(default="IN", description="Country/region code")


class HoneypotRequest(BaseModel):
    """Incoming request to the honeypot API."""
    sessionId: str = Field(..., description="Unique session identifier")
    message: Message = Field(..., description="Latest incoming message")
    conversationHistory: List[Message] = Field(
        default_factory=list,
        description="Previous messages in this conversation"
    )
    metadata: Optional[Metadata] = Field(
        default_factory=Metadata,
        description="Conversation metadata"
    )


class ExtractedIntelligence(BaseModel):
    """Intelligence extracted from scammer conversation."""
    bankAccounts: List[str] = Field(default_factory=list)
    upiIds: List[str] = Field(default_factory=list)
    phishingLinks: List[str] = Field(default_factory=list)
    phoneNumbers: List[str] = Field(default_factory=list)
    emailAddresses: List[str] = Field(default_factory=list)
    suspiciousKeywords: List[str] = Field(default_factory=list)


class EngagementMetrics(BaseModel):
    """Engagement quality metrics for GUVI scoring."""
    engagementDurationSeconds: int = 0
    messagesExchanged: int = 0
    totalTurns: int = 0


class HoneypotResponse(BaseModel):
    """Response from the honeypot API."""
    status: Literal["success", "error"] = "success"
    reply: str = Field(..., description="Agent's response message")
    # GUVI scoring fields (evaluated per-turn)
    scamDetected: bool = False
    totalMessagesExchanged: int = 0
    extractedIntelligence: Optional[ExtractedIntelligence] = None
    agentNotes: str = ""
    engagementMetrics: Optional[EngagementMetrics] = None


class GUVICallbackPayload(BaseModel):
    """Payload sent to GUVI evaluation endpoint."""
    sessionId: str
    scamDetected: bool
    totalMessagesExchanged: int
    extractedIntelligence: ExtractedIntelligence
    agentNotes: str = Field(
        description="Summary of scammer behavior and tactics"
    )


class SessionState(BaseModel):
    """Internal session state management."""
    session_id: str
    created_at: float = Field(default_factory=time.time)
    scam_detected: bool = False
    scam_confidence: float = 0.0
    message_count: int = 0
    conversation_history: List[Message] = Field(default_factory=list)
    extracted_intelligence: ExtractedIntelligence = Field(default_factory=ExtractedIntelligence)
    agent_notes: List[str] = Field(default_factory=list)
    persona_context: str = ""
    personas_used: List[str] = Field(default_factory=list)
    engagement_phase: Literal["detection", "engagement", "extraction", "completed"] = "detection"
