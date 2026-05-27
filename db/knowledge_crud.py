import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.db_models import KnowledgeEntryDB


async def create_knowledge_entry(
    db: Session,
    tenant_id: str,
    file_id: str,
    original_filename: str,
    file_type: str,
    collection_id: Optional[str] = None,
    content_type: Optional[str] = None,
    gcs_path: Optional[str] = None,
    status: str = "pending",
    knowledge_status: str = "indexing",
    metadata: Optional[Dict[str, Any]] = None,
) -> KnowledgeEntryDB:
    """Create a new knowledge entry."""
    try:
        # Convert file_id to UUID if it's a string
        if isinstance(file_id, str):
            file_id_uuid = uuid.UUID(file_id)
        else:
            file_id_uuid = file_id

        knowledge_entry = KnowledgeEntryDB(
            tenant_id=tenant_id,
            collection_id=collection_id,
            file_id=file_id_uuid,
            original_filename=original_filename,
            file_type=file_type,
            content_type=content_type,
            gcs_path=gcs_path,
            status=status,
            knowledge_status=knowledge_status,
            entry_metadata=metadata or {},
        )

        db.add(knowledge_entry)
        db.commit()
        db.refresh(knowledge_entry)

        logging.info(f"Created knowledge entry {knowledge_entry.id} for tenant {tenant_id}")
        return knowledge_entry

    except IntegrityError as e:
        db.rollback()
        logging.error(f"Failed to create knowledge entry due to integrity error: {e}")
        raise ValueError(f"Knowledge entry with file_id {file_id} already exists for tenant {tenant_id}")
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to create knowledge entry: {e}")
        raise


async def get_knowledge_entries(
    db: Session,
    tenant_id: str,
    collection_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
) -> Tuple[List[KnowledgeEntryDB], int]:
    """Get knowledge entries for tenant or collection with pagination."""
    try:
        # Build base query
        query = db.query(KnowledgeEntryDB).filter(KnowledgeEntryDB.tenant_id == tenant_id)

        # Filter by collection if specified
        if collection_id is not None:
            query = query.filter(KnowledgeEntryDB.collection_id == collection_id)
        else:
            # For tenant-level queries, only get entries without collection_id
            query = query.filter(KnowledgeEntryDB.collection_id.is_(None))

        # Filter by status if specified
        if status_filter:
            query = query.filter(KnowledgeEntryDB.status == status_filter)

        # Get total count before applying pagination
        total_count = query.count()

        # Apply pagination and ordering
        entries = query.order_by(desc(KnowledgeEntryDB.created_at)).offset(offset).limit(limit).all()

        logging.info(f"Retrieved {len(entries)} knowledge entries for tenant {tenant_id}, collection {collection_id}")
        return entries, total_count

    except Exception as e:
        logging.error(f"Failed to get knowledge entries: {e}")
        raise


async def get_knowledge_entry(
    db: Session, tenant_id: str, file_id: str, collection_id: Optional[str] = None
) -> Optional[KnowledgeEntryDB]:
    """Get specific knowledge entry."""
    try:
        # Convert file_id to UUID if it's a string
        if isinstance(file_id, str):
            file_id_uuid = uuid.UUID(file_id)
        else:
            file_id_uuid = file_id

        query = db.query(KnowledgeEntryDB).filter(
            and_(KnowledgeEntryDB.tenant_id == tenant_id, KnowledgeEntryDB.file_id == file_id_uuid)
        )

        if collection_id is not None:
            query = query.filter(KnowledgeEntryDB.collection_id == collection_id)
        else:
            query = query.filter(KnowledgeEntryDB.collection_id.is_(None))

        entry = query.first()

        if entry:
            logging.info(f"Retrieved knowledge entry {entry.id} for tenant {tenant_id}")
        else:
            logging.info(f"Knowledge entry not found for file_id {file_id} in tenant {tenant_id}")

        return entry

    except Exception as e:
        logging.error(f"Failed to get knowledge entry: {e}")
        raise


async def update_knowledge_entry(
    db: Session, tenant_id: str, file_id: str, updates: Dict[str, Any], collection_id: Optional[str] = None
) -> Optional[KnowledgeEntryDB]:
    """Update knowledge entry."""
    try:
        entry = await get_knowledge_entry(db, tenant_id, file_id, collection_id)
        if not entry:
            return None

        # Apply updates
        for field, value in updates.items():
            if hasattr(entry, field):
                setattr(entry, field, value)

        db.commit()
        db.refresh(entry)

        logging.info(f"Updated knowledge entry {entry.id} for tenant {tenant_id}")
        return entry

    except Exception as e:
        db.rollback()
        logging.error(f"Failed to update knowledge entry: {e}")
        raise


async def delete_knowledge_entry(
    db: Session, tenant_id: str, file_id: str, collection_id: Optional[str] = None, hard_delete: bool = False
) -> bool:
    """Delete knowledge entry (soft or hard delete)."""
    try:
        entry = await get_knowledge_entry(db, tenant_id, file_id, collection_id)
        if not entry:
            return False

        if hard_delete:
            # Hard delete - actually remove from database
            db.delete(entry)
            logging.info(f"Hard deleted knowledge entry {entry.id} for tenant {tenant_id}")
        else:
            # Soft delete - mark as deleted
            entry.status = "deleted"  # type: ignore[assignment]
            logging.info(f"Soft deleted knowledge entry {entry.id} for tenant {tenant_id}")

        db.commit()
        return True

    except Exception as e:
        db.rollback()
        logging.error(f"Failed to delete knowledge entry: {e}")
        raise


async def get_knowledge_entry_by_id(db: Session, knowledge_id: str) -> Optional[KnowledgeEntryDB]:
    """Get knowledge entry by its ID."""
    try:
        # Convert knowledge_id to UUID if it's a string
        if isinstance(knowledge_id, str):
            knowledge_id_uuid = uuid.UUID(knowledge_id)
        else:
            knowledge_id_uuid = knowledge_id

        entry = db.query(KnowledgeEntryDB).filter(KnowledgeEntryDB.id == knowledge_id_uuid).first()

        if entry:
            logging.info(f"Retrieved knowledge entry {entry.id}")
        else:
            logging.info(f"Knowledge entry not found for id {knowledge_id}")

        return entry

    except Exception as e:
        logging.error(f"Failed to get knowledge entry by id: {e}")
        raise


async def soft_delete_knowledge_entry(
    db: Session, tenant_id: str, file_id: str, collection_id: Optional[str] = None
) -> bool:
    """Soft delete knowledge entry by setting status to 'deleted'."""
    return await delete_knowledge_entry(db, tenant_id, file_id, collection_id, hard_delete=False)


async def hard_delete_knowledge_entry(
    db: Session, tenant_id: str, file_id: str, collection_id: Optional[str] = None
) -> bool:
    """Hard delete knowledge entry from database."""
    return await delete_knowledge_entry(db, tenant_id, file_id, collection_id, hard_delete=True)
