from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentDefinition(BaseModel):
    id: str
    name: str
    prompt_file: str  # relative path to prompt text file
    role: str = "worker"  # leader or worker
    engine: str = "claude_code"  # execution engine preference
    target: str = "linux-pool"  # execution target pool
    order_index: int = 0
    worker_config: Optional[Dict[str, Any]] = None  # full WorkerConfig as dict


class ExtensionDefinition(BaseModel):
    id: str
    name: str
    prompt_file: str  # relative path to extension text file
    domain_tags: List[str] = Field(default_factory=list)  # e.g., ["domain:data_platform"]


class TeamConfig(BaseModel):
    id: str = "supervisor-team"
    name: str = "Supervisor Team"
    mode: str = "supervisor"


class PackManifest(BaseModel):
    name: str
    version: str = "1.0"
    description: Optional[str] = None
    agents: List[AgentDefinition] = Field(default_factory=list)
    extensions: List[ExtensionDefinition] = Field(default_factory=list)
    team: TeamConfig = Field(default_factory=TeamConfig)
    default_engine: str = "claude_code"
    default_target: str = "linux-pool"
