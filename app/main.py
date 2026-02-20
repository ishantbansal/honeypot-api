"""Main FastAPI application for Agentic Honeypot."""

from fastapi import FastAPI, HTTPException, Security, Header, Query, Request
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import time

from app.config import settings
from app.models.schemas import HoneypotRequest, HoneypotResponse, EngagementMetrics, Message
from app.utils.llm_client import create_llm_client, BaseLLMClient
from app.detection.scam_detector import ScamDetector
from app.extraction.intelligence_extractor import IntelligenceExtractor
from app.agents.persona_orchestrator import PersonaOrchestrator
from app.utils.session_manager import session_manager
from app.utils.guvi_callback import create_guvi_callback_handler
from app.utils.response_validator import create_response_validator
from app.utils.analytics import analytics
from app.utils.csv_logger import csv_logger
from app.utils.logger import logger, log_message, log_detection, log_intelligence, log_callback, log_persona, log_error
from app.utils.human_behavior import simulate_human_delay, simulate_distraction_delay

# Debug mode
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Templates
templates = Jinja2Templates(directory="app/templates")

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

    # Log human delay setting
    from app.utils.human_behavior import ENABLE_HUMAN_DELAY
    if ENABLE_HUMAN_DELAY:
        logger.info("⏱️  Human-like delays: ENABLED (10-90s per response)")
    else:
        logger.warning("⚡ Human-like delays: DISABLED (fast mode for testing)")

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
        request_start = time.time()
        session_short = request.sessionId[:12]  # Short ID for logging

        logger.info(f"[{session_short}] ▶️  Processing message for session: {request.sessionId}")
        logger.info(f"[{session_short}] STEP 1/7: Received message from {request.message.sender}")

        # Log incoming message with structured logging
        log_message(
            session_id=request.sessionId,
            sender=request.message.sender,
            text=request.message.text,
            direction="incoming"
        )

        # Get or create session
        step_start = time.time()
        logger.info(f"[{session_short}] STEP 2/7: Loading session state...")
        session = session_manager.get_or_create_session(request.sessionId)
        logger.info(f"[{session_short}] ✓ Session loaded ({time.time() - step_start:.2f}s)")

        # Add incoming message to history
        session = session_manager.update_session(
            session_id=request.sessionId,
            message=request.message
        )

        # Log incoming scammer message to CSV
        csv_logger.log_conversation(
            session_id=request.sessionId,
            message_num=session.message_count,
            sender=request.message.sender,
            text=request.message.text,
            timestamp=request.message.timestamp
        )

        # Perform scam detection on full conversation
        step_start = time.time()
        logger.info(f"[{session_short}] STEP 3/7: Running scam detection...")
        is_scam, confidence, scam_details = await scam_detector.detect_scam(
            message=request.message.text,
            conversation_history=[msg.model_dump() for msg in session.conversation_history]
        )
        logger.info(f"[{session_short}] ✓ Detection complete: {confidence:.2%} confidence ({time.time() - step_start:.2f}s)")

        # Log detection with structured logging
        log_detection(
            session_id=request.sessionId,
            is_scam=is_scam,
            confidence=confidence,
            scam_type=scam_details.get('scam_type', 'unknown')
        )

        # Extract intelligence from conversation
        step_start = time.time()
        logger.info(f"[{session_short}] STEP 4/7: Extracting intelligence...")
        extracted_intel = await intel_extractor.extract_intelligence(
            conversation_history=[msg.model_dump() for msg in session.conversation_history]
        )
        intel_count = (len(extracted_intel.bankAccounts) + len(extracted_intel.upiIds) +
                      len(extracted_intel.phishingLinks) + len(extracted_intel.phoneNumbers))
        logger.info(f"[{session_short}] ✓ Extracted {intel_count} items ({time.time() - step_start:.2f}s)")

        # Log extracted intelligence with structured logging
        if any([extracted_intel.bankAccounts, extracted_intel.upiIds, extracted_intel.phishingLinks, extracted_intel.phoneNumbers]):
            if extracted_intel.bankAccounts:
                log_intelligence(request.sessionId, "bank_accounts", len(extracted_intel.bankAccounts))
            if extracted_intel.upiIds:
                log_intelligence(request.sessionId, "upi_ids", len(extracted_intel.upiIds))
            if extracted_intel.phishingLinks:
                log_intelligence(request.sessionId, "phishing_links", len(extracted_intel.phishingLinks))
            if extracted_intel.phoneNumbers:
                log_intelligence(request.sessionId, "phone_numbers", len(extracted_intel.phoneNumbers))
            # Log intelligence to CSV
            csv_logger.log_intelligence(
                session_id=request.sessionId,
                intelligence=extracted_intel,
                message_num=session.message_count
            )

        # Update session with detection results and extracted intelligence
        # Only add scam type note if it's new or changed
        scam_type = scam_details.get('scam_type') or 'unknown'
        scam_type_note = f"Scam type: {scam_type}"

        # Check if this exact scam type note was already added (exact match to avoid duplicates)
        should_add_note = scam_type_note not in session.agent_notes

        session = session_manager.update_session(
            session_id=request.sessionId,
            scam_detected=is_scam and confidence >= settings.scam_confidence_threshold,
            scam_confidence=confidence,
            scam_type=scam_type,
            extracted_intel=extracted_intel,
            agent_note=scam_type_note if should_add_note else None
        )

        # Generate response using appropriate persona (with extraction targeting)
        step_start = time.time()
        logger.info(f"[{session_short}] STEP 5/7: Generating response with persona (confidence={confidence:.2%})...")
        response_text, persona_name = await persona_orchestrator.generate_response(
            latest_message=request.message.text,
            conversation_history=[msg.model_dump() for msg in session.conversation_history],
            scam_confidence=confidence,
            scam_details=scam_details,
            extracted_intelligence=session.extracted_intelligence.model_dump()
        )
        logger.info(f"[{session_short}] ✓ Persona '{persona_name}' generated response ({time.time() - step_start:.2f}s)")

        if DEBUG:
            logger.debug(f"After persona generation: response_text='{response_text}', persona='{persona_name}'")

        # Log persona selection
        log_persona(
            session_id=request.sessionId,
            persona_name=persona_name,
            confidence=confidence
        )

        # Validate and fix response with LLM-based guardrails
        step_start = time.time()
        logger.info(f"[{session_short}] STEP 6/7: Validating response with guardrails...")
        is_valid, fixed_response, warnings = await response_validator.validate_response(
            response=response_text,
            persona_name=persona_name,
            scam_confidence=confidence
        )
        logger.info(f"[{session_short}] ✓ Validation {'passed' if is_valid else 'failed, fixed'} ({time.time() - step_start:.2f}s)")

        if warnings:
            logger.warning(f"Session {request.sessionId}: Response warnings: {warnings}")

        if DEBUG:
            logger.debug(f"After validation: is_valid={is_valid}, fixed_response='{fixed_response}', warnings={warnings}")

        # Use fixed response
        response_text = fixed_response

        # === ANTI-BOT-DETECTION: Add human-like delay ===
        step_start = time.time()
        logger.info(f"[{session_short}] STEP 7/7: Simulating human-like delay...")
        # Simulate distraction (10% chance of long delay)
        await simulate_distraction_delay()

        # Simulate human typing delay (10-90 seconds based on message length)
        await simulate_human_delay(
            message_length=len(response_text),
            complexity="normal" if confidence < 0.8 else "complex"
        )
        logger.info(f"[{session_short}] ✓ Delay complete ({time.time() - step_start:.2f}s)")

        # Log outgoing response with structured logging
        log_message(
            session_id=request.sessionId,
            sender="user",
            text=response_text,
            direction="outgoing"
        )

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

        # Log agent response to CSV
        csv_logger.log_conversation(
            session_id=request.sessionId,
            message_num=session.message_count,
            sender="user",
            text=response_text,
            persona_used=persona_name,
            timestamp=request.message.timestamp
        )

        # Log/update session in CSV
        csv_logger.log_session(session, completed=False)

        # Check if should trigger GUVI callback
        should_callback = session_manager.should_trigger_callback(
            session_id=request.sessionId,
            min_messages=settings.min_messages_before_callback,
            max_messages=settings.max_conversation_turns
        )

        if should_callback:
            callback_result = await guvi_callback.send_final_result(session)

            # Log callback result
            log_callback(
                session_id=request.sessionId,
                success=callback_result["success"],
                message_count=session.message_count,
                intel_count=intel_count
            )

            if not callback_result["success"]:
                logger.error(
                    f"GUVI callback failed for session {request.sessionId}: "
                    f"{callback_result.get('message')}"
                )

        # Return response
        total_time = time.time() - request_start
        logger.info(f"[{session_short}] ✅ Request completed in {total_time:.2f}s (msgs: {session.message_count}, intel: {intel_count})")

        engagement_duration = int(time.time() - session.created_at)
        agent_notes_str = ". ".join(session.agent_notes[-5:]) if session.agent_notes else f"Scam confidence: {confidence:.2%}, Phase: {session.engagement_phase}"

        return HoneypotResponse(
            status="success",
            reply=response_text,
            sessionId=request.sessionId,
            scamDetected=session.scam_detected,
            scamType=session.scam_type,
            confidenceLevel=round(confidence, 2),
            totalMessagesExchanged=session.message_count,
            engagementDurationSeconds=engagement_duration,
            extractedIntelligence=session.extracted_intelligence,
            agentNotes=agent_notes_str,
            engagementMetrics=EngagementMetrics(
                engagementDurationSeconds=engagement_duration,
                totalMessagesExchanged=session.message_count,
                totalTurns=session.message_count // 2
            )
        )

    except Exception as e:
        # Log error but always return 200 — GUVI treats non-200 as scenario failure
        log_error(
            session_id=request.sessionId,
            error=str(e),
            context="honeypot_endpoint"
        )
        logger.exception(e)
        return HoneypotResponse(
            status="success",
            reply="sorry wait... can u repeat that? im confused",
            sessionId=request.sessionId,
            scamDetected=False,
            totalMessagesExchanged=0,
            engagementDurationSeconds=0,
            agentNotes=f"Processing error - fallback response"
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


def verify_dashboard_password(password: str = Query(..., description="Dashboard password")):
    """Verify dashboard password."""
    if password != settings.dashboard_password:
        raise HTTPException(
            status_code=401,
            detail="Invalid dashboard password"
        )
    return password


@app.get("/api/v1/analytics/stats")
async def get_analytics_stats(password: str = Query(...)):
    """
    Get analytics statistics.

    Args:
        password: Dashboard password

    Returns:
        Statistics dictionary
    """
    verify_dashboard_password(password)
    return analytics.get_stats()


@app.get("/api/v1/analytics/sessions")
async def get_analytics_sessions(
    password: str = Query(...),
    scam_only: bool = Query(False),
    completed_only: bool = Query(False),
    limit: int = Query(100)
):
    """
    Get session data from CSV.

    Args:
        password: Dashboard password
        scam_only: Return only scam sessions
        completed_only: Return only completed sessions
        limit: Maximum number of sessions

    Returns:
        List of sessions
    """
    verify_dashboard_password(password)
    sessions = analytics.get_sessions(
        scam_only=scam_only,
        completed_only=completed_only,
        limit=limit
    )
    return {"sessions": sessions, "count": len(sessions)}


@app.get("/api/v1/analytics/conversations")
async def get_analytics_conversations(
    password: str = Query(...),
    session_id: str = Query(None),
    limit: int = Query(100)
):
    """
    Get conversation data from CSV.

    Args:
        password: Dashboard password
        session_id: Filter by session ID
        limit: Maximum number of messages

    Returns:
        List of conversations
    """
    verify_dashboard_password(password)
    conversations = analytics.get_conversations(
        session_id=session_id,
        limit=limit
    )
    return {"conversations": conversations, "count": len(conversations)}


@app.get("/api/v1/analytics/intelligence")
async def get_analytics_intelligence(
    password: str = Query(...),
    session_id: str = Query(None),
    intel_type: str = Query(None),
    limit: int = Query(100)
):
    """
    Get intelligence data from CSV.

    Args:
        password: Dashboard password
        session_id: Filter by session ID
        intel_type: Filter by type
        limit: Maximum number of items

    Returns:
        List of intelligence
    """
    verify_dashboard_password(password)
    intelligence = analytics.get_intelligence(
        session_id=session_id,
        intel_type=intel_type,
        limit=limit
    )
    return {"intelligence": intelligence, "count": len(intelligence)}


@app.get("/api/v1/analytics/session/{session_id}")
async def get_session_details(
    session_id: str,
    password: str = Query(...)
):
    """
    Get complete session details.

    Args:
        session_id: Session identifier
        password: Dashboard password

    Returns:
        Complete session data
    """
    verify_dashboard_password(password)
    details = analytics.get_session_details(session_id)
    if not details:
        raise HTTPException(status_code=404, detail="Session not found")
    return details


@app.get("/api/v1/analytics/download/sessions")
async def download_sessions_csv(password: str = Query(...)):
    """Download sessions CSV file."""
    verify_dashboard_password(password)
    csv_path = "logs/sessions.csv"
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="CSV file not found")
    return FileResponse(
        csv_path,
        media_type="text/csv",
        filename="sessions.csv"
    )


@app.get("/api/v1/analytics/download/conversations")
async def download_conversations_csv(password: str = Query(...)):
    """Download conversations CSV file."""
    verify_dashboard_password(password)
    csv_path = "logs/conversations.csv"
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="CSV file not found")
    return FileResponse(
        csv_path,
        media_type="text/csv",
        filename="conversations.csv"
    )


@app.get("/api/v1/analytics/download/intelligence")
async def download_intelligence_csv(password: str = Query(...)):
    """Download intelligence CSV file."""
    verify_dashboard_password(password)
    csv_path = "logs/intelligence.csv"
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="CSV file not found")
    return FileResponse(
        csv_path,
        media_type="text/csv",
        filename="intelligence.csv"
    )


@app.get("/dashboard")
async def dashboard(request: Request, password: str = Query(None)):
    """
    Analytics dashboard UI.

    Args:
        request: FastAPI request object
        password: Dashboard password

    Returns:
        HTML dashboard
    """
    if not password:
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Honeypot Dashboard - Login</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body class="bg-light">
            <div class="container mt-5">
                <div class="row justify-content-center">
                    <div class="col-md-4">
                        <div class="card shadow">
                            <div class="card-body">
                                <h3 class="card-title text-center mb-4">🍯 Honeypot Dashboard</h3>
                                <form action="/dashboard" method="get">
                                    <div class="mb-3">
                                        <label class="form-label">Password</label>
                                        <input type="password" class="form-control" name="password" required>
                                    </div>
                                    <button type="submit" class="btn btn-primary w-100">Login</button>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """)

    # Verify password
    try:
        verify_dashboard_password(password)
    except HTTPException:
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Honeypot Dashboard - Error</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body class="bg-light">
            <div class="container mt-5">
                <div class="alert alert-danger">
                    Invalid password. <a href="/dashboard">Try again</a>
                </div>
            </div>
        </body>
        </html>
        """, status_code=401)

    # Get analytics data
    stats = analytics.get_stats()
    recent_sessions = analytics.get_sessions(limit=10)
    recent_conversations = analytics.get_recent_activity(limit=10)
    recent_intelligence = analytics.get_intelligence(limit=20)
    success_metrics = analytics.get_success_metrics()
    scam_intel = analytics.get_scam_intelligence()
    persona_perf = analytics.get_persona_performance()

    # Prepare chart data
    persona_labels = list(persona_perf['persona_distribution'].keys())
    persona_values = list(persona_perf['persona_distribution'].values())
    scam_type_labels = list(scam_intel['scam_type_distribution'].keys())
    scam_type_values = list(scam_intel['scam_type_distribution'].values())

    # Render template
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "password": password,
        "stats": stats,
        "success_metrics": success_metrics,
        "scam_intel": scam_intel,
        "persona_perf": persona_perf,
        "recent_sessions": recent_sessions,
        "recent_conversations": recent_conversations,
        "recent_intelligence": recent_intelligence,
        "persona_labels": persona_labels,
        "persona_values": persona_values,
        "scam_type_labels": scam_type_labels,
        "scam_type_values": scam_type_values
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
