import asyncio
import unittest
import uuid
from datetime import datetime
from unittest.mock import MagicMock

from db.db_models import KnowledgeEntryDB
from db.knowledge_crud import (
    create_knowledge_entry,
    delete_knowledge_entry,
    get_knowledge_entries,
    get_knowledge_entry,
    get_knowledge_entry_by_id,
    hard_delete_knowledge_entry,
    soft_delete_knowledge_entry,
    update_knowledge_entry,
)


class TestKnowledgeCRUD(unittest.TestCase):
    """Test knowledge CRUD operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock()
        self.test_tenant_id = "test-tenant-123"
        self.test_collection_id = "test-collection-456"
        self.test_file_id = str(uuid.uuid4())
        self.test_knowledge_id = str(uuid.uuid4())

        self.sample_knowledge_data = {
            "id": uuid.uuid4(),
            "tenant_id": self.test_tenant_id,
            "collection_id": None,
            "file_id": uuid.UUID(self.test_file_id),
            "original_filename": "test-document.pdf",
            "file_type": "company",
            "content_type": "application/pdf",
            "gcs_path": "files/company/test-document.pdf",
            "status": "active",
            "knowledge_status": "indexed",
            "entry_metadata": {"tags": ["test", "document"]},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

    def test_create_knowledge_entry_success(self):
        """Test successful knowledge entry creation."""
        # Mock database operations
        self.mock_db.add = MagicMock()
        self.mock_db.commit = MagicMock()
        self.mock_db.refresh = MagicMock()

        # Run async function
        async def run_test():
            entry = await create_knowledge_entry(
                db=self.mock_db,
                tenant_id=self.test_tenant_id,
                file_id=self.test_file_id,
                original_filename="test-document.pdf",
                file_type="company",
                content_type="application/pdf",
                gcs_path="files/company/test-document.pdf",
                status="active",
                metadata={"tags": ["test", "document"]},
            )

            # Assertions
            self.mock_db.add.assert_called_once()
            self.mock_db.commit.assert_called_once()
            self.mock_db.refresh.assert_called_once()
            self.assertIsInstance(entry, KnowledgeEntryDB)
            self.assertEqual(entry.tenant_id, self.test_tenant_id)
            self.assertEqual(entry.original_filename, "test-document.pdf")
            self.assertEqual(entry.file_type, "company")

        # Run the test
        asyncio.run(run_test())

    def test_create_knowledge_entry_rollback_on_error(self):
        """Test rollback when knowledge entry creation fails."""
        # Mock database operations to raise exception
        self.mock_db.add = MagicMock()
        self.mock_db.commit = MagicMock(side_effect=Exception("Database error"))
        self.mock_db.rollback = MagicMock()

        async def run_test():
            # Attempt to create knowledge entry
            with self.assertRaises(Exception):
                await create_knowledge_entry(
                    db=self.mock_db,
                    tenant_id=self.test_tenant_id,
                    file_id=self.test_file_id,
                    original_filename="test-document.pdf",
                    file_type="company",
                )

            # Check rollback was called
            self.mock_db.rollback.assert_called_once()

        # Run the test
        asyncio.run(run_test())

    def test_get_knowledge_entries_org_level(self):
        """Test retrieving tenant-level knowledge entries."""
        # Mock database query
        mock_entries = [MagicMock(spec=KnowledgeEntryDB), MagicMock(spec=KnowledgeEntryDB)]
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 2
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_entries
        self.mock_db.query.return_value = mock_query

        async def run_test():
            entries, total_count = await get_knowledge_entries(
                db=self.mock_db, tenant_id=self.test_tenant_id, collection_id=None, limit=50, offset=0
            )

            # Assertions
            self.assertEqual(len(entries), 2)
            self.assertEqual(total_count, 2)
            self.assertEqual(entries, mock_entries)

        # Run the test
        asyncio.run(run_test())

    def test_get_knowledge_entries_project_level(self):
        """Test retrieving collection-level knowledge entries."""
        # Mock database query
        mock_entries = [MagicMock(spec=KnowledgeEntryDB)]
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_entries
        self.mock_db.query.return_value = mock_query

        async def run_test():
            entries, total_count = await get_knowledge_entries(
                db=self.mock_db,
                tenant_id=self.test_tenant_id,
                collection_id=self.test_collection_id,
                limit=50,
                offset=0,
            )

            # Assertions
            self.assertEqual(len(entries), 1)
            self.assertEqual(total_count, 1)
            self.assertEqual(entries, mock_entries)

        # Run the test
        asyncio.run(run_test())

    def test_get_knowledge_entry_found(self):
        """Test retrieving an existing knowledge entry."""
        # Mock database query
        mock_entry = MagicMock(spec=KnowledgeEntryDB)
        mock_entry.id = uuid.UUID(self.test_knowledge_id)
        mock_entry.tenant_id = self.test_tenant_id
        mock_entry.file_id = uuid.UUID(self.test_file_id)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_entry
        self.mock_db.query.return_value = mock_query

        async def run_test():
            entry = await get_knowledge_entry(
                db=self.mock_db, tenant_id=self.test_tenant_id, file_id=self.test_file_id, collection_id=None
            )

            # Assertions
            self.assertEqual(entry, mock_entry)
            self.mock_db.query.assert_called_once_with(KnowledgeEntryDB)

        # Run the test
        asyncio.run(run_test())

    def test_get_knowledge_entry_not_found(self):
        """Test retrieving a non-existent knowledge entry."""
        # Mock database query to return None
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        self.mock_db.query.return_value = mock_query

        async def run_test():
            entry = await get_knowledge_entry(
                db=self.mock_db, tenant_id=self.test_tenant_id, file_id=self.test_file_id, collection_id=None
            )

            # Assertions
            self.assertIsNone(entry)

        # Run the test
        asyncio.run(run_test())

    def test_update_knowledge_entry_success(self):
        """Test successful knowledge entry update."""
        # Mock existing entry
        mock_existing_entry = KnowledgeEntryDB(**self.sample_knowledge_data)

        # Mock get_knowledge_entry to return existing entry
        async def mock_get_knowledge_entry(*args, **kwargs):
            return mock_existing_entry

        # Patch the function
        import db.knowledge_crud

        original_get = db.knowledge_crud.get_knowledge_entry
        db.knowledge_crud.get_knowledge_entry = mock_get_knowledge_entry

        # Mock database operations
        self.mock_db.commit = MagicMock()
        self.mock_db.refresh = MagicMock()

        async def run_test():
            try:
                updated_entry = await update_knowledge_entry(
                    db=self.mock_db,
                    tenant_id=self.test_tenant_id,
                    file_id=self.test_file_id,
                    updates={"status": "archived", "knowledge_status": "outdated"},
                    collection_id=None,
                )

                # Assertions
                self.mock_db.commit.assert_called_once()
                self.mock_db.refresh.assert_called_once()
                self.assertIsNotNone(updated_entry)
                assert updated_entry is not None
                self.assertEqual(updated_entry.status, "archived")
                self.assertEqual(updated_entry.knowledge_status, "outdated")
            finally:
                # Restore original function
                db.knowledge_crud.get_knowledge_entry = original_get

        # Run the test
        asyncio.run(run_test())

    def test_update_knowledge_entry_not_found(self):
        """Test updating a non-existent knowledge entry."""

        # Mock get_knowledge_entry to return None
        async def mock_get_knowledge_entry(*args, **kwargs):
            return None

        # Patch the function
        import db.knowledge_crud

        original_get = db.knowledge_crud.get_knowledge_entry
        db.knowledge_crud.get_knowledge_entry = mock_get_knowledge_entry

        async def run_test():
            try:
                updated_entry = await update_knowledge_entry(
                    db=self.mock_db,
                    tenant_id=self.test_tenant_id,
                    file_id=self.test_file_id,
                    updates={"status": "archived"},
                    collection_id=None,
                )

                # Assertions
                self.assertIsNone(updated_entry)
            finally:
                # Restore original function
                db.knowledge_crud.get_knowledge_entry = original_get

        # Run the test
        asyncio.run(run_test())

    def test_soft_delete_knowledge_entry(self):
        """Test soft deletion of a knowledge entry."""
        # Mock existing entry
        mock_existing_entry = KnowledgeEntryDB(**self.sample_knowledge_data)

        # Mock get_knowledge_entry to return existing entry
        async def mock_get_knowledge_entry(*args, **kwargs):
            return mock_existing_entry

        # Patch the function
        import db.knowledge_crud

        original_get = db.knowledge_crud.get_knowledge_entry
        db.knowledge_crud.get_knowledge_entry = mock_get_knowledge_entry

        # Mock database operations
        self.mock_db.commit = MagicMock()

        async def run_test():
            try:
                result = await soft_delete_knowledge_entry(
                    db=self.mock_db, tenant_id=self.test_tenant_id, file_id=self.test_file_id, collection_id=None
                )

                # Assertions
                self.assertTrue(result)
                self.assertEqual(mock_existing_entry.status, "deleted")
                self.mock_db.commit.assert_called_once()
            finally:
                # Restore original function
                db.knowledge_crud.get_knowledge_entry = original_get

        # Run the test
        asyncio.run(run_test())

    def test_hard_delete_knowledge_entry(self):
        """Test hard deletion of a knowledge entry."""
        # Mock existing entry
        mock_existing_entry = KnowledgeEntryDB(**self.sample_knowledge_data)

        # Mock get_knowledge_entry to return existing entry
        async def mock_get_knowledge_entry(*args, **kwargs):
            return mock_existing_entry

        # Patch the function
        import db.knowledge_crud

        original_get = db.knowledge_crud.get_knowledge_entry
        db.knowledge_crud.get_knowledge_entry = mock_get_knowledge_entry

        # Mock database operations
        self.mock_db.delete = MagicMock()
        self.mock_db.commit = MagicMock()

        async def run_test():
            try:
                result = await hard_delete_knowledge_entry(
                    db=self.mock_db, tenant_id=self.test_tenant_id, file_id=self.test_file_id, collection_id=None
                )

                # Assertions
                self.assertTrue(result)
                self.mock_db.delete.assert_called_once_with(mock_existing_entry)
                self.mock_db.commit.assert_called_once()
            finally:
                # Restore original function
                db.knowledge_crud.get_knowledge_entry = original_get

        # Run the test
        asyncio.run(run_test())

    def test_delete_knowledge_entry_not_found(self):
        """Test deleting a non-existent knowledge entry."""

        # Mock get_knowledge_entry to return None
        async def mock_get_knowledge_entry(*args, **kwargs):
            return None

        # Patch the function
        import db.knowledge_crud

        original_get = db.knowledge_crud.get_knowledge_entry
        db.knowledge_crud.get_knowledge_entry = mock_get_knowledge_entry

        async def run_test():
            try:
                result = await delete_knowledge_entry(
                    db=self.mock_db,
                    tenant_id=self.test_tenant_id,
                    file_id=self.test_file_id,
                    collection_id=None,
                    hard_delete=False,
                )

                # Assertions
                self.assertFalse(result)
            finally:
                # Restore original function
                db.knowledge_crud.get_knowledge_entry = original_get

        # Run the test
        asyncio.run(run_test())

    def test_get_knowledge_entry_by_id(self):
        """Test retrieving knowledge entry by its ID."""
        # Mock database query
        mock_entry = MagicMock(spec=KnowledgeEntryDB)
        mock_entry.id = uuid.UUID(self.test_knowledge_id)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_entry
        self.mock_db.query.return_value = mock_query

        async def run_test():
            entry = await get_knowledge_entry_by_id(db=self.mock_db, knowledge_id=self.test_knowledge_id)

            # Assertions
            self.assertEqual(entry, mock_entry)
            self.mock_db.query.assert_called_once_with(KnowledgeEntryDB)

        # Run the test
        asyncio.run(run_test())

    def test_create_knowledge_entry_invalid_file_id(self):
        """Test knowledge entry creation with invalid file_id."""

        async def run_test():
            with self.assertRaises(ValueError):
                await create_knowledge_entry(
                    db=self.mock_db,
                    tenant_id=self.test_tenant_id,
                    file_id="invalid-uuid",
                    original_filename="test-document.pdf",
                    file_type="company",
                )

        # Run the test
        asyncio.run(run_test())

    def test_create_knowledge_entry_with_collection_id(self):
        """Test successful knowledge entry creation with collection_id."""
        # Mock database operations
        self.mock_db.add = MagicMock()
        self.mock_db.commit = MagicMock()
        self.mock_db.refresh = MagicMock()

        async def run_test():
            entry = await create_knowledge_entry(
                db=self.mock_db,
                tenant_id=self.test_tenant_id,
                file_id=self.test_file_id,
                original_filename="project-doc.md",
                file_type="project",
                collection_id=self.test_collection_id,
                content_type="text/markdown",
                status="active",
                metadata={"tags": ["project", "spec"]},
            )

            # Assertions
            self.mock_db.add.assert_called_once()
            self.mock_db.commit.assert_called_once()
            self.mock_db.refresh.assert_called_once()
            self.assertIsInstance(entry, KnowledgeEntryDB)
            self.assertEqual(entry.tenant_id, self.test_tenant_id)
            self.assertEqual(entry.collection_id, self.test_collection_id)
            self.assertEqual(entry.file_type, "project")

        # Run the test
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
