"""
Authentication Service - Simple file-based user management
For production, use a proper database like PostgreSQL or MongoDB
"""
import json
import hashlib
import secrets
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Storage paths
DATA_DIR = Path("./data")
USERS_FILE = DATA_DIR / "users.json"
TOKENS_FILE = DATA_DIR / "tokens.json"
CONVERSATIONS_DIR = DATA_DIR / "conversations"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)


def _hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """Hash password with salt"""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return hashed, salt


def _verify_password(password: str, hashed: str, salt: str) -> bool:
    """Verify password against hash"""
    check_hash, _ = _hash_password(password, salt)
    return check_hash == hashed


def _load_users() -> Dict[str, Any]:
    """Load users from file"""
    if USERS_FILE.exists():
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}


def _save_users(users: Dict[str, Any]) -> None:
    """Save users to file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)


def _load_tokens() -> Dict[str, Any]:
    """Load tokens from file"""
    if TOKENS_FILE.exists():
        with open(TOKENS_FILE, 'r') as f:
            return json.load(f)
    return {}


def _save_tokens(tokens: Dict[str, Any]) -> None:
    """Save tokens to file"""
    with open(TOKENS_FILE, 'w') as f:
        json.dump(tokens, f, indent=2)


def _generate_token() -> str:
    """Generate a secure token"""
    return secrets.token_urlsafe(32)


def _generate_user_id() -> str:
    """Generate a unique user ID"""
    return secrets.token_hex(12)


def _calculate_age_and_group(dob: str) -> tuple[int, str]:
    """Calculate age and age group from date of birth (YYYY-MM-DD format)"""
    try:
        birth_date = datetime.strptime(dob, "%Y-%m-%d")
        today = datetime.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

        # Determine age group
        if age < 20:
            age_group = "teen"
        elif age < 35:
            age_group = "young_adult"
        elif age < 55:
            age_group = "middle_aged"
        else:
            age_group = "senior"

        return age, age_group
    except (ValueError, TypeError):
        return 0, "unknown"


class AuthService:
    """Simple authentication service"""

    def register_user(
        self,
        name: str,
        email: str,
        password: str,
        phone: str = "",
        gender: str = "",
        dob: str = "",
        profession: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Register a new user with extended profile"""
        users = _load_users()

        # Check if email already exists
        email_lower = email.lower()
        if email_lower in users:
            return None

        # Hash password
        hashed, salt = _hash_password(password)

        # Calculate age and age group from DOB
        age, age_group = _calculate_age_and_group(dob)

        # Create user
        user_id = _generate_user_id()
        user = {
            "id": user_id,
            "name": name,
            "email": email_lower,
            "phone": phone,
            "gender": gender,
            "dob": dob,
            "age": age,
            "age_group": age_group,
            "profession": profession,
            "password_hash": hashed,
            "password_salt": salt,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Save user
        users[email_lower] = user
        _save_users(users)

        # Generate token
        token = self._create_token(user_id)

        logger.info(f"New user registered: {email_lower}")

        return {
            "user": {
                "id": user_id,
                "name": name,
                "email": email_lower,
                "phone": phone,
                "gender": gender,
                "dob": dob,
                "age": age,
                "age_group": age_group,
                "profession": profession,
                "created_at": user["created_at"],
            },
            "token": token,
        }

    def login_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Login an existing user"""
        users = _load_users()
        email_lower = email.lower()

        if email_lower not in users:
            return None

        user = users[email_lower]

        # Verify password
        if not _verify_password(password, user["password_hash"], user["password_salt"]):
            return None

        # Generate token
        token = self._create_token(user["id"])

        logger.info(f"User logged in: {email_lower}")

        # Recalculate age in case it's been a while since registration
        age, age_group = _calculate_age_and_group(user.get("dob", ""))

        return {
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "phone": user.get("phone", ""),
                "gender": user.get("gender", ""),
                "dob": user.get("dob", ""),
                "age": age,
                "age_group": age_group,
                "profession": user.get("profession", ""),
                "created_at": user["created_at"],
            },
            "token": token,
        }

    def _create_token(self, user_id: str) -> str:
        """Create and store a new token for user"""
        tokens = _load_tokens()
        token = _generate_token()

        tokens[token] = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        }

        _save_tokens(tokens)
        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify token and return user info"""
        tokens = _load_tokens()

        if token not in tokens:
            return None

        token_data = tokens[token]

        # Check expiration
        expires_at = datetime.fromisoformat(token_data["expires_at"])
        if datetime.utcnow() > expires_at:
            # Token expired, remove it
            del tokens[token]
            _save_tokens(tokens)
            return None

        # Get user
        users = _load_users()
        user_id = token_data["user_id"]

        for user in users.values():
            if user["id"] == user_id:
                # Recalculate age in case it's been a while
                age, age_group = _calculate_age_and_group(user.get("dob", ""))
                return {
                    "id": user["id"],
                    "name": user["name"],
                    "email": user["email"],
                    "phone": user.get("phone", ""),
                    "gender": user.get("gender", ""),
                    "dob": user.get("dob", ""),
                    "age": age,
                    "age_group": age_group,
                    "profession": user.get("profession", ""),
                    "created_at": user["created_at"],
                }

        return None

    def logout_user(self, token: str) -> bool:
        """Logout user by invalidating token"""
        tokens = _load_tokens()

        if token in tokens:
            del tokens[token]
            _save_tokens(tokens)
            return True

        return False


class ConversationStorage:
    """Store and retrieve user conversations"""

    def _get_user_conversations_file(self, user_id: str) -> Path:
        """Get the path to user's conversations file"""
        return CONVERSATIONS_DIR / f"{user_id}.json"

    def _load_user_conversations(self, user_id: str) -> Dict[str, Any]:
        """Load all conversations for a user"""
        file_path = self._get_user_conversations_file(user_id)
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)
        return {"conversations": {}}

    def _save_user_conversations(self, user_id: str, data: Dict[str, Any]) -> None:
        """Save conversations for a user"""
        file_path = self._get_user_conversations_file(user_id)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)

    def save_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str],
        title: str,
        messages: list
    ) -> str:
        """Save or update a conversation"""
        data = self._load_user_conversations(user_id)

        # Generate new ID if not provided
        if not conversation_id:
            conversation_id = secrets.token_hex(8)

        # Save conversation
        data["conversations"][conversation_id] = {
            "id": conversation_id,
            "title": title[:100],  # Limit title length
            "messages": messages,
            "message_count": len(messages),
            "created_at": data["conversations"].get(conversation_id, {}).get(
                "created_at", datetime.utcnow().isoformat()
            ),
            "updated_at": datetime.utcnow().isoformat(),
        }

        self._save_user_conversations(user_id, data)
        logger.info(f"Saved conversation {conversation_id} for user {user_id}")

        return conversation_id

    def get_conversations_list(self, user_id: str, limit: int = 20) -> list:
        """Get list of conversations for a user (most recent first)"""
        data = self._load_user_conversations(user_id)

        conversations = list(data["conversations"].values())

        # Sort by updated_at descending
        conversations.sort(key=lambda c: c.get("updated_at", ""), reverse=True)

        # Return summary only (without full messages)
        return [
            {
                "id": c["id"],
                "title": c["title"],
                "created_at": c["created_at"],
                "message_count": c["message_count"],
            }
            for c in conversations[:limit]
        ]

    def get_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific conversation"""
        data = self._load_user_conversations(user_id)

        if conversation_id in data["conversations"]:
            return data["conversations"][conversation_id]

        return None

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Delete a conversation"""
        data = self._load_user_conversations(user_id)

        if conversation_id in data["conversations"]:
            del data["conversations"][conversation_id]
            self._save_user_conversations(user_id, data)
            logger.info(f"Deleted conversation {conversation_id} for user {user_id}")
            return True

        return False


# Singleton instances
_auth_service: Optional[AuthService] = None
_conversation_storage: Optional[ConversationStorage] = None


def get_auth_service() -> AuthService:
    """Get or create the singleton AuthService instance"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def get_conversation_storage() -> ConversationStorage:
    """Get or create the singleton ConversationStorage instance"""
    global _conversation_storage
    if _conversation_storage is None:
        _conversation_storage = ConversationStorage()
    return _conversation_storage
