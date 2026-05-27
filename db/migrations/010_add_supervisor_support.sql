-- Migration: Add supervisor/worker platform support
-- Adds: supervisor_runs, execution_jobs, execution_engines, execution_targets tables
-- Modifies: team_info (adds mode column)

-- ============================================================================
-- TEAM INFO: Add mode column
-- ============================================================================

ALTER TABLE team_info ADD COLUMN IF NOT EXISTS mode VARCHAR NOT NULL DEFAULT 'coordinate';

COMMENT ON COLUMN team_info.mode IS 'Team orchestration mode: coordinate (default) or supervisor';

-- ============================================================================
-- SUPERVISOR RUNS TABLE (audit log)
-- ============================================================================

CREATE TABLE IF NOT EXISTS supervisor_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id VARCHAR NOT NULL,
    session_id VARCHAR,
    user_id VARCHAR,
    user_message TEXT NOT NULL,
    supervisor_response JSONB,
    worker_agent_id VARCHAR,
    execution_engine VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'pending',
    execution_output TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_supervisor_runs_team_id ON supervisor_runs(team_id);
CREATE INDEX IF NOT EXISTS idx_supervisor_runs_session_id ON supervisor_runs(session_id);
CREATE INDEX IF NOT EXISTS idx_supervisor_runs_user_id ON supervisor_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_supervisor_runs_status ON supervisor_runs(status);
CREATE INDEX IF NOT EXISTS idx_supervisor_runs_created_at ON supervisor_runs(created_at);

COMMENT ON TABLE supervisor_runs IS 'Audit log for supervisor classification and execution runs';

-- ============================================================================
-- EXECUTION JOBS TABLE (job queue)
-- ============================================================================

CREATE TABLE IF NOT EXISTS execution_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supervisor_run_id UUID,
    worker_config JSONB NOT NULL,
    prompt TEXT NOT NULL,
    execution_target JSONB,
    status VARCHAR NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'awaiting_approval', 'completed', 'failed', 'oom', 'failed_circuit_open')),
    result JSONB,
    container_id VARCHAR,
    target_host VARCHAR,
    retry_count INTEGER DEFAULT 0,
    memory_limit_mb INTEGER,
    last_failure_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    timeout_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_execution_jobs_supervisor_run_id ON execution_jobs(supervisor_run_id);
CREATE INDEX IF NOT EXISTS idx_execution_jobs_status ON execution_jobs(status);
CREATE INDEX IF NOT EXISTS idx_execution_jobs_target_host ON execution_jobs(target_host);
CREATE INDEX IF NOT EXISTS idx_execution_jobs_created_at ON execution_jobs(created_at);

-- Index for job queue polling: find queued jobs for a specific host
CREATE INDEX IF NOT EXISTS idx_execution_jobs_queue_poll
    ON execution_jobs(status, target_host, created_at)
    WHERE status = 'queued';

COMMENT ON TABLE execution_jobs IS 'Job queue for execution engine dispatch with OOM retry tracking';

-- ============================================================================
-- EXECUTION ENGINES TABLE (engine registry)
-- ============================================================================

CREATE TABLE IF NOT EXISTS execution_engines (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    type VARCHAR NOT NULL CHECK (type IN ('code_agent', 'managed_agent', 'direct_ops', 'custom')),
    provider VARCHAR NOT NULL DEFAULT 'anthropic',
    handler_config JSONB,
    description TEXT,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_execution_engines_is_active ON execution_engines(is_active);
CREATE INDEX IF NOT EXISTS idx_execution_engines_type ON execution_engines(type);
CREATE INDEX IF NOT EXISTS idx_execution_engines_provider ON execution_engines(provider);

DROP TRIGGER IF EXISTS update_execution_engines_updated_at ON execution_engines;
CREATE TRIGGER update_execution_engines_updated_at
    BEFORE UPDATE ON execution_engines
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE execution_engines IS 'Registry of available execution engines (Claude Code, managed agents, etc.)';

-- Insert default engines
INSERT INTO execution_engines (id, name, type, provider, description, is_default)
VALUES
    ('claude_code', 'Claude Code', 'code_agent', 'anthropic', 'Claude Code CLI for repository-based work', TRUE),
    ('anthropic_managed', 'Anthropic Managed Agents', 'managed_agent', 'anthropic', 'Anthropic managed agents API for cloud-hosted execution', FALSE),
    ('openai_agents', 'OpenAI Agents', 'managed_agent', 'openai', 'OpenAI Agents API', FALSE),
    ('google_agents', 'Google Vertex AI Agents', 'managed_agent', 'google', 'Google Vertex AI agents', FALSE),
    ('direct_ops', 'Direct Operations Tools', 'direct_ops', 'internal', 'Runtime operations tools (kubectl, cloud CLI)', FALSE)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- EXECUTION TARGETS TABLE (target registry)
-- ============================================================================

CREATE TABLE IF NOT EXISTS execution_targets (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    type VARCHAR NOT NULL CHECK (type IN ('local', 'ssh', 'remote_service', 'managed_agents')),
    connection_config JSONB,
    capacity JSONB,
    worker_pool VARCHAR NOT NULL DEFAULT 'linux_worker_pool',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_execution_targets_is_active ON execution_targets(is_active);
CREATE INDEX IF NOT EXISTS idx_execution_targets_worker_pool ON execution_targets(worker_pool);
CREATE INDEX IF NOT EXISTS idx_execution_targets_type ON execution_targets(type);

DROP TRIGGER IF EXISTS update_execution_targets_updated_at ON execution_targets;
CREATE TRIGGER update_execution_targets_updated_at
    BEFORE UPDATE ON execution_targets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE execution_targets IS 'Registry of available execution targets (VMs, K8s clusters, etc.)';

-- Insert default targets
INSERT INTO execution_targets (id, name, type, worker_pool, connection_config)
VALUES
    ('local', 'Local', 'local', 'linux_worker_pool', '{}'),
    ('managed', 'Managed Agents (Cloud)', 'managed_agents', 'linux_worker_pool', '{}')
ON CONFLICT (id) DO NOTHING;
