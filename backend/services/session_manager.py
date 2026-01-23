"""
Session Manager - Manages conversation session state
In-memory store for POC, can be upgraded to Redis for production
"""
from typing import Optional, Dict
from datetime import datetime, timedelta
import logging

from models.session import SessionState, ConversationPhase

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages conversation session state.
    Uses in-memory store for POC; can be swapped for Redis in production.
    """

    def __init__(self, ttl_minutes: int = 60):
        self._sessions: Dict[str, SessionState] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        logger.info(f"SessionManager initialized with TTL: {ttl_minutes} minutes")

    async def create_session(
        self,
        min_signals: int = 4,
        min_turns: int = 3,
        max_turns: int = 6
    ) -> SessionState:
        """Create new session with initial state"""
        session = SessionState(
            min_signals_threshold=min_signals,
            min_clarification_turns=min_turns,
            max_clarification_turns=max_turns
        )
        self._sessions[session.session_id] = session
        logger.info(f"Created session: {session.session_id} (min_turns={min_turns}, max_turns={max_turns})")
        return session

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        """Retrieve session by ID, return None if expired or not found"""
        session = self._sessions.get(session_id)
        if session:
            # Check expiration
            if datetime.utcnow() - session.last_activity > self._ttl:
                logger.info(f"Session expired: {session_id}")
                await self.delete_session(session_id)
                return None
            # Update last activity
            session.last_activity = datetime.utcnow()
        return session

    async def update_session(self, session: SessionState) -> None:
        """Update session state"""
        session.last_activity = datetime.utcnow()
        self._sessions[session.session_id] = session
        logger.debug(f"Updated session: {session.session_id}, phase: {session.phase.value}")

    async def delete_session(self, session_id: str) -> None:
        """Remove session"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Deleted session: {session_id}")

    async def transition_phase(
        self,
        session: SessionState,
        new_phase: ConversationPhase
    ) -> SessionState:
        """Transition session to new phase"""
        old_phase = session.phase
        session.phase = new_phase
        logger.info(f"Session {session.session_id}: {old_phase.value} -> {new_phase.value}")
        await self.update_session(session)
        return session

    async def cleanup_expired(self) -> int:
        """Remove all expired sessions, return count removed"""
        now = datetime.utcnow()
        expired = [
            sid for sid, session in self._sessions.items()
            if now - session.last_activity > self._ttl
        ]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
        return len(expired)

    def get_active_session_count(self) -> int:
        """Return count of active sessions"""
        return len(self._sessions)


# Singleton instance
_session_manager: Optional[SessionManager] = None


def get_session_manager(ttl_minutes: int = 60) -> SessionManager:
    """Get or create the singleton SessionManager instance"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(ttl_minutes=ttl_minutes)
    return _session_manager
