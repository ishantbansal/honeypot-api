"""Pydantic models for API request/response schemas."""

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


class HoneypotResponse(BaseModel):
    """Response from the honeypot API."""
    status: Literal["success", "error"] = "success"
    reply: str = Field(..., description="Agent's response message")


class ExtractedIntelligence(BaseModel):
    """Intelligence extracted from scammer conversation."""
    bankAccounts: List[str] = Field(default_factory=list)
    upiIds: List[str] = Field(default_factory=list)
    phishingLinks: List[str] = Field(default_factory=list)
    phoneNumbers: List[str] = Field(default_factory=list)
    suspiciousKeywords: List[str] = Field(default_factory=list)


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
    scam_detected: bool = False
    scam_confidence: float = 0.0
    message_count: int = 0
    conversation_history: List[Message] = Field(default_factory=list)
    extracted_intelligence: ExtractedIntelligence = Field(default_factory=ExtractedIntelligence)
    agent_notes: List[str] = Field(default_factory=list)
    persona_context: str = ""
    engagement_phase: Literal["detection", "engagement", "extraction", "completed"] = "detection"
