import re
from typing import Any


def normalize_template(template: str) -> str:
    """Normalize a prompt template by cleaning up whitespace and formatting."""
    # Remove leading/trailing whitespace from each line
    lines = template.strip().split("\n")
    normalized_lines = [line.rstrip() for line in lines]

    # Remove empty lines at start and end
    while normalized_lines and not normalized_lines[0].strip():
        normalized_lines.pop(0)
    while normalized_lines and not normalized_lines[-1].strip():
        normalized_lines.pop()

    return "\n".join(normalized_lines)


def extract_variables(template: str) -> list[str]:
    """Extract variable placeholders from a template.

    Supports:
    - {variable_name}
    - {{variable_name}}
    - {variable_name:format}
    """
    # Match single or double braces with optional format specifier
    pattern = r"\{?\{(\w+)(?::[^}]+)?\}\}?"
    matches = re.findall(pattern, template)
    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique_vars = []
    for var in matches:
        if var not in seen:
            seen.add(var)
            unique_vars.append(var)
    return unique_vars


def validate_template(template: str) -> tuple[bool, list[str]]:
    """Validate a prompt template.

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors: list[str] = []

    if not template or not template.strip():
        errors.append("Template cannot be empty")
        return False, errors

    # Check for unmatched braces
    open_braces = template.count("{")
    close_braces = template.count("}")

    if open_braces != close_braces:
        errors.append(f"Unmatched braces: {open_braces} opening, {close_braces} closing")

    # Check for very short templates
    if len(template.strip()) < 10:
        errors.append("Template is too short (minimum 10 characters)")

    return len(errors) == 0, errors


def render_template(template: str, variables: dict[str, Any]) -> str:
    """Render a template with the given variables.

    Supports both single {var} and double {{var}} brace formats.
    """
    result = template

    for key, value in variables.items():
        # Replace double braces first (more specific)
        result = result.replace(f"{{{{{key}}}}}", str(value))
        # Then single braces
        result = result.replace(f"{{{key}}}", str(value))

    return result


def parse_tools_config(tools_json: str | None) -> list[dict[str, Any]]:
    """Parse tools configuration from JSON string."""
    if not tools_json:
        return []

    import json

    try:
        tools = json.loads(tools_json)
        if isinstance(tools, list):
            return tools
        return []
    except json.JSONDecodeError:
        return []


def parse_tags(tags_json: str | None) -> list[str]:
    """Parse tags from JSON string."""
    if not tags_json:
        return []

    import json

    try:
        tags = json.loads(tags_json)
        if isinstance(tags, list):
            return [str(tag) for tag in tags]
        return []
    except json.JSONDecodeError:
        return []
