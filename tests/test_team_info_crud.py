import unittest
from unittest.mock import MagicMock, patch

from db.db_models import TeamAgentDB, TeamInfoDB
from db.team_info_crud import (
    add_agent_to_team,
    create_team_info,
    delete_team_info,
    get_agent_teams,
    get_all_team_info,
    get_team_agents,
    get_team_info,
    get_team_with_agents,
    remove_agent_from_team,
    soft_delete_team_info,
    team_info_exists,
    update_team_agent_role,
    update_team_info,
)


class TestTeamInfoCRUD(unittest.TestCase):
    """Tests for TeamInfo CRUD operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock()

        # Create mock TeamInfoDB
        self.mock_team = MagicMock(spec=TeamInfoDB)
        self.mock_team.id = "test-team"
        self.mock_team.name = "Test Team"
        self.mock_team.description = "A test team"
        self.mock_team.version = "2.0"
        self.mock_team.is_active = True

        # Create mock TeamAgentDB
        self.mock_team_agent = MagicMock(spec=TeamAgentDB)
        self.mock_team_agent.team_id = "test-team"
        self.mock_team_agent.agent_id = "test-agent"
        self.mock_team_agent.role = "assistant"
        self.mock_team_agent.order_index = 0
        self.mock_team_agent.is_active = True

    def test_create_team_info(self):
        """Test creating a team."""
        self.mock_db.add = MagicMock()
        self.mock_db.commit = MagicMock()
        self.mock_db.refresh = MagicMock()

        with patch("db.team_info_crud.logging"):
            result = create_team_info(
                self.mock_db,
                team_id="new-team",
                name="New Team",
                description="New team description",
            )

        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()
        self.assertIsNotNone(result)

    def test_get_team_info_found(self):
        """Test getting an existing team."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_team

        result = get_team_info(self.mock_db, "test-team")

        self.assertIsNotNone(result)
        assert result is not None  # for mypy
        self.assertEqual(result.id, "test-team")

    def test_get_team_info_not_found(self):
        """Test getting a non-existent team."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = None

        result = get_team_info(self.mock_db, "nonexistent")

        self.assertIsNone(result)

    def test_get_all_team_info_active_only(self):
        """Test getting all active teams."""
        mock_team_2 = MagicMock(spec=TeamInfoDB)
        mock_team_2.id = "team-2"
        mock_team_2.name = "Team 2"

        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = [
            self.mock_team,
            mock_team_2,
        ]
        self.mock_db.query.return_value = mock_query

        result = get_all_team_info(self.mock_db, include_inactive=False)

        self.assertEqual(len(result), 2)
        mock_query.filter.assert_called_once()

    def test_get_all_team_info_include_inactive(self):
        """Test getting all teams including inactive."""
        mock_query = MagicMock()
        mock_query.order_by.return_value.all.return_value = [self.mock_team]
        self.mock_db.query.return_value = mock_query

        result = get_all_team_info(self.mock_db, include_inactive=True)

        self.assertEqual(len(result), 1)
        mock_query.filter.assert_not_called()

    @patch("db.team_info_crud.get_team_info")
    def test_update_team_info_found(self, mock_get):
        """Test updating an existing team."""
        mock_get.return_value = self.mock_team

        with patch("db.team_info_crud.logging"):
            result = update_team_info(
                self.mock_db,
                team_id="test-team",
                name="Updated Name",
                description="Updated description",
            )

        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()
        self.assertIsNotNone(result)

    @patch("db.team_info_crud.get_team_info")
    def test_update_team_info_not_found(self, mock_get):
        """Test updating a non-existent team."""
        mock_get.return_value = None

        result = update_team_info(self.mock_db, team_id="nonexistent", name="New Name")

        self.assertIsNone(result)
        self.mock_db.commit.assert_not_called()

    @patch("db.team_info_crud.get_team_info")
    def test_soft_delete_team_info_found(self, mock_get):
        """Test soft deleting a team."""
        mock_get.return_value = self.mock_team
        self.mock_db.query.return_value.filter.return_value.update = MagicMock()

        with patch("db.team_info_crud.logging"):
            result = soft_delete_team_info(self.mock_db, "test-team")

        self.assertTrue(result)
        self.mock_db.commit.assert_called_once()

    @patch("db.team_info_crud.get_team_info")
    def test_soft_delete_team_info_not_found(self, mock_get):
        """Test soft deleting a non-existent team."""
        mock_get.return_value = None

        result = soft_delete_team_info(self.mock_db, "nonexistent")

        self.assertFalse(result)

    def test_team_info_exists_true(self):
        """Test checking if a team exists."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_team

        result = team_info_exists(self.mock_db, "test-team")

        self.assertTrue(result)

    def test_team_info_exists_false(self):
        """Test checking if a non-existent team exists."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = None

        result = team_info_exists(self.mock_db, "nonexistent")

        self.assertFalse(result)

    def test_delete_team_info_found(self):
        """Test hard deleting a team."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_team
        self.mock_db.query.return_value.filter.return_value.delete = MagicMock()

        with patch("db.team_info_crud.logging"):
            result = delete_team_info(self.mock_db, "test-team")

        self.assertTrue(result)
        self.mock_db.delete.assert_called_once()
        self.mock_db.commit.assert_called_once()

    def test_delete_team_info_not_found(self):
        """Test hard deleting a non-existent team."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("db.team_info_crud.logging"):
            result = delete_team_info(self.mock_db, "nonexistent")

        self.assertFalse(result)

    def test_delete_team_info_error(self):
        """Test hard deleting a team with error."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_team
        self.mock_db.delete.side_effect = Exception("Database error")

        with patch("db.team_info_crud.logging"):
            with self.assertRaises(Exception):
                delete_team_info(self.mock_db, "test-team")

        self.mock_db.rollback.assert_called_once()


class TestTeamAgentCRUD(unittest.TestCase):
    """Tests for TeamAgent CRUD operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock()

        self.mock_team_agent = MagicMock(spec=TeamAgentDB)
        self.mock_team_agent.team_id = "test-team"
        self.mock_team_agent.agent_id = "test-agent"
        self.mock_team_agent.role = "assistant"
        self.mock_team_agent.order_index = 0
        self.mock_team_agent.is_active = True

    def test_add_agent_to_team_success(self):
        """Test adding an agent to a team."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("db.team_info_crud.logging"):
            result = add_agent_to_team(
                self.mock_db,
                team_id="test-team",
                agent_id="new-agent",
                role="assistant",
                order_index=1,
            )

        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.assertIsNotNone(result)

    def test_add_agent_to_team_already_exists(self):
        """Test adding an agent that already exists in team."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_team_agent

        with self.assertRaises(ValueError) as context:
            add_agent_to_team(
                self.mock_db,
                team_id="test-team",
                agent_id="test-agent",
            )

        self.assertIn("already in team", str(context.exception))

    def test_remove_agent_from_team_found(self):
        """Test removing an agent from a team."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_team_agent

        with patch("db.team_info_crud.logging"):
            result = remove_agent_from_team(self.mock_db, "test-team", "test-agent")

        self.assertTrue(result)
        self.mock_db.commit.assert_called_once()

    def test_remove_agent_from_team_not_found(self):
        """Test removing an agent that doesn't exist in team."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = None

        result = remove_agent_from_team(self.mock_db, "test-team", "nonexistent")

        self.assertFalse(result)

    def test_get_team_agents(self):
        """Test getting all agents in a team."""
        mock_agent_2 = MagicMock(spec=TeamAgentDB)
        mock_agent_2.agent_id = "agent-2"

        self.mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            self.mock_team_agent,
            mock_agent_2,
        ]

        result = get_team_agents(self.mock_db, "test-team")

        self.assertEqual(len(result), 2)

    def test_get_agent_teams(self):
        """Test getting all teams an agent belongs to."""
        self.mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            self.mock_team_agent,
        ]

        result = get_agent_teams(self.mock_db, "test-agent")

        self.assertEqual(len(result), 1)

    def test_update_team_agent_role_found(self):
        """Test updating an agent's role in a team."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_team_agent

        with patch("db.team_info_crud.logging"):
            result = update_team_agent_role(
                self.mock_db,
                team_id="test-team",
                agent_id="test-agent",
                role="lead",
                order_index=0,
            )

        self.mock_db.commit.assert_called_once()
        self.assertIsNotNone(result)

    def test_update_team_agent_role_not_found(self):
        """Test updating a non-existent team-agent relationship."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = None

        result = update_team_agent_role(
            self.mock_db,
            team_id="test-team",
            agent_id="nonexistent",
            role="lead",
        )

        self.assertIsNone(result)

    @patch("db.team_info_crud.get_team_info")
    @patch("db.team_info_crud.get_team_agents")
    def test_get_team_with_agents_found(self, mock_get_agents, mock_get_team):
        """Test getting team with all its agents."""
        mock_team = MagicMock(spec=TeamInfoDB)
        mock_team.id = "test-team"
        mock_get_team.return_value = mock_team
        mock_get_agents.return_value = [self.mock_team_agent]

        result = get_team_with_agents(self.mock_db, "test-team")

        self.assertIsNotNone(result)
        assert result is not None  # for mypy
        self.assertIn("team", result)
        self.assertIn("agents", result)
        self.assertEqual(len(result["agents"]), 1)

    @patch("db.team_info_crud.get_team_info")
    def test_get_team_with_agents_not_found(self, mock_get_team):
        """Test getting a non-existent team with agents."""
        mock_get_team.return_value = None

        result = get_team_with_agents(self.mock_db, "nonexistent")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
