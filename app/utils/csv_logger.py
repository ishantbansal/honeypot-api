"""CSV logging system for honeypot analytics."""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import threading
from app.models.schemas import SessionState, ExtractedIntelligence


class CSVLogger:
    """Thread-safe CSV logger for honeypot data."""

    def __init__(self, logs_dir: str = "logs"):
        """Initialize CSV logger.

        Args:
            logs_dir: Directory to store CSV files
        """
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)

        # Define CSV file paths
        self.sessions_file = self.logs_dir / "sessions.csv"
        self.conversations_file = self.logs_dir / "conversations.csv"
        self.intelligence_file = self.logs_dir / "intelligence.csv"

        # Thread locks for safe concurrent writes
        self._sessions_lock = threading.Lock()
        self._conversations_lock = threading.Lock()
        self._intelligence_lock = threading.Lock()

        # Initialize CSV files with headers
        self._init_csv_files()

    def _init_csv_files(self):
        """Initialize CSV files with headers if they don't exist."""
        # Sessions CSV
        if not self.sessions_file.exists():
            with open(self.sessions_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'session_id', 'scam_detected', 'scam_confidence', 'scam_type',
                    'message_count', 'engagement_phase', 'personas_used',
                    'intelligence_count', 'created_at', 'last_updated', 'completed_at'
                ])

        # Conversations CSV
        if not self.conversations_file.exists():
            with open(self.conversations_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'session_id', 'message_num', 'sender', 'text',
                    'persona_used', 'timestamp', 'logged_at'
                ])

        # Intelligence CSV
        if not self.intelligence_file.exists():
            with open(self.intelligence_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'session_id', 'type', 'value', 'extracted_at', 'message_num'
                ])

    def log_session(self, session: SessionState, completed: bool = False):
        """Log session information.

        Args:
            session: Session state object
            completed: Whether session is completed
        """
        with self._sessions_lock:
            # Read existing data
            existing_sessions = {}
            if self.sessions_file.exists():
                with open(self.sessions_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        existing_sessions[row['session_id']] = row

            # Prepare session data
            now = datetime.now().isoformat()
            personas_used = ','.join(session.personas_used) if session.personas_used else ''

            # Count total intelligence
            intel = session.extracted_intelligence
            intelligence_count = (
                len(intel.bankAccounts) + len(intel.upiIds) +
                len(intel.phishingLinks) + len(intel.phoneNumbers)
            )

            # Get scam type from agent notes
            scam_type = 'unknown'
            for note in session.agent_notes:
                if 'Scam type:' in note:
                    scam_type = note.split('Scam type:')[1].strip()
                    break

            session_data = {
                'session_id': session.session_id,
                'scam_detected': str(session.scam_detected),
                'scam_confidence': f"{session.scam_confidence:.4f}",
                'scam_type': scam_type,
                'message_count': str(session.message_count),
                'engagement_phase': session.engagement_phase,
                'personas_used': personas_used,
                'intelligence_count': str(intelligence_count),
                'created_at': existing_sessions.get(session.session_id, {}).get('created_at', now),
                'last_updated': now,
                'completed_at': now if completed else existing_sessions.get(session.session_id, {}).get('completed_at', '')
            }

            # Update existing sessions dict
            existing_sessions[session.session_id] = session_data

            # Write all sessions back
            with open(self.sessions_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'session_id', 'scam_detected', 'scam_confidence', 'scam_type',
                    'message_count', 'engagement_phase', 'personas_used',
                    'intelligence_count', 'created_at', 'last_updated', 'completed_at'
                ])
                writer.writeheader()
                for session_data in existing_sessions.values():
                    writer.writerow(session_data)

    def log_conversation(
        self,
        session_id: str,
        message_num: int,
        sender: str,
        text: str,
        persona_used: Optional[str] = None,
        timestamp: Optional[int] = None
    ):
        """Log a conversation message.

        Args:
            session_id: Session identifier
            message_num: Message number in conversation
            sender: Message sender (scammer/user)
            text: Message text
            persona_used: Persona used for response (if user message)
            timestamp: Original message timestamp
        """
        with self._conversations_lock:
            with open(self.conversations_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    session_id,
                    message_num,
                    sender,
                    text.replace('\n', ' ').replace('\r', ''),  # Clean newlines
                    persona_used or '',
                    timestamp or '',
                    datetime.now().isoformat()
                ])

    def log_intelligence(
        self,
        session_id: str,
        intelligence: ExtractedIntelligence,
        message_num: int
    ):
        """Log extracted intelligence.

        Args:
            session_id: Session identifier
            intelligence: Extracted intelligence object
            message_num: Message number when intelligence was extracted
        """
        with self._intelligence_lock:
            now = datetime.now().isoformat()

            # Read existing intelligence to avoid duplicates
            existing_intel = set()
            if self.intelligence_file.exists():
                with open(self.intelligence_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['session_id'] == session_id:
                            existing_intel.add((row['type'], row['value']))

            # Prepare new intelligence entries
            new_entries = []

            for bank_account in intelligence.bankAccounts:
                if ('bank_account', bank_account) not in existing_intel:
                    new_entries.append(('bank_account', bank_account))

            for upi_id in intelligence.upiIds:
                if ('upi_id', upi_id) not in existing_intel:
                    new_entries.append(('upi_id', upi_id))

            for link in intelligence.phishingLinks:
                if ('phishing_link', link) not in existing_intel:
                    new_entries.append(('phishing_link', link))

            for phone in intelligence.phoneNumbers:
                if ('phone_number', phone) not in existing_intel:
                    new_entries.append(('phone_number', phone))

            # Write new intelligence entries
            if new_entries:
                with open(self.intelligence_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    for intel_type, value in new_entries:
                        writer.writerow([
                            session_id,
                            intel_type,
                            value,
                            now,
                            message_num
                        ])

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics from CSV files.

        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_sessions': 0,
            'scam_sessions': 0,
            'total_messages': 0,
            'total_intelligence': 0,
            'active_sessions': 0,
            'completed_sessions': 0
        }

        # Count sessions
        if self.sessions_file.exists():
            with open(self.sessions_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stats['total_sessions'] += 1
                    if row['scam_detected'] == 'True':
                        stats['scam_sessions'] += 1
                    if row['completed_at']:
                        stats['completed_sessions'] += 1
                    else:
                        stats['active_sessions'] += 1
                    stats['total_messages'] += int(row['message_count'])
                    stats['total_intelligence'] += int(row['intelligence_count'])

        return stats


# Global CSV logger instance
csv_logger = CSVLogger()
