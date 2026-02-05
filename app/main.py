"""Main FastAPI application for Agentic Honeypot."""

from fastapi import FastAPI, HTTPException, Security, Header
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import os

from app.config import settings
from app.models.schemas import HoneypotRequest, HoneypotResponse, Message
from app.utils.llm_client import create_llm_client, BaseLLMClient
from app.detection.scam_detector import ScamDetector
from app.extraction.intelligence_extractor import IntelligenceExtractor
from app.agents.persona_orchestrator import PersonaOrchestrator
from app.utils.session_manager import session_manager
from app.utils.guvi_callback import create_guvi_callback_handler
from app.utils.response_validator import create_response_validator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Debug mode
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Global instances
llm_client: BaseLLMClient = None
scam_detector: ScamDetector = None
intel_extractor: IntelligenceExtractor = None
persona_orchestrator: PersonaOrchestrator = None
response_validator = None
guvi_callback = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup and cleanup on shutdown."""
    global llm_client, scam_detector, intel_extractor, persona_orchestrator, response_validator, guvi_callback

    logger.info("Initializing Honeypot API...")

    # Create LLM client based on configuration
    try:
        llm_client = create_llm_client(
            provider=settings.llm_provider,
            api_key=(
                settings.openai_api_key if settings.llm_provider == "openai"
                else settings.azure_openai_api_key if settings.llm_provider == "azure_openai"
                else settings.anthropic_api_key
            ),
            model=settings.llm_model,
            azure_endpoint=settings.azure_openai_endpoint,
            azure_api_version=settings.azure_openai_api_version,
            azure_deployment_name=settings.azure_openai_deployment_name
        )
        logger.info(f"LLM client initialized: {settings.llm_provider} / {settings.llm_model}")
    except Exception as e:
        logger.error(f"Failed to initialize LLM client: {e}")
        raise

    # Initialize components
    scam_detector = ScamDetector(llm_client)
    intel_extractor = IntelligenceExtractor(llm_client)
    persona_orchestrator = PersonaOrchestrator(llm_client)
    response_validator = create_response_validator(llm_client)
    guvi_callback = create_guvi_callback_handler(settings.guvi_callback_url)

    logger.info("All components initialized successfully")
    logger.info(f"GUVI callback URL: {settings.guvi_callback_url}")

    yield

    # Cleanup
    logger.info("Shutting down Honeypot API...")


# Create FastAPI app
app = FastAPI(
    title="Agentic Honeypot API",
    description="AI-powered honeypot for scam detection and intelligence extraction",
    version="1.0.0",
    lifespan=lifespan
)

# API Key authentication
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify API key from request header."""
    if api_key != settings.api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return api_key


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Agentic Honeypot API",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "active_sessions": session_manager.get_session_count()
    }


@app.post("/api/v1/honeypot", response_model=HoneypotResponse)
async def honeypot_endpoint(
    request: HoneypotRequest,
    api_key: str = Security(verify_api_key)
):
    """
    Main honeypot endpoint that processes incoming messages.

    Args:
        request: Incoming message request
        api_key: API key for authentication

    Returns:
        HoneypotResponse with agent's reply
    """
    try:
        logger.info(f"Processing message for session: {request.sessionId}")

        # Get or create session
        session = session_manager.get_or_create_session(request.sessionId)

        # Add incoming message to history
        session = session_manager.update_session(
            session_id=request.sessionId,
            message=request.message
        )

        # Perform scam detection on full conversation
        is_scam, confidence, scam_details = await scam_detector.detect_scam(
            message=request.message.text,
            conversation_history=[msg.model_dump() for msg in session.conversation_history]
        )

        logger.info(
            f"Session {request.sessionId}: "
            f"Scam={is_scam}, Confidence={confidence:.2f}, "
            f"Type={scam_details.get('scam_type')}"
        )

        # Extract intelligence from conversation
        extracted_intel = await intel_extractor.extract_intelligence(
            conversation_history=[msg.model_dump() for msg in session.conversation_history]
        )

        # Update session with detection results and extracted intelligence
        session = session_manager.update_session(
            session_id=request.sessionId,
            scam_detected=is_scam and confidence >= settings.scam_confidence_threshold,
            scam_confidence=confidence,
            extracted_intel=extracted_intel,
            agent_note=f"Scam type: {scam_details.get('scam_type', 'unknown')}"
        )

        # Generate response using appropriate persona (with extraction targeting)
        response_text, persona_name = await persona_orchestrator.generate_response(
            latest_message=request.message.text,
            conversation_history=[msg.model_dump() for msg in session.conversation_history],
            scam_confidence=confidence,
            scam_details=scam_details,
            extracted_intelligence=session.extracted_intelligence.model_dump()
        )

        if DEBUG:
            print(f"[DEBUG] After persona generation: response_text='{response_text}', persona='{persona_name}'")
        logger.info(f"Session {request.sessionId}: Using persona '{persona_name}'")

        # Validate and fix response with guardrails
        is_valid, fixed_response, warnings = response_validator.validate_response(
            response=response_text,
            persona_name=persona_name,
            scam_confidence=confidence
        )

        if warnings:
            logger.warning(f"Session {request.sessionId}: Response warnings: {warnings}")

        if not is_valid:
            logger.error(f"Session {request.sessionId}: Invalid response, using fallback")
            fixed_response = response_validator.generate_safe_fallback(persona_name)

        if DEBUG:
            print(f"[DEBUG] After validation: is_valid={is_valid}, fixed_response='{fixed_response}', warnings={warnings}")

        # Use fixed response
        response_text = fixed_response

        # Add agent response to conversation history
        agent_message = Message(
            sender="user",
            text=response_text,
            timestamp=request.message.timestamp
        )
        session = session_manager.update_session(
            session_id=request.sessionId,
            message=agent_message,
            persona_used=persona_name
        )

        # Check if should trigger GUVI callback
        should_callback = session_manager.should_trigger_callback(
            session_id=request.sessionId,
            min_messages=settings.min_messages_before_callback,
            max_messages=settings.max_conversation_turns
        )

        if should_callback:
            logger.info(f"Triggering GUVI callback for session {request.sessionId}")

            callback_result = await guvi_callback.send_final_result(session)

            if callback_result["success"]:
                logger.info(f"GUVI callback successful for session {request.sessionId}")
                # Mark session as completed
                session_manager.update_session(
                    session_id=request.sessionId,
                    engagement_phase="completed"
                )
            else:
                logger.error(
                    f"GUVI callback failed for session {request.sessionId}: "
                    f"{callback_result.get('message')}"
                )

        # Return response
        return HoneypotResponse(
            status="success",
            reply=response_text
        )

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/api/v1/session/{session_id}")
async def get_session_info(
    session_id: str,
    api_key: str = Security(verify_api_key)
):
    """
    Get information about a session (for debugging).

    Args:
        session_id: Session identifier
        api_key: API key for authentication

    Returns:
        Session information
    """
    session = session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.session_id,
        "scam_detected": session.scam_detected,
        "scam_confidence": session.scam_confidence,
        "message_count": session.message_count,
        "engagement_phase": session.engagement_phase,
        "extracted_intelligence": session.extracted_intelligence.model_dump(),
        "summary": session_manager.get_session_summary(session_id)
    }


@app.delete("/api/v1/session/{session_id}")
async def delete_session(
    session_id: str,
    api_key: str = Security(verify_api_key)
):
    """
    Delete a session (for cleanup).

    Args:
        session_id: Session identifier
        api_key: API key for authentication

    Returns:
        Deletion confirmation
    """
    deleted = session_manager.delete_session(session_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": f"Session {session_id} deleted successfully"}


@app.get("/api/v1/sessions")
async def list_sessions(api_key: str = Security(verify_api_key)):
    """
    List all active sessions (for monitoring).

    Args:
        api_key: API key for authentication

    Returns:
        List of session summaries
    """
    sessions = session_manager.get_all_sessions()

    return {
        "total_sessions": len(sessions),
        "sessions": [
            {
                "session_id": sid,
                "summary": session_manager.get_session_summary(sid)
            }
            for sid in sessions.keys()
        ]
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
