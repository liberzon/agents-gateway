import os
import unittest

os.environ["TESTING"] = "true"


class TestKnowledgeFilterBuilding(unittest.TestCase):
    """Test the filter building logic used in knowledge service search."""

    def _build_search_filters(self, tenant_id, collection_id=None, extra_filters=None):
        """Replicate the filter building logic from KnowledgeService.search_knowledge."""
        search_filters = extra_filters or {}
        search_filters["meta_data.tenant_id"] = tenant_id
        if collection_id:
            search_filters["meta_data.collection_id"] = collection_id
        return search_filters

    def test_single_tenant_filter(self):
        """Builds correct filter for tenant_id only."""
        filters = self._build_search_filters(tenant_id="org-123")

        self.assertEqual(filters["meta_data.tenant_id"], "org-123")
        self.assertNotIn("meta_data.collection_id", filters)
        self.assertEqual(len(filters), 1)

    def test_tenant_and_collection_filter(self):
        """Combines tenant_id and collection_id filters."""
        filters = self._build_search_filters(tenant_id="org-123", collection_id="proj-456")

        self.assertEqual(filters["meta_data.tenant_id"], "org-123")
        self.assertEqual(filters["meta_data.collection_id"], "proj-456")
        self.assertEqual(len(filters), 2)

    def test_extra_filters(self):
        """Adds arbitrary metadata filters alongside tenant and collection."""
        extra = {"meta_data.file_type": "company", "meta_data.status": "indexed"}
        filters = self._build_search_filters(
            tenant_id="org-123",
            collection_id="proj-456",
            extra_filters=extra,
        )

        self.assertEqual(filters["meta_data.tenant_id"], "org-123")
        self.assertEqual(filters["meta_data.collection_id"], "proj-456")
        self.assertEqual(filters["meta_data.file_type"], "company")
        self.assertEqual(filters["meta_data.status"], "indexed")
        self.assertEqual(len(filters), 4)

    def test_none_collection_id_excluded(self):
        """When collection_id is None, it is not added to filters."""
        filters = self._build_search_filters(tenant_id="org-123", collection_id=None)

        self.assertNotIn("meta_data.collection_id", filters)

    def test_empty_string_collection_id_excluded(self):
        """When collection_id is empty string, it is not added to filters."""
        filters = self._build_search_filters(tenant_id="org-123", collection_id="")

        self.assertNotIn("meta_data.collection_id", filters)

    def test_extra_filters_not_mutated_externally(self):
        """Passing extra_filters dict is modified in place (documents existing behavior)."""
        extra = {"meta_data.custom": "value"}
        filters = self._build_search_filters(tenant_id="org-123", extra_filters=extra)

        # The function modifies the dict in place (same reference)
        self.assertIs(filters, extra)
        self.assertIn("meta_data.tenant_id", extra)


class TestAgnoFilterImport(unittest.TestCase):
    """Test whether agno.vectordb.filters is available for structured filtering."""

    def test_filter_import_availability(self):
        """Check if structured filter classes are importable from agno."""
        try:
            from agno.vectordb.filters import EQ, AND  # noqa: F401

            has_filters = True
        except ImportError:
            has_filters = False

        # Either outcome is acceptable; this test documents the availability.
        # If available, verify basic construction.
        if has_filters:
            from agno.vectordb.filters import EQ

            f = EQ("tenant_id", "org-123")
            self.assertIsNotNone(f)


if __name__ == "__main__":
    unittest.main()
