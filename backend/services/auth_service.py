"""
Authentication Service - MongoDB-based user management
"""
import hashlib
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from config import settings

logger = logging.getLogger(__name__)

# MongoDB client and database
_mongo_client: Optional[MongoClient] = None
_db = None


def get_mongo_client():
    """Get or create MongoDB client"""
    global _mongo_client, _db
    if _mongo_client is None:
        # Construct MongoDB URI with authentication
        mongo_uri = settings.MONGODB_URI
        if settings.DATABASE_PASSWORD:
            # Replace password placeholder if exists
            mongo_uri = mongo_uri.replace("<db_password>", settings.DATABASE_PASSWORD)
        
        _mongo_client = MongoClient(mongo_uri)
        _db = _mongo_client[settings.DATABASE_NAME]
        
        # Create indexes
        _db.users.create_index("email", unique=True)
        _db.tokens.create_index("token", unique=True)
        _db.tokens.create_index("expires_at")
        _db.conversations.create_index([("user_id", 1), ("updated_at", -1)])
        
        logger.info("MongoDB connection established")
    
    return _db


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
    """MongoDB-based authentication service"""

    def __init__(self):
        self.db = get_mongo_client()

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
        email_lower = email.lower()

        # Check if email already exists
        if self.db.users.find_one({"email": email_lower}):
            return None

        # Hash password
        hashed, salt = _hash_password(password)

        # Calculate age and age group from DOB
        age, age_group = _calculate_age_and_group(dob)

        # Create user
        user_id = _generate_user_id()
        user_doc = {
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
            "created_at": datetime.utcnow(),
        }

        try:
            # Save user to MongoDB
            self.db.users.insert_one(user_doc)
            logger.info(f"New user registered: {email_lower}")

            # Generate token
            token = self._create_token(user_id)

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
                    "created_at": user_doc["created_at"].isoformat(),
                },
                "token": token,
            }
        except DuplicateKeyError:
            logger.error(f"Duplicate email during registration: {email_lower}")
            return None

    def login_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Login an existing user"""
        email_lower = email.lower()

        # Find user in MongoDB
        user = self.db.users.find_one({"email": email_lower})
        if not user:
            return None

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
                "created_at": user["created_at"].isoformat(),
            },
            "token": token,
        }

    def _create_token(self, user_id: str) -> str:
        """Create and store a new token for user"""
        token = _generate_token()

        token_doc = {
            "token": token,
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=30),
        }

        self.db.tokens.insert_one(token_doc)
        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify token and return user info"""
        # Find token in MongoDB
        token_doc = self.db.tokens.find_one({"token": token})
        if not token_doc:
            return None

        # Check expiration
        if datetime.utcnow() > token_doc["expires_at"]:
            # Token expired, remove it
            self.db.tokens.delete_one({"token": token})
            return None

        # Get user
        user = self.db.users.find_one({"id": token_doc["user_id"]})
        if not user:
            return None

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
            "created_at": user["created_at"].isoformat(),
        }

    def logout_user(self, token: str) -> bool:
        """Logout user by invalidating token"""
        result = self.db.tokens.delete_one({"token": token})
        return result.deleted_count > 0


class ConversationStorage:
    """Store and retrieve user conversations in MongoDB"""

    def __init__(self):
        self.db = get_mongo_client()

    def save_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str],
        title: str,
        messages: list
    ) -> str:
        """Save or update a conversation"""
        # Generate new ID if not provided
        if not conversation_id:
            conversation_id = secrets.token_hex(8)

        # Check if conversation exists
        existing = self.db.conversations.find_one({
            "user_id": user_id,
            "id": conversation_id
        })

        conversation_doc = {
            "id": conversation_id,
            "user_id": user_id,
            "title": title[:100],  # Limit title length
            "messages": messages,
            "message_count": len(messages),
            "created_at": existing["created_at"] if existing else datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        # Upsert conversation
        self.db.conversations.update_one(
            {"user_id": user_id, "id": conversation_id},
            {"$set": conversation_doc},
            upsert=True
        )

        logger.info(f"Saved conversation {conversation_id} for user {user_id}")
        return conversation_id

    def get_conversations_list(self, user_id: str, limit: int = 20) -> list:
        """Get list of conversations for a user (most recent first)"""
        conversations = list(
            self.db.conversations
            .find({"user_id": user_id})
            .sort("updated_at", -1)
            .limit(limit)
        )

        # Return summary only (without full messages)
        return [
            {
                "id": c["id"],
                "title": c["title"],
                "created_at": c["created_at"].isoformat(),
                "message_count": c["message_count"],
            }
            for c in conversations
        ]

    def get_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific conversation"""
        conversation = self.db.conversations.find_one({
            "user_id": user_id,
            "id": conversation_id
        })

        if conversation:
            # Convert datetime to ISO format for JSON serialization
            conversation["created_at"] = conversation["created_at"].isoformat()
            conversation["updated_at"] = conversation["updated_at"].isoformat()

        return conversation

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Delete a conversation"""
        result = self.db.conversations.delete_one({
            "user_id": user_id,
            "id": conversation_id
        })

        if result.deleted_count > 0:
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