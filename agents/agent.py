import json
import re
import time
from datetime import datetime
from typing import Callable, List, Optional

from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.guardrails import PIIDetectionGuardrail, PromptInjectionGuardrail
from agno.memory import MemoryManager
from agno.skills import Skills
from agno.skills.loaders.base import SkillLoader
from agno.skills.skill import Skill as AgnoSkill
from agno.tools.brightdata import BrightDataTools
from agno.tools.user_control_flow import UserControlFlowTools

from agents import Model
from agents.model_factory import create_model
from agents.toolkit_selector import create_datetime_resolver_tool, create_multi_toolkit_selector
from api.services.knowledge_service import get_knowledge_service
from api.services.models import PullPromptResponse
from api.settings import api_settings
from db.agent_info_crud import AgentConfig
from db.db_models import SkillDB
from db.session import db_url
from toolkits.calendar import CalendarToolkit
from toolkits.contacts import ContactsToolkit
from toolkits.drive import DriveToolkit
from toolkits.email import EmailToolkit
from toolkits.token_cache import TokenCache

# Create module-level token cache instance
token_cache = TokenCache()


class DbSkillLoader(SkillLoader):
    """Load skills from database SkillDB records."""

    def __init__(self, db_skills: List[SkillDB]):
        self._db_skills = db_skills

    def load(self) -> List[AgnoSkill]:
        return [
            AgnoSkill(
                name=s.id,  # type: ignore[arg-type]
                description=s.description or "",  # type: ignore[arg-type]
                instructions=s.instructions,  # type: ignore[arg-type]
                source_path="db",
                scripts=json.loads(s.scripts) if s.scripts else [],  # type: ignore[arg-type]
                references=json.loads(s.references) if s.references else [],  # type: ignore[arg-type]
                allowed_tools=json.loads(s.allowed_tools) if s.allowed_tools else None,  # type: ignore[arg-type]
            )
            for s in self._db_skills
        ]


def extract_agent_id(response: PullPromptResponse) -> Optional[str]:
    agent_id = None

    if response.tags is not None:
        for tag in response.tags:
            if ":" not in tag:
                continue  # Skip malformed tags
            key, value = tag.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            if not key or not value:
                continue  # Skip if key or value is empty

            if key == "agentid":
                agent_id = value

    return agent_id


def extract_available_tools(response: PullPromptResponse) -> set[str]:
    """
    Extract available tools from the 'available_tools' tag.

    Parses tags like "available_tools:calendar,contacts,drive,email,brightdata,user_control_flow"
    and returns a set of enabled tool names.

    Args:
        response: PullPromptResponse containing tags

    Returns:
        Set of tool names to enable. Empty set if no 'available_tools' tag found.

    Examples:
        >>> extract_available_tools(response)  # tag: "available_tools:calendar,contacts"
        {'calendar', 'contacts'}

        >>> extract_available_tools(response)  # no available_tools tag
        set()
    """
    if response.tags is None:
        return set()

    for tag in response.tags:
        if ":" not in tag:
            continue  # Skip malformed tags

        key, value = tag.split(":", 1)
        key = key.strip().lower()
        value = value.strip()

        if not key or not value:
            continue  # Skip if key or value is empty

        if key == "available_tools":
            # Split comma-separated tools and normalize
            tools = {tool.strip().lower() for tool in value.split(",") if tool.strip()}
            return tools

    return set()


def slug_to_table_name(slug: str) -> str:
    """
    Converts a slug (e.g., 'natalie-hayes') into a PostgreSQL-compliant table name.

    Rules:
    - Lowercase only
    - Hyphens and spaces → underscores
    - Only alphanumeric and underscores
    - Cannot start with a digit (prefix with 't_' if so)
    - Max length 63 characters (PostgreSQL limit)
    """
    # Lowercase and replace hyphens/spaces with underscores
    table = re.sub(r"[-\s]+", "_", slug.lower())

    # Remove all characters except letters, digits, and underscores
    table = re.sub(r"[^\w]", "", table)

    # Prefix if it starts with a digit
    if re.match(r"^\d", table):
        table = f"t_{table}"

    # Truncate to 63 characters (PostgreSQL limit)
    return table[:63]


def get_system_timezone() -> str:
    """Return the system's local timezone as an IANA identifier (e.g., 'Asia/Jerusalem')."""
    # First try: Check if datetime.now().astimezone() gives us a ZoneInfo
    local_tz = datetime.now().astimezone().tzinfo
    if local_tz and hasattr(local_tz, "key"):
        return local_tz.key  # type: ignore[return-value]

    # Second try: Use time.tzname to get the system timezone
    # time.tzname gives us (standard_name, dst_name) like ('IST', 'IDT')
    # We need to map this to the IANA identifier
    try:
        # Get the local timezone name from the system
        if time.daylight:
            tz_name = time.tzname[time.daylight]
        else:
            tz_name = time.tzname[0]

        # Map common timezone abbreviations to IANA identifiers
        tz_abbrev_map = {
            "IST": "Asia/Jerusalem",  # Israel Standard Time
            "IDT": "Asia/Jerusalem",  # Israel Daylight Time
            "EST": "America/New_York",
            "EDT": "America/New_York",
            "PST": "America/Los_Angeles",
            "PDT": "America/Los_Angeles",
            "GMT": "UTC",
            "UTC": "UTC",
        }

        if tz_name in tz_abbrev_map:
            return tz_abbrev_map[tz_name]
    except Exception:
        pass

    # Last resort: return UTC
    return "UTC"


def get_agent(
    prompt: PullPromptResponse,
    user_id: str,
    session_id: str,
    organizer_email: str,
    tenant_id: str,
    timezone: str = "UTC",
    model_id: str = Model.gemini_2_5_pro,
    debug_mode: Optional[bool] = None,
    fetch_token_func: Optional[Callable[[str, str], Optional[str]]] = None,
    config: Optional[AgentConfig] = None,
    db_skills: Optional[List[SkillDB]] = None,
) -> Agent:
    agent_slug_id = prompt.name
    db_table_name = slug_to_table_name(f"a_{agent_slug_id}_agent")

    # Extract agent_name from tags (find tag that starts with "agent_name:")
    agent_name = prompt.name  # Default to prompt.name if not found
    if prompt.tags:
        for tag in prompt.tags:
            if tag.startswith("agent_name:"):
                agent_name = tag.split(":", 1)[1].strip()
                break

    system_prompt_template = prompt.template

    # Use environment-based debug mode if not explicitly provided
    if debug_mode is None:
        debug_mode = api_settings.agent_debug_mode

    # Use defaults if no config provided
    if config is None:
        config = AgentConfig()

    # Create PostgresDb instance for agent storage and memories
    db_instance = PostgresDb(db_url=db_url, session_table=db_table_name)

    # Create MemoryManager only if memory is enabled
    memory_manager = None
    if config.enable_memory:
        memory_manager = MemoryManager(
            model=create_model(
                model=model_id,
                gemini_api_key=api_settings.gemini_api_key,
                openai_api_key=api_settings.openai_api_key,
                anthropic_api_key=api_settings.anthropic_api_key,
            ),
            db=db_instance,
            delete_memories=True,
            clear_memories=True,
        )

    # Extract available tools from tags (empty set means no optional toolkits)
    available_tools = extract_available_tools(prompt)

    # Initialize toolkit selector if organizer_email and fetch_token_func are provided
    if organizer_email and fetch_token_func and user_id:
        # Conditionally create toolkit instances based on available_tools tag
        calendar_google = None
        calendar_microsoft = None
        calendar_no_auth = None
        if "calendar" in available_tools:
            calendar_google = CalendarToolkit(
                user_id=user_id,
                organizer_email=organizer_email,
                service_name="google_calendar",
                auth=True,
                fetch_token_func=fetch_token_func,
            )
            calendar_microsoft = CalendarToolkit(
                user_id=user_id,
                organizer_email=organizer_email,
                service_name="microsoft_calendar",
                auth=True,
                fetch_token_func=fetch_token_func,
            )
            calendar_no_auth = CalendarToolkit(
                user_id=user_id,
                organizer_email=organizer_email,
                service_name="calendar",
                auth=False,
            )

        contacts_google = None
        contacts_microsoft = None
        contacts_no_auth = None
        if "contacts" in available_tools:
            contacts_google = ContactsToolkit(
                user_id=user_id,
                service_name="google_contacts",
                auth=True,
                fetch_token_func=fetch_token_func,
            )
            contacts_microsoft = ContactsToolkit(
                user_id=user_id,
                service_name="microsoft_contacts",
                auth=True,
                fetch_token_func=fetch_token_func,
            )
            contacts_no_auth = ContactsToolkit(
                user_id=user_id,
                service_name="contacts",
                auth=False,
            )

        drive_google = None
        drive_microsoft = None
        drive_no_auth = None
        if "drive" in available_tools:
            drive_google = DriveToolkit(
                user_id=user_id,
                service_name="google_drive",
                auth=True,
                fetch_token_func=fetch_token_func,
                tenant_id=tenant_id,
            )
            drive_microsoft = DriveToolkit(
                user_id=user_id,
                service_name="microsoft_drive",
                auth=True,
                fetch_token_func=fetch_token_func,
                tenant_id=tenant_id,
            )
            drive_no_auth = DriveToolkit(user_id=user_id, service_name="drive", auth=False, tenant_id=tenant_id)

        email_google = None
        email_microsoft = None
        email_no_auth = None
        if "email" in available_tools:
            email_google = EmailToolkit(
                user_id=user_id,
                service_name="google_gmail",
                auth=True,
                fetch_token_func=fetch_token_func,
            )
            email_microsoft = EmailToolkit(
                user_id=user_id,
                service_name="outlook_mail",
                auth=True,
                fetch_token_func=fetch_token_func,
            )
            email_no_auth = EmailToolkit(
                user_id=user_id,
                service_name="email",
                auth=False,
            )

    # Build base tools list conditionally based on available_tools tag
    base_tools_list: list = []

    # UserControlFlowTools - conditionally enabled
    if "user_control_flow" in available_tools:
        base_tools_list.append(UserControlFlowTools(enable_get_user_input=False))

    # DateTime resolver - always enabled (mandatory)
    base_tools_list.append(create_datetime_resolver_tool(timezone))

    # BrightDataTools - conditionally enabled
    if "brightdata" in available_tools:
        base_tools_list.append(
            BrightDataTools(
                api_key=api_settings.bright_data_api_key or None,
                serp_zone=api_settings.bright_data_serp_zone,
                web_unlocker_zone=api_settings.bright_data_web_unlocker_zone,
                verbose=True,
            )
        )

    # Initialize toolkit selector if organizer_email and fetch_token_func are provided
    if organizer_email and fetch_token_func and user_id:
        # Create the toolkit selector hook (will only select from non-None toolkits)
        # Pass base_tools_list so the pre-hook can preserve them
        pre_hooks = [
            create_multi_toolkit_selector(
                user_id=user_id,
                timezone=timezone,
                base_tools=base_tools_list,
                calendar_google=calendar_google,
                calendar_microsoft=calendar_microsoft,
                calendar_no_auth=calendar_no_auth,
                contacts_google=contacts_google,
                contacts_microsoft=contacts_microsoft,
                contacts_no_auth=contacts_no_auth,
                drive_google=drive_google,
                drive_microsoft=drive_microsoft,
                drive_no_auth=drive_no_auth,
                email_google=email_google,
                email_microsoft=email_microsoft,
                email_no_auth=email_no_auth,
            )
        ]
    else:
        pre_hooks = []

    # Add guardrails if enabled
    if api_settings.enable_guardrails:
        guardrails = [PromptInjectionGuardrail(), PIIDetectionGuardrail(mask_pii=True)]
        pre_hooks = guardrails + pre_hooks

    # Use base_tools_list as initial tools (will be updated by pre-hook if enabled)
    tools_list = base_tools_list

    # Load skills from database if provided
    skills = Skills(loaders=[DbSkillLoader(db_skills)]) if db_skills else None

    return Agent(
        add_datetime_to_context=True,
        add_history_to_context=config.enable_history,
        compress_tool_results=True,
        db=db_instance,
        debug_mode=debug_mode,
        enable_agentic_memory=config.enable_memory,
        enable_agentic_state=True,
        id=agent_slug_id,
        knowledge=get_knowledge_service().get_dynamic_kb(),
        markdown=True,
        memory_manager=memory_manager,
        model=create_model(
            model=model_id,
            gemini_api_key=api_settings.gemini_api_key,
            openai_api_key=api_settings.openai_api_key,
            anthropic_api_key=api_settings.anthropic_api_key,
        ),
        name=agent_name,
        num_history_runs=config.num_history_runs,
        pre_hooks=pre_hooks,
        read_chat_history=config.enable_history,
        reasoning=config.enable_reasoning,
        reasoning_min_steps=config.reasoning_min_steps,
        reasoning_max_steps=config.reasoning_max_steps,
        search_knowledge=True,
        skills=skills,
        session_id=session_id,
        store_history_messages=True,
        stream_events=True,
        system_message=system_prompt_template,
        tools=tools_list,
        user_id=user_id,
        timezone_identifier=timezone,
    )
