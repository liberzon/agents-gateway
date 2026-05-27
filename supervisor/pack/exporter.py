import logging
import os
from typing import Any

import yaml  # type: ignore[import-untyped]

from supervisor.pack.schema import AgentDefinition, PackManifest, TeamConfig

logger = logging.getLogger(__name__)


class PackExporter:
    """Exports an existing supervisor team as an agent pack directory."""

    async def export(self, team_id: str, api_client: Any, output_dir: str) -> str:
        """Read team config from API and write pack directory.

        Args:
            team_id: Team ID to export
            api_client: HTTP client for API calls
            output_dir: Directory to write the pack to

        Returns:
            Path to the created pack directory
        """
        os.makedirs(output_dir, exist_ok=True)
        prompts_dir = os.path.join(output_dir, "prompts")
        os.makedirs(prompts_dir, exist_ok=True)

        # Fetch team info
        team_info = await api_client.get_team(team_id)
        team_agents = await api_client.get_team_members(team_id)

        agents = []
        for ta in team_agents:
            agent_info = await api_client.get_agent(ta["agent_id"])
            prompt_info = await api_client.get_prompt(agent_info.get("prompt_service_id", ""))

            # Write prompt file
            prompt_filename = f"{ta['agent_id']}.txt"
            prompt_path = os.path.join(prompts_dir, prompt_filename)
            with open(prompt_path, "w") as f:
                f.write(prompt_info.get("template", ""))

            # Parse config
            config = agent_info.get("config", {})
            worker_config = config.get("worker_config") if isinstance(config, dict) else None

            agents.append(
                AgentDefinition(
                    id=ta["agent_id"],
                    name=agent_info.get("name", ta["agent_id"]),
                    prompt_file=f"prompts/{prompt_filename}",
                    role=ta.get("role", "worker"),
                    order_index=ta.get("order_index", 0),
                    worker_config=worker_config,
                )
            )

        manifest = PackManifest(
            name=team_info.get("name", team_id),
            description=team_info.get("description", ""),
            agents=agents,
            team=TeamConfig(
                id=team_id,
                name=team_info.get("name", team_id),
                mode=team_info.get("mode", "supervisor"),
            ),
        )

        # Write pack.yaml
        manifest_path = os.path.join(output_dir, "pack.yaml")
        with open(manifest_path, "w") as f:
            yaml.dump(manifest.model_dump(), f, default_flow_style=False, sort_keys=False)

        logger.info(f"Exported pack to {output_dir}")
        return output_dir
