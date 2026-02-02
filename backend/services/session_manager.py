from typing import Optional, Dict
from datetime import datetime, timedelta
import logging

from models.session import SessionState, ConversationPhase
from config import settings

logger = logging.getLogger(__name__)


class SessionManager:
    """Base class/interface for Session Managers"""
    async def create_session(self, **kwargs) -> SessionState: pass
    async def get_session(self, session_id: str) -> Optional[SessionState]: pass
    async def update_session(self, session: SessionState) -> None: pass
    async def delete_session(self, session_id: str) -> None: pass
    async def transition_phase(self, session: SessionState, new_phase: ConversationPhase) -> SessionState: pass


class InMemorySessionManager(SessionManager):
    """
    In-memory session storage (default for local dev).
    """
    def __init__(self, ttl_minutes: int = 60):
        self._sessions: Dict[str, SessionState] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        logger.info(f"InMemorySessionManager initialized (TTL: {ttl_minutes}m)")

    async def create_session(self, min_signals=4, min_turns=3, max_turns=6) -> SessionState:
        session = SessionState(
            min_signals_threshold=min_signals,
            min_clarification_turns=min_turns,
            max_clarification_turns=max_turns
        )
        self._sessions[session.session_id] = session
        return session

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        session = self._sessions.get(session_id)
        if session:
            if datetime.utcnow() - session.last_activity > self._ttl:
                del self._sessions[session_id]
                return None
            session.last_activity = datetime.utcnow()
        return session

    async def update_session(self, session: SessionState) -> None:
        session.last_activity = datetime.utcnow()
        self._sessions[session.session_id] = session

    async def delete_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]

    async def transition_phase(self, session: SessionState, new_phase: ConversationPhase) -> SessionState:
        session.phase = new_phase
        await self.update_session(session)
        return session


class MongoSessionManager(SessionManager):
    """
    MongoDB-backed session storage for multi-instance production environments.
    """
    def __init__(self, ttl_minutes: int = 60):
        from services.auth_service import get_mongo_client
        self.db = get_mongo_client()
        self.collection = self.db.sessions
        self._ttl = timedelta(minutes=ttl_minutes)
        
        # Ensure index for automatic expiration
        self.collection.create_index("last_activity", expireAfterSeconds=ttl_minutes * 60)
        self.collection.create_index("session_id", unique=True)
        
        logger.info(f"MongoSessionManager initialized (TTL: {ttl_minutes}m)")

    async def create_session(self, min_signals=4, min_turns=3, max_turns=6) -> SessionState:
        session = SessionState(
            min_signals_threshold=min_signals,
            min_clarification_turns=min_turns,
            max_clarification_turns=max_turns
        )
        # Store initial state
        await self.update_session(session)
        logger.info(f"💾 Created and saved new session to MongoDB: {session.session_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        logger.debug(f"🔍 Querying MongoDB for session {session_id}")
        doc = self.collection.find_one({"session_id": session_id})
        if not doc:
            logger.debug(f"❌ Session {session_id} not found in MongoDB")
            return None
        
        try:
            session = SessionState.from_dict(doc)
            logger.debug(f"✅ Retrieved session {session_id} from MongoDB, turn_count={session.turn_count}")
            return session
        except Exception as e:
            logger.error(f"❌ Error deserializing session {session_id}: {e}")
            return None

    async def update_session(self, session: SessionState) -> None:
        session.last_activity = datetime.utcnow()
        data = session.to_dict()
        
        # Use upsert to save session state
        result = self.collection.update_one(
            {"session_id": session.session_id},
            {"$set": data},
            upsert=True
        )
        logger.debug(f"💾 Saved session {session.session_id} to MongoDB (turn_count={session.turn_count}, matched={result.matched_count}, upserted={result.upserted_id is not None})")

    async def delete_session(self, session_id: str) -> None:
        self.collection.delete_one({"session_id": session_id})

    async def transition_phase(self, session: SessionState, new_phase: ConversationPhase) -> SessionState:
        session.phase = new_phase
        await self.update_session(session)
        return session


# Singleton instance
_session_manager: Optional[SessionManager] = None


def get_session_manager(ttl_minutes: int = 60) -> SessionManager:
    """
    Get the appropriate SessionManager instance.
    Prefers MongoDB if configured, otherwise falls back to memory.
    """
    global _session_manager
    if _session_manager is None:
        # Check if MongoDB is configured in settings
        if settings.MONGODB_URI and settings.DATABASE_NAME:
            try:
                _session_manager = MongoSessionManager(ttl_minutes=ttl_minutes)
                logger.info("Using MongoDB for persistent session storage")
            except Exception as e:
                logger.error(f"Failed to initialize MongoSessionManager: {e}. Falling back to In-Memory.")
                _session_manager = InMemorySessionManager(ttl_minutes=ttl_minutes)
        else:
            logger.info("No MongoDB config found. Using In-Memory session storage.")
            _session_manager = InMemorySessionManager(ttl_minutes=ttl_minutes)
            
    return _session_manager
