import unittest
import uuid
from datetime import datetime
from typing import List
from unittest.mock import MagicMock, patch

import numpy as np
from agno.knowledge.document import Document

from api.services.knowledge_service import KnowledgeService
from db.db_models import KnowledgeEntryDB


class DummyEmbedder:
    """Deterministic embedder for unit tests — no external model required."""

    def __init__(self, dim: int = 64):
        self.dim = dim
        self.dimensions = dim
        self.enable_batch = False

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [self.get_embedding(text) for text in texts]

    def get_embedding(self, text: str) -> List[float]:
        hash_val = hash(text) % (2**32)
        np.random.seed(hash_val)
        return np.random.normal(0, 1, self.dim).tolist()

    def get_embedding_and_usage(self, text: str):
        return self.get_embedding(text), {"total_tokens": len(text.split())}


class TestKnowledgeService(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        # Patch api_settings to use in-memory Qdrant for testing
        self.api_settings_patcher = patch("api.services.knowledge_service.api_settings")
        mock_api_settings = self.api_settings_patcher.start()
        mock_api_settings.qdrant_url = None  # Force in-memory mode
        mock_api_settings.qdrant_api_key = None
        mock_api_settings.qdrant_port = 6333
        mock_api_settings.gemini_api_key = "test-key"

        # Create knowledge service with DummyEmbedder
        self.knowledge_service = KnowledgeService(embedder=DummyEmbedder())
        self.mock_db = MagicMock()
        self.test_tenant_id = "test-tenant-123"
        self.test_collection_id = "test-collection-456"
        self.test_file_id = str(uuid.uuid4())

        # Sample knowledge entry
        self.sample_entry = KnowledgeEntryDB(
            id=uuid.uuid4(),
            tenant_id=self.test_tenant_id,
            collection_id=None,
            file_id=uuid.UUID(self.test_file_id),
            original_filename="test-document.md",
            file_type="company",
            content_type="text/markdown",
            gcs_path="files/company/test-document.md",
            status="active",
            knowledge_status="indexing",
            entry_metadata={"tags": ["test", "document"]},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    def tearDown(self):
        """Clean up test fixtures."""
        # Stop all patches
        self.api_settings_patcher.stop()

    @patch("api.services.knowledge_service.update_knowledge_entry")
    def test_create_knowledge_base_success(self, mock_update):
        """Test successful knowledge base creation."""
        # Create a URL-based entry that doesn't require GCS
        url_entry = KnowledgeEntryDB(
            id=uuid.uuid4(),
            tenant_id=self.test_tenant_id,
            collection_id=None,
            file_id=uuid.UUID(self.test_file_id),
            original_filename="https://example.com/test-document",
            file_type="company",
            content_type="text/url",
            gcs_path=None,  # No GCS path
            status="active",
            knowledge_status="indexing",
            entry_metadata={"tags": ["test", "url"]},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Mock the update function
        mock_update.return_value = url_entry

        async def run_test():
            # Mock the URL fetch to return test content
            with patch.object(
                self.knowledge_service, "_fetch_url_content", return_value="Test document content from URL"
            ):
                result = await self.knowledge_service.create_knowledge_base(db=self.mock_db, entry=url_entry)

                # Should succeed
                self.assertTrue(result)
                mock_update.assert_called_once()

        # Run the async test
        import asyncio

        asyncio.run(run_test())

    @patch("api.services.knowledge_service.update_knowledge_entry")
    def test_update_knowledge_base_success(self, mock_update):
        """Test successful knowledge base update."""
        # Create a URL-based entry that doesn't require GCS
        url_entry = KnowledgeEntryDB(
            id=uuid.uuid4(),
            tenant_id=self.test_tenant_id,
            collection_id=None,
            file_id=uuid.UUID(self.test_file_id),
            original_filename="https://example.com/updated-document",
            file_type="company",
            content_type="text/url",
            gcs_path=None,  # No GCS path
            status="active",
            knowledge_status="indexing",
            entry_metadata={"tags": ["test", "url", "updated"]},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Mock the update function
        mock_update.return_value = url_entry

        async def run_test():
            # Mock the URL fetch to return test content
            with patch.object(
                self.knowledge_service, "_fetch_url_content", return_value="Updated document content from URL"
            ):
                result = await self.knowledge_service.update_knowledge_base(db=self.mock_db, entry=url_entry)

                # Should succeed
                self.assertTrue(result)
                mock_update.assert_called_once()

        # Run the async test
        import asyncio

        asyncio.run(run_test())

    @patch("api.services.knowledge_service.delete_knowledge_entry")
    def test_delete_knowledge_base_success(self, mock_delete):
        """Test successful knowledge base deletion."""
        # Mock the delete function
        mock_delete.return_value = True

        async def run_test():
            result = await self.knowledge_service.delete_knowledge_base(db=self.mock_db, entry=self.sample_entry)

            # Should succeed
            self.assertTrue(result)
            mock_delete.assert_called_once()

        # Run the async test
        import asyncio

        asyncio.run(run_test())

    @patch("api.services.knowledge_service.get_knowledge_entry")
    def test_index_knowledge_entry_not_found(self, mock_get):
        """Test indexing when knowledge entry not found."""
        # Mock entry not found
        mock_get.return_value = None

        async def run_test():
            result = await self.knowledge_service.index_knowledge_entry(
                db=self.mock_db,
                tenant_id=self.test_tenant_id,
                file_id=self.test_file_id,
                content="# Test Document\nThis is test content.",
                collection_id=None,
            )

            # Assertions
            self.assertFalse(result)

        # Run the async test
        import asyncio

        asyncio.run(run_test())

    def test_search_knowledge_with_results(self):
        """Test searching knowledge base with mocked results."""

        async def run_test():
            # Mock the dynamic KB to return Document objects
            with patch.object(self.knowledge_service, "get_dynamic_kb") as mock_get_kb:
                mock_dynamic_kb = MagicMock()
                mock_doc = Document(
                    content="Test content", meta_data={"tenant_id": self.test_tenant_id, "score": 0.9}, name="test_doc"
                )
                mock_dynamic_kb.search.return_value = [mock_doc]
                mock_get_kb.return_value = mock_dynamic_kb

                results = await self.knowledge_service.search_knowledge(
                    db=self.mock_db, tenant_id=self.test_tenant_id, query="test query", collection_id=None, k=5
                )

                # Should return the mocked results converted to dict format
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["document"], "Test content")

        # Run the async test
        import asyncio

        asyncio.run(run_test())

    @patch("api.services.knowledge_service.get_knowledge_entry")
    @patch("api.services.knowledge_service.delete_knowledge_entry")
    def test_remove_knowledge_entry(self, mock_delete, mock_get):
        """Test removing knowledge entry from index."""
        # Mock the CRUD functions
        mock_get.return_value = self.sample_entry
        mock_delete.return_value = True

        async def run_test():
            # This should not fail even if the KB doesn't exist yet
            result = await self.knowledge_service.remove_knowledge_entry(
                db=self.mock_db, tenant_id=self.test_tenant_id, file_id=self.test_file_id, collection_id=None
            )

            # Should succeed (no-op for non-existent entries)
            self.assertTrue(result)
            mock_get.assert_called_once()

        # Run the async test
        import asyncio

        asyncio.run(run_test())

    def test_search_knowledge_empty_kb(self):
        """Test searching empty knowledge base."""

        async def run_test():
            # Mock the dynamic KB to return empty results
            with patch.object(self.knowledge_service, "get_dynamic_kb") as mock_get_kb:
                mock_dynamic_kb = MagicMock()
                mock_dynamic_kb.search.return_value = []
                mock_get_kb.return_value = mock_dynamic_kb

                results = await self.knowledge_service.search_knowledge(
                    db=self.mock_db, tenant_id=self.test_tenant_id, query="test query", collection_id=None, k=5
                )

                # Should return empty list for new/empty KB
                self.assertEqual(results, [])

        # Run the async test
        import asyncio

        asyncio.run(run_test())

    def test_get_knowledge_stats_empty_kb(self):
        """Test getting stats for empty knowledge base."""

        async def run_test():
            stats = await self.knowledge_service.get_knowledge_stats(tenant_id=self.test_tenant_id, collection_id=None)

            # Should return empty stats for non-existent KB
            self.assertEqual(stats["total_chunks"], 0)
            self.assertEqual(stats["sources"], 0)

        # Run the async test
        import asyncio

        asyncio.run(run_test())

    def test_get_knowledge_stats_ready_status(self):
        """Test getting stats returns ready status."""

        async def run_test():
            stats = await self.knowledge_service.get_knowledge_stats(tenant_id=self.test_tenant_id, collection_id=None)

            # Should return ready status and correct type
            self.assertEqual(stats["status"], "ready")
            self.assertEqual(stats["kb_type"], "dynamic_qdrant")
            self.assertIn("total_chunks", stats)
            self.assertIn("sources", stats)

        # Run the async test
        import asyncio

        asyncio.run(run_test())

    def test_unified_knowledge_base_approach(self):
        """Test that the service uses a unified knowledge base approach."""
        # Test that the service has a unified dynamic KB
        dynamic_kb = self.knowledge_service.get_dynamic_kb()
        self.assertIsNotNone(dynamic_kb)

        # Test that the same KB instance is returned for multiple calls
        dynamic_kb2 = self.knowledge_service.get_dynamic_kb()
        self.assertEqual(dynamic_kb, dynamic_kb2)

        # Test that the KB has the expected collection name
        self.assertEqual(dynamic_kb.vector_db.collection, "unified_knowledge")  # type: ignore


if __name__ == "__main__":
    unittest.main()
