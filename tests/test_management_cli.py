"""Tests for the supervisor management CLI (supervisor/__main__.py)."""

import argparse
import asyncio
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import yaml  # type: ignore[import-untyped]

from supervisor.__main__ import APIClient, cmd_load_pack, cmd_validate_pack
from supervisor.pack.exporter import PackExporter
from supervisor.pack.loader import PackLoader
from supervisor.pack.schema import AgentDefinition, PackManifest


def _create_valid_pack(tmpdir: str) -> str:
    """Create a valid pack directory for testing."""
    prompts_dir = os.path.join(tmpdir, "prompts")
    os.makedirs(prompts_dir, exist_ok=True)

    # Write prompt files
    with open(os.path.join(prompts_dir, "leader.txt"), "w") as f:
        f.write("You are the leader agent. Classify and route tasks.")
    with open(os.path.join(prompts_dir, "worker-coding.txt"), "w") as f:
        f.write("You are a coding worker. Write code to solve the task.")

    # Write pack.yaml
    manifest = {
        "name": "test-pack",
        "version": "1.0",
        "description": "Test pack",
        "agents": [
            {
                "id": "leader",
                "name": "Leader Agent",
                "prompt_file": "prompts/leader.txt",
                "role": "leader",
                "order_index": 0,
            },
            {
                "id": "worker-coding",
                "name": "Coding Worker",
                "prompt_file": "prompts/worker-coding.txt",
                "role": "worker",
                "order_index": 1,
                "worker_config": {
                    "mcp_servers": [
                        {"name": "git", "type": "stdio", "command": "npx", "args": ["-y", "@anthropic/mcp-git"]}
                    ]
                },
            },
        ],
        "extensions": [],
        "team": {
            "id": "test-team",
            "name": "Test Team",
            "mode": "supervisor",
        },
    }

    with open(os.path.join(tmpdir, "pack.yaml"), "w") as f:
        yaml.dump(manifest, f)

    return tmpdir


# ---------------------------------------------------------------------------
# PackManifest parsing
# ---------------------------------------------------------------------------


class TestPackManifestParsing(unittest.TestCase):
    """Test PackManifest parsing from YAML."""

    def test_parse_valid_manifest(self) -> None:
        """Parse a well-formed pack.yaml into PackManifest."""
        data = {
            "name": "my-pack",
            "version": "2.0",
            "description": "A test pack",
            "agents": [
                {"id": "leader", "name": "Leader", "prompt_file": "prompts/leader.txt", "role": "leader"},
                {
                    "id": "worker-code",
                    "name": "Coder",
                    "prompt_file": "prompts/coder.txt",
                    "role": "worker",
                    "worker_config": {"mcp_servers": []},
                },
            ],
            "extensions": [
                {"id": "ext-data", "name": "Data Extension", "prompt_file": "prompts/ext.txt", "domain_tags": ["data"]},
            ],
            "team": {"id": "pack-team", "name": "Pack Team", "mode": "supervisor"},
        }

        manifest = PackManifest(**data)  # type: ignore[arg-type]
        self.assertEqual(manifest.name, "my-pack")
        self.assertEqual(manifest.version, "2.0")
        self.assertEqual(len(manifest.agents), 2)
        self.assertEqual(len(manifest.extensions), 1)
        self.assertEqual(manifest.team.mode, "supervisor")

    def test_agent_definition_with_worker_config(self) -> None:
        """AgentDefinition parses worker_config correctly."""
        agent = AgentDefinition(
            id="worker-infra",
            name="Infra Worker",
            prompt_file="prompts/infra.txt",
            role="worker",
            worker_config={
                "mcp_servers": [{"name": "aws", "type": "http", "url": "https://aws.mcp/"}],
                "allowed_commands": ["terraform plan"],
            },
        )
        self.assertIsNotNone(agent.worker_config)
        self.assertEqual(agent.worker_config["mcp_servers"][0]["name"], "aws")  # type: ignore[index]

    def test_manifest_defaults(self) -> None:
        """PackManifest has sensible defaults."""
        manifest = PackManifest(name="minimal")
        self.assertEqual(manifest.version, "1.0")
        self.assertEqual(manifest.default_engine, "claude_code")
        self.assertEqual(manifest.default_target, "linux-pool")
        self.assertEqual(manifest.team.mode, "supervisor")


# ---------------------------------------------------------------------------
# validate-pack
# ---------------------------------------------------------------------------


class TestValidatePack(unittest.TestCase):
    """Test validate-pack command."""

    def test_validate_valid_pack(self) -> None:
        """validate-pack succeeds on a valid pack."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_valid_pack(tmpdir)

            loader = PackLoader()
            errors = loader.validate(tmpdir)
            self.assertEqual(errors, [])

    def test_validate_missing_prompt_file(self) -> None:
        """validate-pack reports missing prompt file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_valid_pack(tmpdir)
            # Remove the worker prompt file
            os.remove(os.path.join(tmpdir, "prompts", "worker-coding.txt"))

            loader = PackLoader()
            errors = loader.validate(tmpdir)
            self.assertTrue(len(errors) > 0)
            self.assertTrue(any("Missing prompt file" in e for e in errors))

    def test_validate_missing_pack_yaml(self) -> None:
        """validate-pack reports missing pack.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = PackLoader()
            errors = loader.validate(tmpdir)
            self.assertEqual(errors, ["pack.yaml not found"])

    def test_validate_no_leader(self) -> None:
        """validate-pack reports error when no leader agent defined."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = os.path.join(tmpdir, "prompts")
            os.makedirs(prompts_dir)
            with open(os.path.join(prompts_dir, "worker.txt"), "w") as f:
                f.write("Worker prompt")

            manifest = {
                "name": "no-leader-pack",
                "agents": [
                    {"id": "worker", "name": "Worker", "prompt_file": "prompts/worker.txt", "role": "worker"},
                ],
                "team": {"id": "team", "name": "Team"},
            }
            with open(os.path.join(tmpdir, "pack.yaml"), "w") as f:
                yaml.dump(manifest, f)

            loader = PackLoader()
            errors = loader.validate(tmpdir)
            self.assertTrue(any("No agent with role='leader'" in e for e in errors))

    def test_cmd_validate_pack_valid(self) -> None:
        """cmd_validate_pack exits cleanly on valid pack."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_valid_pack(tmpdir)
            args = argparse.Namespace(pack_dir=tmpdir)
            # Should not raise or call sys.exit(1)
            cmd_validate_pack(args)

    def test_cmd_validate_pack_invalid(self) -> None:
        """cmd_validate_pack exits with error on invalid pack."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Empty directory — missing pack.yaml
            args = argparse.Namespace(pack_dir=tmpdir)
            with self.assertRaises(SystemExit) as ctx:
                cmd_validate_pack(args)
            self.assertEqual(ctx.exception.code, 1)


# ---------------------------------------------------------------------------
# load-pack
# ---------------------------------------------------------------------------


class TestLoadPack(unittest.TestCase):
    """Test load-pack command (with mocked API)."""

    @patch.object(PackLoader, "apply", new_callable=AsyncMock)
    def test_load_pack_creates_resources(self, mock_apply: AsyncMock) -> None:
        """load-pack creates prompts, agents, and team via API."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_valid_pack(tmpdir)

            mock_apply.return_value = {
                "prompts": ["prompt-leader", "prompt-worker-coding"],
                "agents": ["leader", "worker-coding"],
                "team": "test-team",
            }

            args = argparse.Namespace(
                pack_dir=tmpdir,
                api_url="http://localhost:8000",
                api_key="test-key",
            )
            cmd_load_pack(args)

            mock_apply.assert_called_once()


class TestPackLoaderApply(unittest.TestCase):
    """Test PackLoader.apply method."""

    def test_apply_calls_api_client(self) -> None:
        """PackLoader.apply creates prompts, agents, and team via the API client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_valid_pack(tmpdir)

            loader = PackLoader()
            manifest = loader.load(tmpdir)

            mock_client = MagicMock()
            mock_client.create_or_update_prompt = AsyncMock()
            mock_client.create_or_update_agent = AsyncMock()
            mock_client.create_or_update_team = AsyncMock()

            results = asyncio.run(loader.apply(tmpdir, manifest, mock_client))

            # Should have created prompts for 2 agents
            self.assertEqual(len(results["prompts"]), 2)
            # Should have created 2 agents
            self.assertEqual(len(results["agents"]), 2)
            # Should have created 1 team
            self.assertEqual(results["team"], "test-team")

            mock_client.create_or_update_prompt.assert_called()
            mock_client.create_or_update_agent.assert_called()
            mock_client.create_or_update_team.assert_called_once()


# ---------------------------------------------------------------------------
# list-workers (mocked API)
# ---------------------------------------------------------------------------


class TestListWorkers(unittest.TestCase):
    """Test list-workers command."""

    @patch("supervisor.__main__.httpx.AsyncClient")
    def test_list_workers_calls_api(self, mock_client_class: MagicMock) -> None:
        """list-workers fetches agents from the API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "worker-coding", "name": "Coder", "tags": '["role:worker"]'},
            {"id": "leader", "name": "Leader", "tags": '["role:leader"]'},
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        from supervisor.__main__ import cmd_list_workers

        args = argparse.Namespace(api_url="http://localhost:8000", api_key="key123")
        cmd_list_workers(args)


# ---------------------------------------------------------------------------
# PackExporter
# ---------------------------------------------------------------------------


class TestPackExporter(unittest.TestCase):
    """Test PackExporter writes correct directory structure."""

    def test_export_creates_pack_directory(self) -> None:
        """PackExporter writes pack.yaml and prompt files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "exported")

            mock_client = MagicMock()
            mock_client.get_team = AsyncMock(
                return_value={"name": "Export Team", "description": "Team desc", "mode": "supervisor"}
            )
            mock_client.get_team_members = AsyncMock(
                return_value=[
                    {"agent_id": "leader", "role": "leader", "order_index": 0},
                    {"agent_id": "worker-code", "role": "worker", "order_index": 1},
                ]
            )
            mock_client.get_agent = AsyncMock(
                side_effect=lambda aid: {
                    "name": aid.replace("-", " ").title(),
                    "prompt_service_id": f"prompt-{aid}",
                    "config": {},
                }
            )
            mock_client.get_prompt = AsyncMock(side_effect=lambda pid: {"template": f"Prompt template for {pid}"})

            exporter = PackExporter()
            result_dir = asyncio.run(exporter.export("test-team", mock_client, output_dir))

            # Verify pack.yaml exists
            self.assertTrue(os.path.exists(os.path.join(result_dir, "pack.yaml")))

            # Verify prompt files exist
            self.assertTrue(os.path.exists(os.path.join(result_dir, "prompts", "leader.txt")))
            self.assertTrue(os.path.exists(os.path.join(result_dir, "prompts", "worker-code.txt")))

            # Verify pack.yaml content
            with open(os.path.join(result_dir, "pack.yaml")) as f:
                data = yaml.safe_load(f)
            self.assertEqual(data["name"], "Export Team")
            self.assertEqual(len(data["agents"]), 2)


# ---------------------------------------------------------------------------
# APIClient tests
# ---------------------------------------------------------------------------


class TestAPIClient(unittest.TestCase):
    """Test the CLI API client."""

    def test_api_client_headers(self) -> None:
        """APIClient sets X-API-Key header when key provided."""
        client = APIClient(base_url="http://localhost:8000", api_key="my-key")
        self.assertEqual(client.headers["X-API-Key"], "my-key")

    def test_api_client_no_key(self) -> None:
        """APIClient has no auth header when no key provided."""
        client = APIClient(base_url="http://localhost:8000")
        self.assertNotIn("X-API-Key", client.headers)

    def test_api_client_base_url_trailing_slash(self) -> None:
        """APIClient strips trailing slash from base URL."""
        client = APIClient(base_url="http://localhost:8000/")
        self.assertEqual(client.base_url, "http://localhost:8000")


if __name__ == "__main__":
    unittest.main()
