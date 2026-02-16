"""Analytics module for reading and analyzing CSV data."""

import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class Analytics:
    """Analytics reader for CSV data."""

    def __init__(self, logs_dir: str = "logs"):
        """Initialize analytics.

        Args:
            logs_dir: Directory containing CSV files
        """
        self.logs_dir = Path(logs_dir)
        self.sessions_file = self.logs_dir / "sessions.csv"
        self.conversations_file = self.logs_dir / "conversations.csv"
        self.intelligence_file = self.logs_dir / "intelligence.csv"

    def get_sessions(
        self,
        scam_only: bool = False,
        completed_only: bool = False,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get session data.

        Args:
            scam_only: Return only scam sessions
            completed_only: Return only completed sessions
            limit: Maximum number of sessions to return

        Returns:
            List of session dictionaries
        """
        if not self.sessions_file.exists():
            return []

        sessions = []
        with open(self.sessions_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Apply filters
                if scam_only and row['scam_detected'] != 'True':
                    continue
                if completed_only and not row['completed_at']:
                    continue

                sessions.append(row)

        # Sort by last_updated (most recent first)
        sessions.sort(key=lambda x: x.get('last_updated', ''), reverse=True)

        # Apply limit
        if limit:
            sessions = sessions[:limit]

        return sessions

    def get_conversations(
        self,
        session_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get conversation data.

        Args:
            session_id: Filter by specific session
            limit: Maximum number of messages to return

        Returns:
            List of conversation message dictionaries
        """
        if not self.conversations_file.exists():
            return []

        conversations = []
        with open(self.conversations_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Apply session filter
                if session_id and row['session_id'] != session_id:
                    continue

                conversations.append(row)

        # Sort by logged_at (most recent first) if no session filter
        if not session_id:
            conversations.sort(key=lambda x: x.get('logged_at', ''), reverse=True)

        # Apply limit
        if limit:
            conversations = conversations[:limit]

        return conversations

    def get_intelligence(
        self,
        session_id: Optional[str] = None,
        intel_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get intelligence data.

        Args:
            session_id: Filter by specific session
            intel_type: Filter by intelligence type
            limit: Maximum number of intelligence items to return

        Returns:
            List of intelligence dictionaries
        """
        if not self.intelligence_file.exists():
            return []

        intelligence = []
        with open(self.intelligence_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Apply filters
                if session_id and row['session_id'] != session_id:
                    continue
                if intel_type and row['type'] != intel_type:
                    continue

                intelligence.append(row)

        # Sort by extracted_at (most recent first)
        intelligence.sort(key=lambda x: x.get('extracted_at', ''), reverse=True)

        # Apply limit
        if limit:
            intelligence = intelligence[:limit]

        return intelligence

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics.

        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_sessions': 0,
            'scam_sessions': 0,
            'total_messages': 0,
            'total_intelligence': 0,
            'active_sessions': 0,
            'completed_sessions': 0,
            'intelligence_by_type': {
                'bank_account': 0,
                'upi_id': 0,
                'phishing_link': 0,
                'phone_number': 0
            },
            'scam_types': {}
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
                    stats['total_messages'] += int(row['message_count']) if row['message_count'] else 0

                    # Count scam types
                    scam_type = row.get('scam_type', 'unknown')
                    stats['scam_types'][scam_type] = stats['scam_types'].get(scam_type, 0) + 1

        # Count intelligence by type
        if self.intelligence_file.exists():
            with open(self.intelligence_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stats['total_intelligence'] += 1
                    intel_type = row['type']
                    if intel_type in stats['intelligence_by_type']:
                        stats['intelligence_by_type'][intel_type] += 1

        return stats

    def search_sessions(self, query: str) -> List[Dict[str, Any]]:
        """Search sessions by session_id or scam_type.

        Args:
            query: Search query

        Returns:
            List of matching session dictionaries
        """
        sessions = self.get_sessions()
        query_lower = query.lower()

        return [
            s for s in sessions
            if query_lower in s.get('session_id', '').lower()
            or query_lower in s.get('scam_type', '').lower()
        ]

    def get_session_details(self, session_id: str) -> Dict[str, Any]:
        """Get complete details for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with session, conversations, and intelligence
        """
        # Get session data
        sessions = self.get_sessions()
        session = next((s for s in sessions if s['session_id'] == session_id), None)

        if not session:
            return {}

        # Get conversations for this session
        conversations = self.get_conversations(session_id=session_id)

        # Get intelligence for this session
        intelligence = self.get_intelligence(session_id=session_id)

        return {
            'session': session,
            'conversations': conversations,
            'intelligence': intelligence
        }

    def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent activity across all sessions.

        Args:
            limit: Number of recent conversations to return

        Returns:
            List of recent conversation dictionaries
        """
        return self.get_conversations(limit=limit)

    def get_success_metrics(self) -> Dict[str, Any]:
        """Get success/effectiveness metrics.

        Returns:
            Dictionary with success metrics
        """
        metrics = {
            'extraction_rate': 0.0,
            'avg_intel_per_session': 0.0,
            'avg_messages_per_session': 0.0,
            'completion_rate': 0.0,
            'sessions_with_intel': 0,
            'scam_detection_rate': 0.0,
            'conversion_funnel': {
                'total_sessions': 0,
                'scam_detected': 0,
                'intel_extracted': 0,
                'completed': 0
            }
        }

        sessions = self.get_sessions()
        if not sessions:
            return metrics

        total_sessions = len(sessions)
        scam_sessions = 0
        sessions_with_intel = 0
        total_messages = 0
        completed_sessions = 0

        # Get all intelligence to map session_id -> intel count
        intel_by_session = {}
        intelligence = self.get_intelligence()
        for intel in intelligence:
            session_id = intel['session_id']
            intel_by_session[session_id] = intel_by_session.get(session_id, 0) + 1

        # Analyze sessions
        for session in sessions:
            if session['scam_detected'] == 'True':
                scam_sessions += 1

            if session['session_id'] in intel_by_session:
                sessions_with_intel += 1

            total_messages += int(session.get('message_count', 0) or 0)

            if session.get('completed_at'):
                completed_sessions += 1

        # Calculate metrics
        metrics['conversion_funnel']['total_sessions'] = total_sessions
        metrics['conversion_funnel']['scam_detected'] = scam_sessions
        metrics['conversion_funnel']['intel_extracted'] = sessions_with_intel
        metrics['conversion_funnel']['completed'] = completed_sessions

        if scam_sessions > 0:
            metrics['extraction_rate'] = round((sessions_with_intel / scam_sessions) * 100, 1)
            metrics['avg_intel_per_session'] = round(len(intelligence) / scam_sessions, 2)

        if total_sessions > 0:
            metrics['avg_messages_per_session'] = round(total_messages / total_sessions, 1)
            metrics['completion_rate'] = round((completed_sessions / total_sessions) * 100, 1)
            metrics['scam_detection_rate'] = round((scam_sessions / total_sessions) * 100, 1)

        metrics['sessions_with_intel'] = sessions_with_intel

        return metrics

    def get_scam_intelligence(self) -> Dict[str, Any]:
        """Get scam intelligence insights.

        Returns:
            Dictionary with scam intelligence data
        """
        intel_data = {
            'scam_type_distribution': {},
            'top_scammers': [],
            'duplicate_entities': {
                'phones': [],
                'upis': [],
                'bank_accounts': []
            },
            'most_extracted': {
                'phone_numbers': [],
                'upi_ids': [],
                'bank_accounts': []
            }
        }

        sessions = self.get_sessions()
        intelligence = self.get_intelligence()

        # Scam type distribution
        for session in sessions:
            scam_type = session.get('scam_type', 'unknown')
            intel_data['scam_type_distribution'][scam_type] = \
                intel_data['scam_type_distribution'].get(scam_type, 0) + 1

        # Track entity occurrences across sessions
        entity_sessions = {
            'phone': {},  # phone -> [session_ids]
            'upi': {},
            'bank': {}
        }

        entity_counts = {
            'phone': {},  # phone -> count
            'upi': {},
            'bank': {}
        }

        for intel in intelligence:
            session_id = intel['session_id']
            value = intel['value']
            intel_type = intel['type']

            if intel_type == 'phone_number':
                entity_sessions['phone'].setdefault(value, []).append(session_id)
                entity_counts['phone'][value] = entity_counts['phone'].get(value, 0) + 1
            elif intel_type == 'upi_id':
                entity_sessions['upi'].setdefault(value, []).append(session_id)
                entity_counts['upi'][value] = entity_counts['upi'].get(value, 0) + 1
            elif intel_type == 'bank_account':
                entity_sessions['bank'].setdefault(value, []).append(session_id)
                entity_counts['bank'][value] = entity_counts['bank'].get(value, 0) + 1

        # Find duplicate entities (appearing in multiple sessions)
        for phone, session_ids in entity_sessions['phone'].items():
            unique_sessions = list(set(session_ids))
            if len(unique_sessions) > 1:
                intel_data['duplicate_entities']['phones'].append({
                    'value': phone,
                    'session_count': len(unique_sessions),
                    'total_appearances': len(session_ids)
                })

        for upi, session_ids in entity_sessions['upi'].items():
            unique_sessions = list(set(session_ids))
            if len(unique_sessions) > 1:
                intel_data['duplicate_entities']['upis'].append({
                    'value': upi,
                    'session_count': len(unique_sessions),
                    'total_appearances': len(session_ids)
                })

        for bank, session_ids in entity_sessions['bank'].items():
            unique_sessions = list(set(session_ids))
            if len(unique_sessions) > 1:
                intel_data['duplicate_entities']['bank_accounts'].append({
                    'value': bank,
                    'session_count': len(unique_sessions),
                    'total_appearances': len(session_ids)
                })

        # Sort duplicates by session count (most suspicious first)
        intel_data['duplicate_entities']['phones'].sort(key=lambda x: x['session_count'], reverse=True)
        intel_data['duplicate_entities']['upis'].sort(key=lambda x: x['session_count'], reverse=True)
        intel_data['duplicate_entities']['bank_accounts'].sort(key=lambda x: x['session_count'], reverse=True)

        # Most extracted entities (top 5 by frequency)
        top_phones = sorted(entity_counts['phone'].items(), key=lambda x: x[1], reverse=True)[:5]
        top_upis = sorted(entity_counts['upi'].items(), key=lambda x: x[1], reverse=True)[:5]
        top_banks = sorted(entity_counts['bank'].items(), key=lambda x: x[1], reverse=True)[:5]

        intel_data['most_extracted']['phone_numbers'] = [
            {'value': phone, 'count': count} for phone, count in top_phones
        ]
        intel_data['most_extracted']['upi_ids'] = [
            {'value': upi, 'count': count} for upi, count in top_upis
        ]
        intel_data['most_extracted']['bank_accounts'] = [
            {'value': bank, 'count': count} for bank, count in top_banks
        ]

        # Top scammers (entities appearing most frequently)
        all_entities = []
        for phone, count in entity_counts['phone'].items():
            all_entities.append({
                'type': 'phone',
                'value': phone,
                'count': count,
                'sessions': len(set(entity_sessions['phone'][phone]))
            })
        for upi, count in entity_counts['upi'].items():
            all_entities.append({
                'type': 'upi',
                'value': upi,
                'count': count,
                'sessions': len(set(entity_sessions['upi'][upi]))
            })

        all_entities.sort(key=lambda x: (x['sessions'], x['count']), reverse=True)
        intel_data['top_scammers'] = all_entities[:10]

        return intel_data

    def get_persona_performance(self) -> Dict[str, Any]:
        """Get persona performance metrics.

        Returns:
            Dictionary with persona performance data
        """
        performance = {
            'personas': {
                'Normal User': {'sessions': 0, 'intel_extracted': 0, 'total_messages': 0, 'success_rate': 0.0},
                'Skeptical User': {'sessions': 0, 'intel_extracted': 0, 'total_messages': 0, 'success_rate': 0.0},
                'Honeypot': {'sessions': 0, 'intel_extracted': 0, 'total_messages': 0, 'success_rate': 0.0}
            },
            'persona_distribution': {},
            'effectiveness_scores': {}
        }

        # Get all conversations to track persona usage
        conversations = self.get_conversations()
        intelligence = self.get_intelligence()

        # Build session -> intel count map
        intel_by_session = {}
        for intel in intelligence:
            session_id = intel['session_id']
            intel_by_session[session_id] = intel_by_session.get(session_id, 0) + 1

        # Track persona usage per session
        session_personas = {}  # session_id -> {persona: message_count}
        for conv in conversations:
            session_id = conv['session_id']
            persona = conv.get('persona_used', '')

            if not persona:
                continue

            if session_id not in session_personas:
                session_personas[session_id] = {}

            session_personas[session_id][persona] = \
                session_personas[session_id].get(persona, 0) + 1

        # Calculate metrics per persona
        for session_id, personas in session_personas.items():
            # Determine dominant persona for this session
            dominant_persona = max(personas.items(), key=lambda x: x[1])[0] if personas else None

            if dominant_persona and dominant_persona in performance['personas']:
                performance['personas'][dominant_persona]['sessions'] += 1
                performance['personas'][dominant_persona]['total_messages'] += sum(personas.values())

                # Check if this session extracted intel
                if session_id in intel_by_session:
                    performance['personas'][dominant_persona]['intel_extracted'] += intel_by_session[session_id]

        # Calculate success rates and effectiveness scores
        for persona, data in performance['personas'].items():
            if data['sessions'] > 0:
                sessions_with_intel = sum(1 for sid, personas in session_personas.items()
                                         if max(personas.items(), key=lambda x: x[1])[0] == persona
                                         and sid in intel_by_session)
                data['success_rate'] = round((sessions_with_intel / data['sessions']) * 100, 1)

                # Effectiveness = intel per message
                if data['total_messages'] > 0:
                    effectiveness = data['intel_extracted'] / data['total_messages']
                    performance['effectiveness_scores'][persona] = round(effectiveness, 3)
                else:
                    performance['effectiveness_scores'][persona] = 0.0

            performance['persona_distribution'][persona] = data['sessions']

        return performance


# Global analytics instance
analytics = Analytics()
