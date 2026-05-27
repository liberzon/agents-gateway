import datetime
import hashlib
import json
import logging
import secrets
from typing import Any, Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from db.db_models import ApiKeyDB


def _hash_api_key(api_key: str) -> str:
    """Hash an API key using SHA-256."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return f"agw_{secrets.token_urlsafe(32)}"


def create_api_key(
    db: Session,
    name: str,
    owner_id: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    rate_limit: int = 1000,
    expires_at: Optional[datetime.datetime] = None,
) -> tuple[ApiKeyDB, str]:
    """
    Create a new API key.

    Args:
        db: Database session
        name: Human-readable name for the key
        owner_id: Optional owner identifier
        scopes: List of allowed scopes (e.g., ["read", "write", "admin"])
        rate_limit: Max requests per hour (0 = unlimited)
        expires_at: Optional expiration datetime

    Returns:
        Tuple of (ApiKeyDB record, raw_api_key)
        IMPORTANT: The raw API key is only returned once at creation time.
    """
    # Generate a new API key
    raw_key = generate_api_key()
    key_hash = _hash_api_key(raw_key)

    # Serialize scopes to JSON string
    scopes_json = json.dumps(scopes) if scopes else None

    api_key_record = ApiKeyDB(
        key_hash=key_hash,
        name=name,
        owner_id=owner_id,
        scopes=scopes_json,
        rate_limit=rate_limit,
        expires_at=expires_at,
        is_active=True,
    )

    db.add(api_key_record)
    db.commit()
    db.refresh(api_key_record)

    logging.info(f"Created API key '{name}' (id={api_key_record.id}) for owner={owner_id}")
    return api_key_record, raw_key


def validate_api_key(db: Session, api_key: str) -> Optional[ApiKeyDB]:
    """
    Validate an API key and return the record if valid.

    Args:
        db: Database session
        api_key: The raw API key to validate

    Returns:
        ApiKeyDB record if valid, None otherwise
    """
    key_hash = _hash_api_key(api_key)

    api_key_record = (
        db.query(ApiKeyDB)
        .filter(
            and_(
                ApiKeyDB.key_hash == key_hash,
                ApiKeyDB.is_active == True,  # noqa: E712
            )
        )
        .first()
    )

    if not api_key_record:
        return None

    # Check expiration
    if api_key_record.expires_at and api_key_record.expires_at < datetime.datetime.utcnow():
        logging.warning(f"API key '{api_key_record.name}' has expired")
        return None

    # Update last_used_at
    api_key_record.last_used_at = datetime.datetime.utcnow()  # type: ignore[assignment]
    db.commit()

    return api_key_record


def get_api_key_by_id(db: Session, key_id: int) -> Optional[ApiKeyDB]:
    """Get an API key by its ID."""
    return db.query(ApiKeyDB).filter(ApiKeyDB.id == key_id).first()


def get_api_keys_by_owner(db: Session, owner_id: str, include_inactive: bool = False) -> List[ApiKeyDB]:
    """Get all API keys for an owner."""
    query = db.query(ApiKeyDB).filter(ApiKeyDB.owner_id == owner_id)
    if not include_inactive:
        query = query.filter(ApiKeyDB.is_active == True)  # noqa: E712
    return query.order_by(ApiKeyDB.created_at.desc()).all()


def get_all_api_keys(db: Session, include_inactive: bool = False) -> List[ApiKeyDB]:
    """Get all API keys."""
    query = db.query(ApiKeyDB)
    if not include_inactive:
        query = query.filter(ApiKeyDB.is_active == True)  # noqa: E712
    return query.order_by(ApiKeyDB.created_at.desc()).all()


def update_api_key(
    db: Session,
    key_id: int,
    name: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    rate_limit: Optional[int] = None,
    expires_at: Optional[datetime.datetime] = None,
    is_active: Optional[bool] = None,
) -> Optional[ApiKeyDB]:
    """
    Update an API key's metadata.

    Args:
        db: Database session
        key_id: API key ID
        name: New name (optional)
        scopes: New scopes (optional)
        rate_limit: New rate limit (optional)
        expires_at: New expiration (optional)
        is_active: New active status (optional)

    Returns:
        Updated ApiKeyDB record or None if not found
    """
    api_key_record = db.query(ApiKeyDB).filter(ApiKeyDB.id == key_id).first()
    if not api_key_record:
        return None

    if name is not None:
        api_key_record.name = name  # type: ignore[assignment]
    if scopes is not None:
        api_key_record.scopes = json.dumps(scopes)  # type: ignore[assignment]
    if rate_limit is not None:
        api_key_record.rate_limit = rate_limit  # type: ignore[assignment]
    if expires_at is not None:
        api_key_record.expires_at = expires_at  # type: ignore[assignment]
    if is_active is not None:
        api_key_record.is_active = is_active  # type: ignore[assignment]

    db.commit()
    db.refresh(api_key_record)
    logging.info(f"Updated API key id={key_id}")
    return api_key_record


def deactivate_api_key(db: Session, key_id: int) -> bool:
    """Soft delete an API key by setting is_active=False."""
    api_key_record = db.query(ApiKeyDB).filter(ApiKeyDB.id == key_id).first()
    if not api_key_record:
        return False

    api_key_record.is_active = False  # type: ignore[assignment]
    db.commit()
    logging.info(f"Deactivated API key id={key_id}")
    return True


def delete_api_key(db: Session, key_id: int) -> bool:
    """Permanently delete an API key."""
    api_key_record = db.query(ApiKeyDB).filter(ApiKeyDB.id == key_id).first()
    if not api_key_record:
        return False

    db.delete(api_key_record)
    db.commit()
    logging.info(f"Deleted API key id={key_id}")
    return True


def get_api_key_scopes(api_key_record: ApiKeyDB) -> List[str]:
    """Parse and return the scopes for an API key."""
    if not api_key_record.scopes:
        return []
    try:
        return json.loads(str(api_key_record.scopes))
    except (json.JSONDecodeError, TypeError):
        return []


def api_key_to_dict(api_key_record: ApiKeyDB) -> Dict[str, Any]:
    """Convert an ApiKeyDB record to a dictionary (excluding the hash)."""
    return {
        "id": api_key_record.id,
        "name": api_key_record.name,
        "owner_id": api_key_record.owner_id,
        "scopes": get_api_key_scopes(api_key_record),
        "rate_limit": api_key_record.rate_limit,
        "expires_at": api_key_record.expires_at.isoformat() if api_key_record.expires_at else None,
        "last_used_at": api_key_record.last_used_at.isoformat() if api_key_record.last_used_at else None,
        "created_at": api_key_record.created_at.isoformat() if api_key_record.created_at else None,
        "updated_at": api_key_record.updated_at.isoformat() if api_key_record.updated_at else None,
        "is_active": api_key_record.is_active,
    }
