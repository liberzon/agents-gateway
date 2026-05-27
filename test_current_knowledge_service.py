#!/usr/bin/env python3
"""
Reproduction script to test current knowledge service functionality
before refactoring.
"""

import asyncio
import os
import sys
from typing import Optional
from unittest.mock import Mock

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uuid
from datetime import datetime

from api.services.knowledge_service import KnowledgeService


class MockKnowledgeEntry:
    """Mock KnowledgeEntryDB for testing."""

    def __init__(self, file_id: str, tenant_id: str, collection_id: Optional[str] = None):
        self.id = uuid.uuid4()
        self.tenant_id = tenant_id
        self.collection_id = collection_id
        self.file_id = file_id
        self.original_filename = "test_document.txt"
        self.file_type = "project"
        self.content_type = "text/plain"
        self.gcs_path = None
        self.status = "active"
        self.knowledge_status = "indexing"
        self.entry_metadata = {"test": "metadata"}
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


async def test_current_knowledge_service():
    """Test current knowledge service functionality."""
    print("Testing current KnowledgeService implementation...")

    # Create mock database session
    mock_db = Mock()

    # Create test data
    tenant_id = "test-tenant-123"
    collection_id = "test-collection-456"
    file_id = str(uuid.uuid4())
    content = "This is test content for the knowledge base."

    # Mock knowledge entry
    mock_entry = MockKnowledgeEntry(file_id, tenant_id, collection_id)

    # Mock CRUD functions
    async def mock_get_knowledge_entry(db, tenant_id, file_id, collection_id=None):
        return mock_entry

    async def mock_update_knowledge_entry(db, tenant_id, file_id, updates, collection_id=None):
        print(f"Mock update called with updates: {updates}")
        return True

    # Patch the CRUD functions
    import db.knowledge_crud

    db.knowledge_crud.get_knowledge_entry = mock_get_knowledge_entry
    db.knowledge_crud.update_knowledge_entry = mock_update_knowledge_entry

    try:
        # Initialize knowledge service
        service = KnowledgeService()
        print("✓ KnowledgeService initialized successfully")
        print(f"  - Qdrant URL: {service.qdrant_url}")
        print(f"  - KB type: {type(service._kb).__name__}")  # type: ignore

        # Test indexing
        print("\n1. Testing index_knowledge_entry...")
        result = await service.index_knowledge_entry(
            db=mock_db, tenant_id=tenant_id, file_id=file_id, content=content, collection_id=collection_id
        )
        print(f"   Index result: {result}")

        # Test search
        print("\n2. Testing search_knowledge...")
        search_results = await service.search_knowledge(
            db=mock_db, tenant_id=tenant_id, query="test content", collection_id=collection_id, k=5
        )
        print(f"   Search results count: {len(search_results)}")

        # Test reindexing
        print("\n3. Testing reindex_knowledge_entry...")
        reindex_result = await service.reindex_knowledge_entry(
            db=mock_db,
            tenant_id=tenant_id,
            file_id=file_id,
            content=content + " Updated content.",
            collection_id=collection_id,
        )
        print(f"   Reindex result: {reindex_result}")

        # Test removal
        print("\n4. Testing remove_knowledge_entry...")
        remove_result = await service.remove_knowledge_entry(
            db=mock_db, tenant_id=tenant_id, file_id=file_id, collection_id=collection_id
        )
        print(f"   Remove result: {remove_result}")

        # Test stats
        print("\n5. Testing get_knowledge_stats...")
        stats = await service.get_knowledge_stats(tenant_id=tenant_id, collection_id=collection_id)
        print(f"   Stats: {stats}")

        print("\n✓ All current functionality tests completed successfully!")

    except Exception as e:
        print(f"✗ Error testing current functionality: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


async def main():
    """Main test function."""
    print("=" * 60)
    print("KNOWLEDGE SERVICE - CURRENT FUNCTIONALITY TEST")
    print("=" * 60)

    success = await test_current_knowledge_service()

    print("\n" + "=" * 60)
    if success:
        print("✓ Current functionality test PASSED")
    else:
        print("✗ Current functionality test FAILED")
    print("=" * 60)

    return success


if __name__ == "__main__":
    asyncio.run(main())
