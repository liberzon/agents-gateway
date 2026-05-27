"""
Unit tests for AgentConfig model.
"""

import json
import unittest

from db.agent_info_crud import AgentConfig, get_agent_config
from db.db_models import AgentInfoDB


class TestAgentConfig(unittest.TestCase):
    """Test AgentConfig Pydantic model."""

    def test_agent_config_defaults(self):
        """Default config has memory+history enabled, reasoning disabled."""
        config = AgentConfig()

        # Memory enabled by default
        self.assertTrue(config.enable_memory)

        # History enabled by default
        self.assertTrue(config.enable_history)
        self.assertEqual(config.num_history_runs, 3)

        # Reasoning disabled by default
        self.assertFalse(config.enable_reasoning)
        self.assertEqual(config.reasoning_min_steps, 1)
        self.assertEqual(config.reasoning_max_steps, 10)

    def test_agent_config_from_json(self):
        """Parse config from JSON string."""
        json_str = json.dumps(
            {
                "enable_memory": False,
                "enable_history": True,
                "num_history_runs": 5,
                "enable_reasoning": True,
                "reasoning_min_steps": 2,
                "reasoning_max_steps": 15,
            }
        )

        config = AgentConfig.model_validate_json(json_str)

        self.assertFalse(config.enable_memory)
        self.assertTrue(config.enable_history)
        self.assertEqual(config.num_history_runs, 5)
        self.assertTrue(config.enable_reasoning)
        self.assertEqual(config.reasoning_min_steps, 2)
        self.assertEqual(config.reasoning_max_steps, 15)

    def test_agent_config_to_json(self):
        """Serialize config to JSON string."""
        config = AgentConfig(
            enable_memory=False,
            enable_history=False,
            num_history_runs=10,
            enable_reasoning=True,
            reasoning_min_steps=3,
            reasoning_max_steps=20,
        )

        json_str = config.model_dump_json()
        parsed = json.loads(json_str)

        self.assertFalse(parsed["enable_memory"])
        self.assertFalse(parsed["enable_history"])
        self.assertEqual(parsed["num_history_runs"], 10)
        self.assertTrue(parsed["enable_reasoning"])
        self.assertEqual(parsed["reasoning_min_steps"], 3)
        self.assertEqual(parsed["reasoning_max_steps"], 20)

    def test_agent_config_partial_override(self):
        """Partial config uses defaults for missing fields."""
        json_str = json.dumps(
            {
                "enable_memory": False,
                "enable_reasoning": True,
            }
        )

        config = AgentConfig.model_validate_json(json_str)

        # Overridden fields
        self.assertFalse(config.enable_memory)
        self.assertTrue(config.enable_reasoning)

        # Default fields (not specified)
        self.assertTrue(config.enable_history)
        self.assertEqual(config.num_history_runs, 3)
        self.assertEqual(config.reasoning_min_steps, 1)
        self.assertEqual(config.reasoning_max_steps, 10)

    def test_agent_config_all_disabled(self):
        """Test config with all features disabled."""
        config = AgentConfig(
            enable_memory=False,
            enable_history=False,
            enable_reasoning=False,
        )

        self.assertFalse(config.enable_memory)
        self.assertFalse(config.enable_history)
        self.assertFalse(config.enable_reasoning)

    def test_agent_config_all_enabled(self):
        """Test config with all features enabled."""
        config = AgentConfig(
            enable_memory=True,
            enable_history=True,
            num_history_runs=10,
            enable_reasoning=True,
            reasoning_min_steps=5,
            reasoning_max_steps=25,
        )

        self.assertTrue(config.enable_memory)
        self.assertTrue(config.enable_history)
        self.assertEqual(config.num_history_runs, 10)
        self.assertTrue(config.enable_reasoning)
        self.assertEqual(config.reasoning_min_steps, 5)
        self.assertEqual(config.reasoning_max_steps, 25)


class TestGetAgentConfig(unittest.TestCase):
    """Test get_agent_config helper function."""

    def test_get_agent_config_with_valid_json(self):
        """Parse config from AgentInfoDB with valid JSON."""
        agent_info = AgentInfoDB(
            id="test-agent",
            name="Test Agent",
            prompt_service_id="test-prompt",
            config=json.dumps(
                {
                    "enable_memory": False,
                    "enable_history": True,
                    "num_history_runs": 7,
                    "enable_reasoning": True,
                    "reasoning_min_steps": 2,
                    "reasoning_max_steps": 12,
                }
            ),
        )

        config = get_agent_config(agent_info)

        self.assertFalse(config.enable_memory)
        self.assertTrue(config.enable_history)
        self.assertEqual(config.num_history_runs, 7)
        self.assertTrue(config.enable_reasoning)
        self.assertEqual(config.reasoning_min_steps, 2)
        self.assertEqual(config.reasoning_max_steps, 12)

    def test_get_agent_config_with_null_config(self):
        """Return defaults when config is None."""
        agent_info = AgentInfoDB(
            id="test-agent",
            name="Test Agent",
            prompt_service_id="test-prompt",
            config=None,
        )

        config = get_agent_config(agent_info)

        # Should return defaults
        self.assertTrue(config.enable_memory)
        self.assertTrue(config.enable_history)
        self.assertEqual(config.num_history_runs, 3)
        self.assertFalse(config.enable_reasoning)
        self.assertEqual(config.reasoning_min_steps, 1)
        self.assertEqual(config.reasoning_max_steps, 10)

    def test_get_agent_config_with_empty_string(self):
        """Return defaults when config is empty string."""
        agent_info = AgentInfoDB(
            id="test-agent",
            name="Test Agent",
            prompt_service_id="test-prompt",
            config="",
        )

        config = get_agent_config(agent_info)

        # Should return defaults (empty string is falsy)
        self.assertTrue(config.enable_memory)
        self.assertTrue(config.enable_history)
        self.assertFalse(config.enable_reasoning)

    def test_get_agent_config_with_invalid_json(self):
        """Return defaults when config is invalid JSON."""
        agent_info = AgentInfoDB(
            id="test-agent",
            name="Test Agent",
            prompt_service_id="test-prompt",
            config="not valid json {{{",
        )

        config = get_agent_config(agent_info)

        # Should return defaults
        self.assertTrue(config.enable_memory)
        self.assertTrue(config.enable_history)
        self.assertFalse(config.enable_reasoning)

    def test_get_agent_config_with_partial_json(self):
        """Use defaults for missing fields in partial JSON."""
        agent_info = AgentInfoDB(
            id="test-agent",
            name="Test Agent",
            prompt_service_id="test-prompt",
            config=json.dumps({"enable_memory": False}),
        )

        config = get_agent_config(agent_info)

        # Overridden
        self.assertFalse(config.enable_memory)

        # Defaults
        self.assertTrue(config.enable_history)
        self.assertEqual(config.num_history_runs, 3)
        self.assertFalse(config.enable_reasoning)


if __name__ == "__main__":
    unittest.main()
