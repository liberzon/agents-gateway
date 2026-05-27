"""
Unit tests for V2 agent selector module.
"""

import unittest
from unittest.mock import MagicMock, patch

from agents import Model
from agents.v2_selector import get_agent as get_agent_v2
from agents.v2_selector import get_available_agents as get_available_agents_v2


class TestAgentSelectorV2(unittest.TestCase):
    """Test the V2 agent selector with caching."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_agent_info = MagicMock()
        self.sample_agent_info.id = "test-agent"
        self.sample_agent_info.prompt_service_id = "test-prompt-123"

    @patch("agents.v2_selector.get_all_agent_info")
    @patch("agents.v2_selector.get_db")
    def test_get_available_agents_v2(self, mock_get_db, mock_get_all):
        """Test getting available agents from database."""
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db

        mock_agents = [MagicMock(id="agent-1"), MagicMock(id="agent-2"), MagicMock(id="agent-3")]
        mock_get_all.return_value = mock_agents

        agents = get_available_agents_v2()

        self.assertEqual(agents, ["agent-1", "agent-2", "agent-3"])

    @patch("agents.v2_selector.get_available_agents")
    @patch("agents.v2_selector.get_agent_info")
    @patch("agents.v2_selector._get_prompt_from_local_storage")
    @patch("agents.v2_selector.get_agent_impl")
    @patch("agents.v2_selector.get_agent_config")
    @patch("agents.v2_selector.get_db")
    def test_get_agent_v2_success(
        self,
        mock_get_db,
        mock_get_agent_config,
        mock_get_agent,
        mock_get_prompt_local,
        mock_get_agent_info,
        mock_get_available,
    ):
        """Test successfully getting an agent with V2 selector."""
        # Setup mocks
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db
        mock_get_available.return_value = ["test-agent"]
        mock_get_agent_info.return_value = self.sample_agent_info

        mock_prompt = MagicMock()
        mock_prompt.template = "You are a test agent"
        mock_get_prompt_local.return_value = mock_prompt

        mock_config = MagicMock()
        mock_get_agent_config.return_value = mock_config

        mock_agent_instance = MagicMock()
        mock_get_agent.return_value = mock_agent_instance

        # Test the function
        agent = get_agent_v2(
            model_id=Model.gemini_2_5_pro, agent_id="test-agent", user_id="test-user", session_id="test-session"
        )

        # Assertions
        self.assertEqual(agent, mock_agent_instance)
        mock_get_prompt_local.assert_called_once_with(mock_db, "test-prompt-123")
        mock_get_agent_config.assert_called_once_with(self.sample_agent_info)
        mock_get_agent.assert_called_once_with(
            prompt=mock_prompt,
            user_id="test-user",
            session_id="test-session",
            organizer_email="default@example.com",
            tenant_id="default_tenant",
            model_id=Model.gemini_2_5_pro,
            debug_mode=True,
            fetch_token_func=None,
            config=mock_config,
        )

    @patch("agents.v2_selector.get_available_agents")
    @patch("agents.v2_selector.get_db")
    def test_get_agent_v2_not_found(self, mock_get_db, mock_get_available):
        """Test getting a non-existent agent with V2 selector."""
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db
        mock_get_available.return_value = ["existing-agent"]

        with self.assertRaises(ValueError) as context:
            get_agent_v2(agent_id="non-existent-agent")

        self.assertIn("Agent: non-existent-agent not found in database", str(context.exception))

    @patch("agents.v2_selector.get_available_agents")
    @patch("agents.v2_selector.get_agent_info")
    @patch("agents.v2_selector._get_prompt_from_local_storage")
    @patch("agents.v2_selector.get_db")
    def test_get_agent_v2_prompt_not_found(
        self, mock_get_db, mock_get_prompt_local, mock_get_agent_info, mock_get_available
    ):
        """Test handling when prompt is not found in local storage."""
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db
        mock_get_available.return_value = ["test-agent"]
        mock_get_agent_info.return_value = self.sample_agent_info
        mock_get_prompt_local.return_value = None

        with self.assertRaises(ValueError) as context:
            get_agent_v2(agent_id="test-agent")

        self.assertIn("Prompt: test-prompt-123 not found", str(context.exception))


class TestAgentSelectorCaching(unittest.TestCase):
    """Test agent selector caching functionality (SEL-010 to SEL-013)."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_agent_info = MagicMock()
        self.sample_agent_info.id = "test-agent"
        self.sample_agent_info.prompt_service_id = "test-prompt-123"

    def test_sel_010_cache_key_generation_crc32(self):
        """SEL-010: Cache key uses CRC32 hash of prompt template."""
        import zlib

        from api.routes.v2.agents import compute_cache_key

        template = "You are a helpful assistant"
        agent_id = "test-agent"
        model = MagicMock()
        model.value = "gemini-2.5-pro"
        user_id = "user123"
        session_id = "session456"

        cache_key = compute_cache_key(template, agent_id, model, user_id, session_id)

        # Verify CRC32 hash is in the key
        expected_hash = zlib.crc32(template.encode("utf-8")) & 0xFFFFFFFF
        self.assertTrue(cache_key.startswith(str(expected_hash)))

        # Verify key format: "crc32:agent_id:model:user_id:session_id"
        parts = cache_key.split(":")
        self.assertEqual(len(parts), 5)
        self.assertEqual(parts[0], str(expected_hash))
        self.assertEqual(parts[1], agent_id)
        self.assertEqual(parts[2], "gemini-2.5-pro")
        self.assertEqual(parts[3], user_id)
        self.assertEqual(parts[4], session_id)

    def test_sel_011_cache_hit(self):
        """SEL-011: Same parameters return cached agent."""
        from api.routes.v2.agents import _agent_cache, _cache_lock, compute_cache_key

        template = "Test prompt"
        agent_id = "cache-test-agent"
        model = MagicMock()
        model.value = "gemini-2.5-pro"
        user_id = "user1"
        session_id = "session1"

        cache_key = compute_cache_key(template, agent_id, model, user_id, session_id)

        # Add a mock agent to cache
        mock_agent = MagicMock()
        mock_agent.id = "cache-test-agent"

        with _cache_lock:
            _agent_cache[cache_key] = mock_agent

        try:
            # Verify cache lookup works
            with _cache_lock:
                cached_agent = _agent_cache.get(cache_key)

            self.assertIsNotNone(cached_agent)
            assert cached_agent is not None  # Type narrowing for mypy
            self.assertEqual(cached_agent.id, "cache-test-agent")
        finally:
            # Cleanup
            with _cache_lock:
                _agent_cache.pop(cache_key, None)

    def test_sel_012_cache_miss(self):
        """SEL-012: Different parameters create new agent (cache miss)."""
        from api.routes.v2.agents import _agent_cache, _cache_lock, compute_cache_key

        template = "Test prompt"
        agent_id = "miss-test-agent"
        model = MagicMock()
        model.value = "gemini-2.5-pro"

        # Generate key for user1
        key_user1 = compute_cache_key(template, agent_id, model, "user1", "session1")

        # Generate key for user2 (different user)
        key_user2 = compute_cache_key(template, agent_id, model, "user2", "session1")

        # Keys should be different
        self.assertNotEqual(key_user1, key_user2)

        # Add only user1 to cache
        mock_agent = MagicMock()
        with _cache_lock:
            _agent_cache[key_user1] = mock_agent

        try:
            # user2's key should not be in cache
            with _cache_lock:
                self.assertIn(key_user1, _agent_cache)
                self.assertNotIn(key_user2, _agent_cache)
        finally:
            # Cleanup
            with _cache_lock:
                _agent_cache.pop(key_user1, None)

    def test_sel_013_cache_differentiation_by_template_model(self):
        """SEL-013: Cache differentiates by template+model combination."""
        from api.routes.v2.agents import compute_cache_key

        agent_id = "diff-test-agent"
        user_id = "user1"
        session_id = "session1"
        model = MagicMock()
        model.value = "gemini-2.5-pro"

        # Different templates produce different keys
        key_template1 = compute_cache_key("Template A", agent_id, model, user_id, session_id)
        key_template2 = compute_cache_key("Template B", agent_id, model, user_id, session_id)
        self.assertNotEqual(key_template1, key_template2)

        # Different models produce different keys
        model2 = MagicMock()
        model2.value = "gemini-2.0-flash"
        key_model1 = compute_cache_key("Same template", agent_id, model, user_id, session_id)
        key_model2 = compute_cache_key("Same template", agent_id, model2, user_id, session_id)
        self.assertNotEqual(key_model1, key_model2)

        # Same everything produces same key
        key_same1 = compute_cache_key("Same template", agent_id, model, user_id, session_id)
        key_same2 = compute_cache_key("Same template", agent_id, model, user_id, session_id)
        self.assertEqual(key_same1, key_same2)


class TestAgentSelectorKnowledgeBase(unittest.TestCase):
    """Test agent selector with knowledge base (SEL-005)."""

    @patch("agents.v2_selector.get_available_agents")
    @patch("agents.v2_selector.get_agent_info")
    @patch("agents.v2_selector._get_prompt_from_local_storage")
    @patch("agents.v2_selector.get_agent_impl")
    @patch("agents.v2_selector.get_db")
    def test_sel_005_select_with_knowledge_base(
        self, mock_get_db, mock_get_agent, mock_get_prompt_local, mock_get_agent_info, mock_get_available
    ):
        """SEL-005: Agent selector passes org_id for knowledge base access."""
        # Setup mocks
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db
        mock_get_available.return_value = ["kb-enabled-agent"]

        mock_agent_info = MagicMock()
        mock_agent_info.id = "kb-enabled-agent"
        mock_agent_info.prompt_service_id = "kb-prompt-123"
        mock_get_agent_info.return_value = mock_agent_info

        mock_prompt = MagicMock()
        mock_prompt.template = "You are a knowledge-enabled agent"
        mock_get_prompt_local.return_value = mock_prompt

        mock_agent_instance = MagicMock()
        mock_get_agent.return_value = mock_agent_instance

        # Test with org_id for knowledge base
        org_id = "test_org_with_kb"
        _agent = get_agent_v2(
            model_id=Model.gemini_2_5_pro,
            agent_id="kb-enabled-agent",
            user_id="test-user",
            session_id="test-session",
            tenant_id=org_id,
        )

        # Verify tenant_id was passed to get_agent_impl
        mock_get_agent.assert_called_once()
        call_kwargs = mock_get_agent.call_args[1]
        self.assertEqual(call_kwargs["tenant_id"], org_id)


if __name__ == "__main__":
    unittest.main()
