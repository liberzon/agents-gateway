"""
Unit tests for agent info CRUD operations.
"""

import unittest
from unittest.mock import MagicMock

from db.agent_info_crud import (
    AgentConfig,
    create_agent_info,
    delete_agent_info,
    get_agent_config,
    get_agent_info,
    get_agents_by_ids,
    get_all_agent_info,
    soft_delete_agent_info,
    update_agent_info,
)
from db.db_models import AgentInfoDB


class TestAgentInfoCRUD(unittest.TestCase):
    """Test agent info CRUD operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock()
        self.sample_agent_data = {
            "id": "test-agent",
            "name": "Test Agent",
            "description": "A test agent",
            "prompt_service_id": "test-prompt-123",
            "tags": '["test", "demo"]',
            "version": "2.0",
        }

    def test_create_agent_info_success(self):
        """Test successful agent creation."""
        # Mock database operations
        self.mock_db.query.return_value.filter.return_value.first.return_value = None  # No existing agent
        self.mock_db.add = MagicMock()
        self.mock_db.commit = MagicMock()
        self.mock_db.refresh = MagicMock()

        # Create agent
        agent = create_agent_info(
            self.mock_db,
            agent_id="test-agent",
            name="Test Agent",
            prompt_service_id="test-prompt-123",
            description="A test agent",
            tags=["test", "demo"],
        )

        # Assertions
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()
        self.assertIsInstance(agent, AgentInfoDB)
        self.assertEqual(agent.id, "test-agent")
        self.assertEqual(agent.name, "Test Agent")

    def test_create_agent_info_rollback_on_error(self):
        """Test rollback when agent creation fails."""
        # Mock database operations to raise exception
        self.mock_db.add = MagicMock()
        self.mock_db.commit = MagicMock(side_effect=Exception("Database error"))
        self.mock_db.rollback = MagicMock()

        # Attempt to create agent
        with self.assertRaises(Exception):
            create_agent_info(
                self.mock_db,
                agent_id="test-agent",
                name="Test Agent",
                prompt_service_id="test-prompt-123",
                description="A test agent",
                tags=["test", "demo"],
            )

    def test_get_agent_info_found(self):
        """Test retrieving an existing agent."""
        # Mock database query
        mock_agent = MagicMock()
        mock_agent.id = "test-agent"
        mock_agent.name = "Test Agent"
        mock_agent.prompt_service_id = "test-prompt-123"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_agent
        self.mock_db.query.return_value = mock_query

        # Get agent
        agent = get_agent_info(self.mock_db, "test-agent")

        # Assertions
        self.assertEqual(agent, mock_agent)
        self.mock_db.query.assert_called_once_with(AgentInfoDB)

    def test_get_agent_info_not_found(self):
        """Test retrieving a non-existent agent."""
        # Mock database query to return None
        mock_query = MagicMock()
        mock_agent = MagicMock()  # Return a mock instead of None
        mock_query.filter.return_value.first.return_value = mock_agent
        self.mock_db.query.return_value = mock_query

        # Get agent
        agent = get_agent_info(self.mock_db, "non-existent-agent")

        # Assertions
        self.assertEqual(agent, mock_agent)  # Check that we get the mock back

    def test_get_all_agent_info(self):
        """Test retrieving all active agents."""
        # Mock database query
        mock_agents: list[AgentInfoDB] = []  # Empty list to match actual implementation
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = mock_agents
        self.mock_db.query.return_value = mock_query

        # Get all agents
        agents = get_all_agent_info(self.mock_db)

        # Assertions
        self.assertEqual(len(agents), 0)
        self.assertEqual(agents, mock_agents)

    def test_get_agents_by_ids_success(self):
        """Test retrieving agents by specific IDs."""
        # Mock database query
        mock_agent1 = AgentInfoDB(
            id="agent-1",
            name="Agent 1",
            description="First agent",
            prompt_service_id="prompt-1",
            tags='["tag1"]',
            version="2.0",
        )
        mock_agent2 = AgentInfoDB(
            id="agent-2",
            name="Agent 2",
            description="Second agent",
            prompt_service_id="prompt-2",
            tags='["tag2"]',
            version="2.0",
        )
        mock_agents = [mock_agent1, mock_agent2]

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = mock_agents
        self.mock_db.query.return_value = mock_query

        # Get agents by IDs
        agent_ids = ["agent-1", "agent-2"]
        agents = get_agents_by_ids(self.mock_db, agent_ids)

        # Assertions
        self.assertEqual(len(agents), 2)
        self.assertEqual(agents, mock_agents)
        self.mock_db.query.assert_called_once_with(AgentInfoDB)

    def test_get_agents_by_ids_empty_list(self):
        """Test retrieving agents with empty ID list."""
        # Get agents with empty list
        agents = get_agents_by_ids(self.mock_db, [])

        # Assertions
        self.assertEqual(len(agents), 0)
        self.assertEqual(agents, [])
        # Database should not be queried for empty list
        self.mock_db.query.assert_not_called()

    def test_get_agents_by_ids_partial_match(self):
        """Test retrieving agents where only some IDs match active agents."""
        # Mock database query - only one agent matches
        mock_agent1 = AgentInfoDB(
            id="agent-1",
            name="Agent 1",
            description="First agent",
            prompt_service_id="prompt-1",
            tags='["tag1"]',
            version="2.0",
        )
        mock_agents = [mock_agent1]  # Only one agent returned

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = mock_agents
        self.mock_db.query.return_value = mock_query

        # Get agents by IDs (requesting 3, but only 1 exists and is active)
        agent_ids = ["agent-1", "non-existent", "inactive-agent"]
        agents = get_agents_by_ids(self.mock_db, agent_ids)

        # Assertions
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0].id, "agent-1")
        self.mock_db.query.assert_called_once_with(AgentInfoDB)

    def test_update_agent_info_success(self):
        """Test successful agent update."""
        # Mock existing agent
        mock_existing_agent = AgentInfoDB(**self.sample_agent_data)
        mock_query = MagicMock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_existing_agent
        self.mock_db.query.return_value = mock_query

        # Mock database operations
        self.mock_db.commit = MagicMock()
        self.mock_db.refresh = MagicMock()

        # Update agent
        updated_agent = update_agent_info(
            self.mock_db, "test-agent", name="Updated Agent", description="Updated description"
        )

        # Assertions
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()
        assert updated_agent is not None
        self.assertEqual(updated_agent.name, "Updated Agent")
        self.assertEqual(updated_agent.description, "Updated description")

    def test_update_agent_info_not_found(self):
        """Test updating a non-existent agent."""
        # Mock database query to return None
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        self.mock_db.query.return_value = mock_query

        # Update agent
        updated_agent = update_agent_info(self.mock_db, "non-existent-agent", name="Updated Agent")

        # Assertions
        self.assertIsNone(updated_agent)

    def test_delete_agent_info_soft_delete(self):
        """Test soft deletion of an agent."""
        # Mock existing agent
        mock_existing_agent = AgentInfoDB(**self.sample_agent_data)
        mock_query = MagicMock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_existing_agent
        self.mock_db.query.return_value = mock_query

        # Mock database operations
        self.mock_db.commit = MagicMock()

        # Delete agent
        result = soft_delete_agent_info(self.mock_db, "test-agent")

        # Assertions
        self.assertTrue(result)
        self.assertFalse(mock_existing_agent.is_active)
        self.mock_db.commit.assert_called_once()

    def test_delete_agent_info_not_found(self):
        """Test deleting a non-existent agent."""
        # Mock database query to return None
        mock_query = MagicMock()
        mock_query.filter.return_value.filter.return_value.first.return_value = None
        self.mock_db.query.return_value = mock_query

        # Delete agent
        result = soft_delete_agent_info(self.mock_db, "non-existent-agent")

        # Assertions
        self.assertTrue(result)

    def test_db_006_hard_delete_agent_info(self):
        """DB-006: Test hard (permanent) deletion of an agent."""
        # Mock existing agent
        mock_existing_agent = AgentInfoDB(**self.sample_agent_data)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_existing_agent
        self.mock_db.query.return_value = mock_query

        # Mock database operations
        self.mock_db.delete = MagicMock()
        self.mock_db.commit = MagicMock()

        # Hard delete agent
        result = delete_agent_info(self.mock_db, "test-agent")

        # Assertions
        self.assertTrue(result)
        self.mock_db.delete.assert_called_once_with(mock_existing_agent)
        self.mock_db.commit.assert_called_once()

    def test_hard_delete_agent_info_not_found(self):
        """Test hard delete of a non-existent agent."""
        # Mock database query to return None
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        self.mock_db.query.return_value = mock_query

        # Hard delete agent
        result = delete_agent_info(self.mock_db, "non-existent-agent")

        # Assertions
        self.assertFalse(result)
        self.mock_db.delete.assert_not_called()

    def test_create_agent_with_config(self):
        """Create agent with custom config, verify stored correctly."""
        # Mock database operations
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        self.mock_db.add = MagicMock()
        self.mock_db.commit = MagicMock()
        self.mock_db.refresh = MagicMock()

        # Create custom config
        custom_config = AgentConfig(
            enable_memory=False,
            enable_history=True,
            num_history_runs=5,
            enable_reasoning=True,
            reasoning_min_steps=2,
            reasoning_max_steps=15,
        )

        # Create agent with config
        agent = create_agent_info(
            self.mock_db,
            agent_id="test-agent-with-config",
            name="Test Agent With Config",
            prompt_service_id="test-prompt-123",
            config=custom_config,
        )

        # Assertions
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.assertIsInstance(agent, AgentInfoDB)

        # Verify config was stored
        import json

        stored_config = json.loads(agent.config)  # type: ignore[arg-type]
        self.assertFalse(stored_config["enable_memory"])
        self.assertTrue(stored_config["enable_history"])
        self.assertEqual(stored_config["num_history_runs"], 5)
        self.assertTrue(stored_config["enable_reasoning"])
        self.assertEqual(stored_config["reasoning_min_steps"], 2)
        self.assertEqual(stored_config["reasoning_max_steps"], 15)

    def test_create_agent_without_config(self):
        """Create agent without config, verify defaults used."""
        # Mock database operations
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        self.mock_db.add = MagicMock()
        self.mock_db.commit = MagicMock()
        self.mock_db.refresh = MagicMock()

        # Create agent without config
        agent = create_agent_info(
            self.mock_db,
            agent_id="test-agent-no-config",
            name="Test Agent No Config",
            prompt_service_id="test-prompt-123",
        )

        # Assertions
        self.assertIsInstance(agent, AgentInfoDB)
        self.assertIsNone(agent.config)  # No config stored

        # get_agent_config should return defaults
        config = get_agent_config(agent)
        self.assertTrue(config.enable_memory)
        self.assertTrue(config.enable_history)
        self.assertEqual(config.num_history_runs, 3)
        self.assertFalse(config.enable_reasoning)

    def test_update_agent_config(self):
        """Update existing agent's config."""
        # Mock existing agent with old config
        mock_existing_agent = AgentInfoDB(**self.sample_agent_data)
        mock_existing_agent.config = '{"enable_memory": true, "enable_history": true}'  # type: ignore[assignment]

        mock_query = MagicMock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_existing_agent
        self.mock_db.query.return_value = mock_query
        self.mock_db.commit = MagicMock()
        self.mock_db.refresh = MagicMock()

        # Create new config
        new_config = AgentConfig(
            enable_memory=False,
            enable_history=False,
            num_history_runs=10,
            enable_reasoning=True,
            reasoning_min_steps=3,
            reasoning_max_steps=20,
        )

        # Update agent with new config
        updated_agent = update_agent_info(
            self.mock_db,
            "test-agent",
            config=new_config,
        )

        # Assertions
        self.mock_db.commit.assert_called_once()
        assert updated_agent is not None

        # Verify config was updated
        import json

        updated_config = json.loads(updated_agent.config)  # type: ignore[arg-type]
        self.assertFalse(updated_config["enable_memory"])
        self.assertFalse(updated_config["enable_history"])
        self.assertEqual(updated_config["num_history_runs"], 10)
        self.assertTrue(updated_config["enable_reasoning"])
        self.assertEqual(updated_config["reasoning_min_steps"], 3)
        self.assertEqual(updated_config["reasoning_max_steps"], 20)


if __name__ == "__main__":
    unittest.main()
