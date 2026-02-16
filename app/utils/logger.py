"""Enhanced logging configuration using Loguru."""

import sys
from pathlib import Path
from loguru import logger
import os


def setup_logging(log_dir: str = "logs", debug: bool = False):
    """
    Setup enhanced logging with Loguru.

    Args:
        log_dir: Directory to store log files
        debug: Enable debug mode
    """
    # Remove default handler
    logger.remove()

    # Create logs directory
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Console handler with colors
    log_level = "DEBUG" if debug else "INFO"
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True
    )

    # File handler - General logs with rotation
    logger.add(
        log_path / "honeypot_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # Rotate at midnight
        retention="7 days",  # Keep logs for 7 days
        compression="zip",  # Compress old logs
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="INFO"
    )

    # File handler - Error logs
    logger.add(
        log_path / "errors_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",  # Keep error logs longer
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR"
    )

    # File handler - JSON structured logs (for parsing)
    logger.add(
        log_path / "honeypot_structured_{time:YYYY-MM-DD}.json",
        rotation="00:00",
        retention="7 days",
        compression="zip",
        serialize=True,  # JSON format
        level="INFO"
    )

    logger.info("🚀 Enhanced logging initialized")
    logger.info(f"📁 Log directory: {log_path.absolute()}")
    logger.info(f"🔍 Log level: {log_level}")

    return logger


# Create configured logger instance
log_dir = "logs"
debug_mode = os.getenv("DEBUG", "false").lower() == "true"
logger = setup_logging(log_dir=log_dir, debug=debug_mode)


# Convenience functions for structured logging
def log_message(session_id: str, sender: str, text: str, direction: str = "incoming"):
    """Log a conversation message with structured data."""
    icon = "📨" if direction == "incoming" else "📤"
    logger.bind(
        session_id=session_id,
        sender=sender,
        direction=direction
    ).info(f"{icon} [{session_id[:12]}] {sender}: {text[:100]}")


def log_detection(session_id: str, is_scam: bool, confidence: float, scam_type: str):
    """Log scam detection result."""
    icon = "🚨" if is_scam else "✅"
    logger.bind(
        session_id=session_id,
        is_scam=is_scam,
        confidence=confidence,
        scam_type=scam_type
    ).info(f"{icon} [{session_id[:12]}] Scam={is_scam}, Confidence={confidence:.2f}, Type={scam_type}")


def log_intelligence(session_id: str, intel_type: str, count: int):
    """Log intelligence extraction."""
    logger.bind(
        session_id=session_id,
        intel_type=intel_type,
        count=count
    ).info(f"🔍 [{session_id[:12]}] Extracted {count} {intel_type}")


def log_callback(session_id: str, success: bool, message_count: int, intel_count: int):
    """Log GUVI callback."""
    icon = "✅" if success else "❌"
    logger.bind(
        session_id=session_id,
        success=success,
        message_count=message_count,
        intel_count=intel_count
    ).info(f"{icon} [{session_id[:12]}] GUVI callback: success={success}, messages={message_count}, intel={intel_count}")


def log_persona(session_id: str, persona_name: str, confidence: float):
    """Log persona selection."""
    logger.bind(
        session_id=session_id,
        persona=persona_name,
        confidence=confidence
    ).info(f"🎭 [{session_id[:12]}] Using persona: {persona_name} (confidence={confidence:.2f})")


def log_error(session_id: str, error: str, context: str = ""):
    """Log an error with context."""
    logger.bind(
        session_id=session_id,
        context=context
    ).error(f"❌ [{session_id[:12]}] {context}: {error}")
