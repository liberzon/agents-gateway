from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StreamVerbosity(str, Enum):
    full = "full"
    events = "events"
    result = "result"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    awaiting_approval = "awaiting_approval"
    completed = "completed"
    failed = "failed"
    oom = "oom"
    failed_circuit_open = "failed_circuit_open"


class ExecutionTargetType(str, Enum):
    local = "local"
    ssh = "ssh"
    remote_service = "remote_service"
    managed_agents = "managed_agents"


class EngineType(str, Enum):
    code_agent = "code_agent"
    managed_agent = "managed_agent"
    direct_ops = "direct_ops"
    custom = "custom"


class WorkerType(str, Enum):
    coding = "coding"
    planning = "planning"
    infrastructure = "infrastructure"
    operations = "operations"
    documentation = "documentation"
    verifier = "verifier"
    data_platform = "data_platform"
    bi_reporting = "bi_reporting"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class OperationMode(str, Enum):
    none = "none"
    observe_only = "observe_only"
    safe_remediation = "safe_remediation"
    dangerous_remediation = "dangerous_remediation"


class Classification(str, Enum):
    no_action = "no_action"
    answer_only = "answer_only"
    read_only_analysis = "read_only_analysis"
    code_fix = "code_fix"
    feature_small = "feature_small"
    feature_medium = "feature_medium"
    feature_large = "feature_large"
    refactor_scoped = "refactor_scoped"
    test_generation = "test_generation"
    documentation_update = "documentation_update"
    infrastructure_change = "infrastructure_change"
    noc_operation = "noc_operation"
    high_risk_escalation = "high_risk_escalation"


# ---------------------------------------------------------------------------
# MCP & Plugin Configuration
# ---------------------------------------------------------------------------


class MCPServerConfig(BaseModel):
    name: str
    type: str = "stdio"  # stdio, http, sse
    command: Optional[str] = None  # for stdio
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    url: Optional[str] = None  # for http/sse
    headers: Dict[str, str] = Field(default_factory=dict)
    description: Optional[str] = None


class HookConfig(BaseModel):
    event: str  # PreToolUse, PostToolUse, PermissionRequest, Stop, etc.
    matcher: str = ""  # tool matcher pattern (e.g. "Bash", "Edit|Write")
    hook_type: str = "command"  # command, http
    command_or_url: str = ""
    timeout: int = 30


class PermissionRules(BaseModel):
    allow: List[str] = Field(default_factory=list)
    deny: List[str] = Field(default_factory=list)
    ask: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Worker & Execution Configuration
# ---------------------------------------------------------------------------


class WorkerConfig(BaseModel):
    mcp_servers: List[MCPServerConfig] = Field(default_factory=list)
    hooks: List[HookConfig] = Field(default_factory=list)
    permissions: PermissionRules = Field(default_factory=PermissionRules)
    execution_engine_preference: Optional[str] = None  # engine registry ID
    worker_pool: str = "linux_worker_pool"
    allowed_tools: List[str] = Field(default_factory=list)
    allowed_commands: List[str] = Field(default_factory=list)


class ExecutionTarget(BaseModel):
    type: ExecutionTargetType = ExecutionTargetType.local
    host: Optional[str] = None
    port: Optional[int] = None
    repo_path: Optional[str] = None
    ssh_key_path: Optional[str] = None
    api_url: Optional[str] = None
    worker_pool: str = "linux_worker_pool"


class ExecutionLimits(BaseModel):
    network_access: bool = False
    allow_dependency_install: bool = False
    allow_git_push: bool = False
    allow_merge: bool = False
    allow_delete_files: bool = False
    allow_migrations: bool = False
    allow_apply_or_deploy: bool = False
    allow_production_change: bool = False
    max_runtime_minutes: int = 15
    max_attempts: int = 3
    max_memory_mb: int = 4096
    max_cpus: float = 2.0


class RetryPolicy(BaseModel):
    max_retries: int = 2
    memory_multiplier: float = 2.0
    enable_supervisor_replan: bool = True
    circuit_breaker_threshold: int = 3


# ---------------------------------------------------------------------------
# Supervisor Output Schema (matches prompt pack JSON contract)
# ---------------------------------------------------------------------------


class JobSpec(BaseModel):
    job_type: str = "none"  # planning, coding, infrastructure, operations, etc.
    operation_mode: OperationMode = OperationMode.none
    environment: str = "unknown"  # dev, staging, prod, local, unknown
    worker_pool: str = "linux_worker_pool"
    preferred_execution_engine: str = "none"  # engine registry ID or "none"
    objective: str = ""
    repository: str = ""
    iac_system: str = "none"  # terraform, cdk, cloudformation, helm, kubernetes_manifest, none
    suggested_branch_name: str = ""
    allowed_directories: List[str] = Field(default_factory=list)
    forbidden_directories: List[str] = Field(default_factory=list)
    resource_scope: List[str] = Field(default_factory=list)
    allowed_tools: List[str] = Field(default_factory=list)
    allowed_commands: List[str] = Field(default_factory=list)
    forbidden_actions: List[str] = Field(default_factory=list)
    worker_context: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)
    verification_steps: List[str] = Field(default_factory=list)
    rollback_steps: List[str] = Field(default_factory=list)
    stop_conditions: List[str] = Field(default_factory=list)
    output_contract: List[str] = Field(
        default_factory=lambda: [
            "summary",
            "files_changed_or_resources_touched",
            "commands_run",
            "verification_results",
            "remaining_risks",
        ]
    )
    execution_limits: ExecutionLimits = Field(default_factory=ExecutionLimits)


class SupervisorResponse(BaseModel):
    classification: Classification = Classification.no_action
    should_invoke_worker: bool = False
    worker_type: str = "none"  # WorkerType value or "none"
    execution_engine: str = "none"  # engine preference
    execution_engine_reason: str = ""
    rationale: str = ""
    risk_level: RiskLevel = RiskLevel.low
    requires_human_review: bool = False
    job: JobSpec = Field(default_factory=JobSpec)


# ---------------------------------------------------------------------------
# Execution Result
# ---------------------------------------------------------------------------


class ExecutionResult(BaseModel):
    output: str = ""
    files_changed: List[str] = Field(default_factory=list)
    commands_run: List[str] = Field(default_factory=list)
    verification_results: Dict[str, Any] = Field(default_factory=dict)
    status: str = "completed"  # completed, failed, oom, cancelled
    error: Optional[str] = None
    container_id: Optional[str] = None
    duration_seconds: Optional[float] = None
    retry_count: int = 0


# ---------------------------------------------------------------------------
# Approval Flow
# ---------------------------------------------------------------------------


class ApprovalRequest(BaseModel):
    job_id: str
    tool_name: str
    tool_args: Dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    risk_level: RiskLevel = RiskLevel.medium


class ApprovalDecision(BaseModel):
    approved: bool
    modified_args: Optional[Dict[str, Any]] = None
    reason: str = ""


# ---------------------------------------------------------------------------
# Stream Event
# ---------------------------------------------------------------------------


class StreamEvent(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: str  # tool_call, tool_result, thinking, message, status, approval_request, error
    worker_id: Optional[str] = None
    content: Any = None


# ---------------------------------------------------------------------------
# API Request/Response Models
# ---------------------------------------------------------------------------


class SupervisorRunRequest(BaseModel):
    message: str
    stream: bool = True
    stream_verbosity: StreamVerbosity = StreamVerbosity.events
    model: str = "gemini-2.5-pro"
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    user_profile: Optional[Dict[str, Any]] = None
    tenant_profile: Optional[Dict[str, Any]] = None
    timezone: str = "UTC"


class SupervisorRunResponse(BaseModel):
    run_id: str
    team_id: str
    classification: Classification
    worker_type: str
    execution_engine: str
    risk_level: RiskLevel
    requires_human_review: bool
    job_spec: JobSpec
    execution_result: Optional[ExecutionResult] = None
    status: str = "classified"


# ---------------------------------------------------------------------------
# Engine & Target Registry Models
# ---------------------------------------------------------------------------


class EngineCreate(BaseModel):
    id: str
    name: str
    type: EngineType
    provider: str = "anthropic"
    handler_config: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None
    is_default: bool = False


class EngineInfo(BaseModel):
    id: str
    name: str
    type: EngineType
    provider: str
    handler_config: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None
    is_default: bool = False
    is_active: bool = True


class TargetCreate(BaseModel):
    id: str
    name: str
    type: ExecutionTargetType
    connection_config: Dict[str, Any] = Field(default_factory=dict)
    capacity: Dict[str, Any] = Field(default_factory=dict)
    worker_pool: str = "linux_worker_pool"


class TargetInfo(BaseModel):
    id: str
    name: str
    type: ExecutionTargetType
    connection_config: Dict[str, Any] = Field(default_factory=dict)
    capacity: Dict[str, Any] = Field(default_factory=dict)
    worker_pool: str = "linux_worker_pool"
    is_active: bool = True
