from typing import List, Optional

from pydantic import BaseModel, Field

# ------------------------------------------------------------------ #
# Pydantic I/O models
# ------------------------------------------------------------------ #


class ToolSchema(BaseModel):
    name: str
    description: str
    parameters: dict


class PushPromptRequest(BaseModel):
    name: str
    raw_template: str = Field(
        ...,
        description=r"Template containing literal '\n' and [placeholders]",
    )
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    tools: Optional[List[ToolSchema]] = None  # optional tool list


class PushPromptResponse(BaseModel):
    url: str


class PullPromptResponse(BaseModel):
    name: str
    template: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    tools: Optional[List[ToolSchema]] = None


class ListPromptsResponse(BaseModel):
    prompts: List[str]
