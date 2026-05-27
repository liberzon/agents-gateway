"""
Agent selector module with caching capabilities.

This module provides functions to get available agents and retrieve specific agents.
It implements caching for prompts service access to improve performance.
"""

import logging
import os
from typing import Callable, List, Optional

from sqlalchemy.orm import Session

from agents import Model
from agents.agent import get_agent as get_agent_impl
from api.services.models import PullPromptResponse
from api.services.prompts_client import prompts_client
from api.settings import api_settings
from db.agent_info_crud import get_agent_config, get_agent_info, get_all_agent_info
from db.session import get_db


def get_available_agents(db: Optional[Session] = None) -> List[str]:
    """
    Returns a list of all available agent IDs from the database.

    Args:
        db: Database session (optional, will create one if not provided)

    Returns:
        List[str]: Sorted list of agent IDs
    """
    # Fetch from database
    close_db = False
    if db is None:
        db = next(get_db())
        close_db = True

    try:
        agents = get_all_agent_info(db)
        agent_ids = [agent.id for agent in agents]
        return sorted(agent_ids)  # type: ignore[arg-type]
    finally:
        if close_db:
            db.close()


def get_agent(
    model_id: str = Model.gemini_2_5_pro,
    agent_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    organizer_email: str = "default@example.com",
    tenant_id: str = "default_tenant",
    debug_mode: Optional[bool] = None,
    fetch_token_func: Optional[Callable[[str, str], Optional[str]]] = None,
    db: Optional[Session] = None,
):
    """
    Get an agent by ID, fetching its prompt from the prompts service.
    Prompts are cached for improved performance.

    Args:
        model_id: The model ID to use
        agent_id: The agent ID to get
        user_id: Optional user ID
        session_id: Optional session ID
        organizer_email: Organizer email for calendar operations
        tenant_id: Tenant ID for knowledge base integration
        debug_mode: Whether to enable debug mode (defaults to environment setting)
        fetch_token_func: Optional function to fetch access tokens
        db: Database session (optional, will create one if not provided)

    Returns:
        Agent: The agent instance

    Raises:
        ValueError: If the agent is not found or the prompt is not found
    """
    close_db = False
    if db is None:
        db = next(get_db())
        close_db = True

    try:
        # Check if agent exists in database
        available_agents = get_available_agents(db)
        if agent_id not in available_agents:
            raise ValueError(f"Agent: {agent_id} not found in database")

        # Get agent info directly from database (no caching)
        agent_info = get_agent_info(db, agent_id)
        if not agent_info:
            raise ValueError(f"Agent: {agent_id} not found in database")

        # Get prompt — try cache/service first, fall back to local postgres storage
        prompt_service_id = agent_info.prompt_service_id
        # Use local postgres storage directly when that's the configured backend,
        # or fall back to prompts service client + local storage
        prompt = None
        if os.environ.get("PROMPT_STORAGE_BACKEND", "postgres").lower() == "postgres":
            prompt = _get_prompt_from_local_storage(db, str(prompt_service_id))
        else:
            prompt = prompts_client.get_prompt(prompt_service_id)  # type: ignore[arg-type]
            if not prompt:
                prompt = _get_prompt_from_local_storage(db, str(prompt_service_id))
        if not prompt:
            raise ValueError(f"Prompt: {prompt_service_id} not found")
        logging.info(f"Prompt loaded for {agent_id}: {len(prompt.template)} chars")

        # Use environment-based debug mode if not explicitly provided
        if debug_mode is None:
            debug_mode = api_settings.agent_debug_mode

        # Get config from database
        agent_config = get_agent_config(agent_info)
        logging.info(f"Creating agent impl for {agent_id}...")

        # Create and return agent
        return get_agent_impl(
            prompt=prompt,
            user_id=user_id or "default_user",
            session_id=session_id or "default_session",
            organizer_email=organizer_email,
            tenant_id=tenant_id,
            model_id=model_id,
            debug_mode=debug_mode,
            fetch_token_func=fetch_token_func,
            config=agent_config,
        )
    finally:
        if close_db:
            db.close()


def _get_prompt_from_local_storage(db: Session, prompt_service_id: str) -> Optional[PullPromptResponse]:
    """Fallback: load prompt from local postgres storage when external service is unavailable."""
    try:
        from prompts.storage import get_prompt_storage

        storage = get_prompt_storage(db)
        prompt_db = storage.get(prompt_service_id)
        if prompt_db:
            import json

            tags = None
            if prompt_db.tags:
                try:
                    tags = json.loads(prompt_db.tags) if isinstance(prompt_db.tags, str) else prompt_db.tags
                except (json.JSONDecodeError, TypeError):
                    tags = None
            return PullPromptResponse(
                name=prompt_db.name,
                template=prompt_db.template,
                description=prompt_db.description,
                tags=tags,
            )
    except Exception as e:
        logging.warning(f"Failed to load prompt '{prompt_service_id}' from local storage: {e}")
    return None
