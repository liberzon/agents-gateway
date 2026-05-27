import logging
import os
from typing import Any, Dict, List, Optional

import yaml  # type: ignore[import-untyped]

from supervisor.pack.schema import PackManifest

logger = logging.getLogger(__name__)


class PackLoader:
    """Loads agent packs from a directory and applies them via API."""

    def load(self, pack_dir: str) -> PackManifest:
        """Read and validate a pack directory."""
        manifest_path = os.path.join(pack_dir, "pack.yaml")
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Pack manifest not found: {manifest_path}")

        with open(manifest_path) as f:
            data = yaml.safe_load(f)

        manifest = PackManifest(**data)

        # Validate that all referenced prompt files exist
        errors = self.validate(pack_dir, manifest)
        if errors:
            raise ValueError(f"Pack validation errors: {errors}")

        return manifest

    def validate(self, pack_dir: str, manifest: Optional[PackManifest] = None) -> List[str]:
        """Validate pack structure. Returns list of errors."""
        errors: List[str] = []

        if manifest is None:
            manifest_path = os.path.join(pack_dir, "pack.yaml")
            if not os.path.exists(manifest_path):
                return ["pack.yaml not found"]
            with open(manifest_path) as f:
                data = yaml.safe_load(f)
            manifest = PackManifest(**data)

        # Check prompt files exist
        for agent in manifest.agents:
            prompt_path = os.path.join(pack_dir, agent.prompt_file)
            if not os.path.exists(prompt_path):
                errors.append(f"Missing prompt file for agent {agent.id}: {agent.prompt_file}")

        for ext in manifest.extensions:
            prompt_path = os.path.join(pack_dir, ext.prompt_file)
            if not os.path.exists(prompt_path):
                errors.append(f"Missing prompt file for extension {ext.id}: {ext.prompt_file}")

        # Check at least one leader
        leaders = [a for a in manifest.agents if a.role == "leader"]
        if not leaders:
            errors.append("No agent with role='leader' defined")

        return errors

    def read_prompt_file(self, pack_dir: str, relative_path: str) -> str:
        """Read a prompt text file from the pack directory."""
        full_path = os.path.join(pack_dir, relative_path)
        with open(full_path) as f:
            return f.read()

    async def apply(self, pack_dir: str, manifest: PackManifest, api_client: Any) -> Dict[str, Any]:
        """Apply a pack by creating/updating resources via API client.

        Args:
            pack_dir: Path to the pack directory
            manifest: Parsed pack manifest
            api_client: HTTP client with methods for API calls

        Returns:
            Summary of created/updated resources
        """
        results: Dict[str, Any] = {"prompts": [], "agents": [], "team": None}

        # Create prompts for agents
        for agent_def in manifest.agents:
            prompt_text = self.read_prompt_file(pack_dir, agent_def.prompt_file)
            prompt_id = f"prompt-{agent_def.id}"
            tags = [f"role:{agent_def.role}"]
            if agent_def.role == "worker":
                worker_type = agent_def.id.replace("worker-", "")
                tags.append(f"worker:{worker_type}")

            prompt_data = {
                "id": prompt_id,
                "name": agent_def.name,
                "template": prompt_text,
                "tags": tags,
            }
            await api_client.create_or_update_prompt(prompt_data)
            results["prompts"].append(prompt_id)

        # Create prompts for extensions
        for ext_def in manifest.extensions:
            prompt_text = self.read_prompt_file(pack_dir, ext_def.prompt_file)
            prompt_id = f"prompt-ext-{ext_def.id}"
            prompt_data = {
                "id": prompt_id,
                "name": ext_def.name,
                "template": prompt_text,
                "tags": ext_def.domain_tags,
            }
            await api_client.create_or_update_prompt(prompt_data)
            results["prompts"].append(prompt_id)

        # Create agents (using template text directly — API requires it)
        for agent_def in manifest.agents:
            prompt_text = self.read_prompt_file(pack_dir, agent_def.prompt_file)
            tags = [f"role:{agent_def.role}"]
            if agent_def.role == "worker":
                worker_type = agent_def.id.replace("worker-", "")
                tags.append(f"worker:{worker_type}")

            config: Dict[str, Any] = {"enable_memory": False, "enable_history": True, "num_history_runs": 3}
            if agent_def.worker_config:
                config["worker_config"] = agent_def.worker_config

            agent_data = {
                "id": agent_def.id,
                "name": agent_def.name,
                "template": prompt_text,
                "tags": tags,
                "config": config,
            }
            await api_client.create_or_update_agent(agent_data)
            results["agents"].append(agent_def.id)

        # Create team
        team_data = {
            "id": manifest.team.id,
            "name": manifest.team.name,
            "mode": manifest.team.mode,
            "agents": [{"agent_id": a.id, "role": a.role, "order_index": a.order_index} for a in manifest.agents],
        }
        await api_client.create_or_update_team(team_data)
        results["team"] = manifest.team.id

        return results
