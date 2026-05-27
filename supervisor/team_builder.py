import logging
from typing import Any, List, Optional

from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.memory import MemoryManager
from agno.team import Team, TeamMode

from agents.model_factory import create_model
from agents.v2_selector import get_agent
from api.services.knowledge_service import get_knowledge_service
from db.agent_info_crud import AgentConfig, get_agent_config, get_agent_info
from db.url import get_db_url
from toolkits.claude_code import ClaudeCodeToolkit
from toolkits.managed_agents import ManagedAgentsToolkit

logger = logging.getLogger(__name__)


def build_supervisor_team(
    team_id: str,
    team_name: str,
    team_agents_db: List[Any],
    db: Any,
    user_id: str,
    session_id: str,
    model_id: str,
    organizer_email: str = "default@example.com",
    tenant_id: str = "default_tenant",
    fetch_token_func: Optional[Any] = None,
    debug_mode: bool = False,
) -> Team:
    """Build a supervisor team with execution engine toolkits wired to workers.

    This function may be called from asyncio.to_thread, so it creates its own DB session
    to avoid cross-thread SQLAlchemy access issues.

    1. Identify leader agent (role="leader")
    2. For each worker: load WorkerConfig, instantiate ClaudeCodeToolkit + ManagedAgentsToolkit
    3. Attach toolkits, compose domain extensions
    4. Create Team(mode=TeamMode.coordinate)
    """
    db_url = get_db_url()

    # Create a fresh DB session for this thread (avoids cross-thread SQLAlchemy issues)
    from db.session import get_db as _get_db

    thread_db = next(_get_db())

    # Sort agents by order_index
    sorted_agents = sorted(team_agents_db, key=lambda x: int(x.order_index) if x.order_index is not None else 999)

    members: List[Agent] = []

    try:
        for team_agent in sorted_agents:
            agent_id = str(team_agent.agent_id)
            role = team_agent.role or "worker"

            logger.info(f"Building agent {agent_id} (role={role})...")
            agent = get_agent(
                model_id=model_id,
                agent_id=agent_id,
                user_id=user_id,
                session_id=session_id,
                organizer_email=organizer_email,
                tenant_id=tenant_id,
                debug_mode=debug_mode,
                fetch_token_func=fetch_token_func,
                db=thread_db,
            )
            logger.info(f"Agent {agent_id} created successfully")

            # For workers (not leader), attach execution engine toolkits
            if role != "leader":
                agent_info = get_agent_info(thread_db, agent_id)
                config = get_agent_config(agent_info) if agent_info else AgentConfig()
                worker_config = config.worker_config

                if worker_config:
                    claude_toolkit = ClaudeCodeToolkit(
                        user_id=user_id,
                        worker_config=worker_config,
                        execution_target_type=_resolve_target_type(worker_config),
                    )
                    managed_toolkit = ManagedAgentsToolkit(
                        user_id=user_id,
                        worker_config=worker_config,
                    )
                    existing_tools = list(agent.tools) if agent.tools else []
                    existing_tools.extend([claude_toolkit, managed_toolkit])
                    agent.tools = existing_tools

            members.append(agent)
    except Exception as e:
        logger.error(f"Failed to build supervisor team: {e}")
        raise
    finally:
        thread_db.close()

    # Create team storage
    db_instance = PostgresDb(
        db_url=db_url,
        session_table=f"t_{team_id}_s",
        memory_table=f"t_{team_id}_m",
    )

    from api.settings import api_settings as _settings

    team_model = create_model(
        model_id,
        gemini_api_key=_settings.gemini_api_key,
        openai_api_key=_settings.openai_api_key,
        anthropic_api_key=_settings.anthropic_api_key,
    )
    memory_model = create_model(
        model_id,
        gemini_api_key=_settings.gemini_api_key,
        openai_api_key=_settings.openai_api_key,
        anthropic_api_key=_settings.anthropic_api_key,
    )

    memory_manager = MemoryManager(
        model=memory_model,
        db=db_instance,
        delete_memories=True,
        clear_memories=True,
    )

    # Team pre-hook: execute member pre-hooks
    def team_pre_hook(**kwargs: Any) -> None:
        team_instance = kwargs.get("team")
        if not team_instance or not hasattr(team_instance, "members") or not team_instance.members:
            return
        for member in team_instance.members:
            if hasattr(member, "pre_hooks") and member.pre_hooks:
                for hook in member.pre_hooks:
                    try:
                        hook(member, None)
                    except Exception as e:
                        logger.error(f"Pre-hook error for {member.name}: {e}")

    return Team(  # type: ignore[call-arg]
        name=team_name,
        id=team_id,
        user_id=user_id,
        session_id=session_id,
        members=members,  # type: ignore[arg-type]
        mode=TeamMode.coordinate,
        model=team_model,
        compress_tool_results=True,
        enable_agentic_state=True,
        add_datetime_to_context=True,
        enable_agentic_memory=True,
        respond_directly=True,
        read_chat_history=True,
        store_history_messages=True,
        num_history_runs=3,
        markdown=True,
        debug_mode=debug_mode,
        show_members_responses=True,
        telemetry=True,
        db=db_instance,
        memory_manager=memory_manager,
        knowledge=get_knowledge_service().get_dynamic_kb(),
        pre_hooks=[team_pre_hook],
    )


def _resolve_target_type(worker_config: Any) -> str:
    """Resolve execution target type from worker config."""
    engine_pref = getattr(worker_config, "execution_engine_preference", None)
    if engine_pref and "managed" in engine_pref:
        return "managed_agents"
    return "local"
