"""Management CLI for the supervisor/worker platform.

Usage:
    python -m supervisor load-pack path/to/pack/ --api-url URL --api-key KEY
    python -m supervisor validate-pack path/to/pack/
    python -m supervisor list-workers --api-url URL --api-key KEY
    python -m supervisor job-status JOB_ID --api-url URL --api-key KEY
"""

import argparse
import asyncio
import json
import logging
import sys
from typing import Any, Dict, Optional

import httpx

from supervisor.pack.loader import PackLoader

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class APIClient:
    """Simple HTTP client for the agent-api."""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.headers: Dict[str, str] = {}
        if api_key:
            self.headers["X-API-Key"] = api_key

    async def create_or_update_prompt(self, data: Dict[str, Any]) -> None:
        async with httpx.AsyncClient() as client:
            # Ensure tags is a list, not a JSON string
            if isinstance(data.get("tags"), str):
                data["tags"] = json.loads(data["tags"])
            resp = await client.post(f"{self.base_url}/v2/prompts", json=data, headers=self.headers, timeout=30.0)
            if resp.status_code == 409:
                await client.put(
                    f"{self.base_url}/v2/prompts/{data['id']}", json=data, headers=self.headers, timeout=30.0
                )
            elif resp.status_code >= 400:
                logger.warning(f"Failed to create prompt {data.get('id')}: {resp.status_code} {resp.text}")
            else:
                logger.info(f"Created prompt: {data.get('id')}")

    async def create_or_update_agent(self, data: Dict[str, Any]) -> None:
        async with httpx.AsyncClient() as client:
            # Ensure tags is a list
            if isinstance(data.get("tags"), str):
                data["tags"] = json.loads(data["tags"])
            # Ensure config is a dict object, not a string
            if isinstance(data.get("config"), str):
                data["config"] = json.loads(data["config"])
            resp = await client.post(f"{self.base_url}/v2/agents", json=data, headers=self.headers, timeout=30.0)
            if resp.status_code >= 400:
                logger.warning(f"Failed to create agent {data.get('id')}: {resp.status_code} {resp.text}")
            else:
                logger.info(f"Created agent: {data.get('id')}")

    async def create_or_update_team(self, data: Dict[str, Any]) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/v2/teams", json=data, headers=self.headers, timeout=30.0)
            if resp.status_code >= 400:
                logger.warning(f"Failed to create team {data.get('id')}: {resp.status_code} {resp.text}")
            else:
                logger.info(f"Created team: {data.get('id')}")

    async def get_team(self, team_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/v2/teams/{team_id}", headers=self.headers, timeout=30.0)
            resp.raise_for_status()
            return resp.json()

    async def get_team_members(self, team_id: str) -> list:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/v2/teams/{team_id}/members", headers=self.headers, timeout=30.0)
            resp.raise_for_status()
            return resp.json()

    async def get_agent(self, agent_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/v2/agents/{agent_id}", headers=self.headers, timeout=30.0)
            resp.raise_for_status()
            return resp.json()

    async def get_prompt(self, prompt_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/v2/prompts/{prompt_id}", headers=self.headers, timeout=30.0)
            resp.raise_for_status()
            return resp.json()


def cmd_load_pack(args: argparse.Namespace) -> None:
    loader = PackLoader()
    manifest = loader.load(args.pack_dir)
    logger.info(f"Loaded pack: {manifest.name} v{manifest.version}")
    logger.info(f"  Agents: {len(manifest.agents)}")
    logger.info(f"  Extensions: {len(manifest.extensions)}")
    logger.info(f"  Team: {manifest.team.id}")

    client = APIClient(args.api_url, args.api_key)
    results = asyncio.run(loader.apply(args.pack_dir, manifest, client))

    logger.info("Applied pack:")
    logger.info(f"  Prompts created: {len(results['prompts'])}")
    logger.info(f"  Agents created: {len(results['agents'])}")
    logger.info(f"  Team: {results['team']}")


def cmd_validate_pack(args: argparse.Namespace) -> None:
    loader = PackLoader()
    errors = loader.validate(args.pack_dir)
    if errors:
        for e in errors:
            logger.error(f"  {e}")
        sys.exit(1)
    else:
        logger.info("Pack is valid")


def cmd_list_workers(args: argparse.Namespace) -> None:
    async def _list() -> None:
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": args.api_key} if args.api_key else {}
            resp = await client.get(f"{args.api_url}/v2/agents", headers=headers, timeout=30.0)
            resp.raise_for_status()
            agents = resp.json()
            for agent in agents:
                tags = agent.get("tags", [])
                if isinstance(tags, str):
                    tags = json.loads(tags) if tags else []
                role_tags = [t for t in tags if t.startswith("role:")]
                print(f"  {agent['id']:30s} {agent.get('name', ''):30s} {', '.join(role_tags)}")

    asyncio.run(_list())


def cmd_job_status(args: argparse.Namespace) -> None:
    print(f"Job status check for {args.job_id} (endpoint not yet available)")


def main() -> None:
    parser = argparse.ArgumentParser(prog="supervisor", description="Supervisor/Worker Platform CLI")
    subparsers = parser.add_subparsers(dest="command")

    # load-pack
    p_load = subparsers.add_parser("load-pack", help="Load an agent pack via API")
    p_load.add_argument("pack_dir", help="Path to the agent pack directory")
    p_load.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    p_load.add_argument("--api-key", default=None, help="API key")

    # validate-pack
    p_validate = subparsers.add_parser("validate-pack", help="Validate an agent pack")
    p_validate.add_argument("pack_dir", help="Path to the agent pack directory")

    # list-workers
    p_list = subparsers.add_parser("list-workers", help="List registered worker agents")
    p_list.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    p_list.add_argument("--api-key", default=None, help="API key")

    # job-status
    p_job = subparsers.add_parser("job-status", help="Check execution job status")
    p_job.add_argument("job_id", help="Job ID")
    p_job.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    p_job.add_argument("--api-key", default=None, help="API key")

    args = parser.parse_args()

    if args.command == "load-pack":
        cmd_load_pack(args)
    elif args.command == "validate-pack":
        cmd_validate_pack(args)
    elif args.command == "list-workers":
        cmd_list_workers(args)
    elif args.command == "job-status":
        cmd_job_status(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
