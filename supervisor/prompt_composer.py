import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from db.db_models import PromptDB

logger = logging.getLogger(__name__)


def compose_worker_prompt(
    base_prompt: str,
    domain_extensions: Optional[List[str]] = None,
    job_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Compose a final worker prompt from base template + domain extensions + job context.

    1. Fill template placeholders ({objective}, {allowed_directories}, etc.)
    2. Append domain extension text blocks
    """
    prompt = base_prompt

    # Fill template placeholders from job context
    if job_context:
        for key, value in job_context.items():
            placeholder = "{" + key + "}"
            if placeholder in prompt:
                if isinstance(value, list):
                    formatted = "\n".join(f"- {item}" for item in value)
                elif isinstance(value, dict):
                    formatted = "\n".join(f"- {k}: {v}" for k, v in value.items())
                else:
                    formatted = str(value)
                prompt = prompt.replace(placeholder, formatted)

    # Clear any remaining unfilled placeholders
    prompt = re.sub(r"\{(\w+)\}", r"(not specified)", prompt)

    # Append domain extensions
    if domain_extensions:
        prompt += "\n\n"
        for ext in domain_extensions:
            prompt += f"\n{ext}\n"

    return prompt


def fetch_domain_extensions(
    db: Session,
    domain_tags: Optional[List[str]] = None,
) -> List[str]:
    """Fetch domain extension prompts by tag from the prompts table.

    Args:
        db: Database session
        domain_tags: List of domain tags to match (e.g., ["domain:data_platform"])

    Returns:
        List of domain extension prompt texts
    """
    if not domain_tags:
        return []

    extensions: List[str] = []
    prompts = db.query(PromptDB).filter(PromptDB.is_active.is_(True)).all()

    for prompt_db in prompts:
        if not prompt_db.tags:
            continue
        try:
            import json

            tags = json.loads(prompt_db.tags) if isinstance(prompt_db.tags, str) else prompt_db.tags
            if isinstance(tags, list):
                for tag in domain_tags:
                    if tag in tags:
                        extensions.append(prompt_db.template)
                        break
        except Exception:
            continue

    return extensions
