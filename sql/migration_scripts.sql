-- ====================================
-- MIGRATION SCRIPTS FOR AGENT API
-- ====================================

-- Step-by-step migration scripts for database updates

-- ====================================
-- MIGRATION 1: Add is_estimated column to token_usage
-- ====================================

-- Check if column exists before adding
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'token_usage' 
        AND column_name = 'is_estimated'
    ) THEN
        ALTER TABLE token_usage ADD COLUMN is_estimated BOOLEAN DEFAULT FALSE;
        UPDATE token_usage SET is_estimated = FALSE WHERE is_estimated IS NULL;
        RAISE NOTICE 'Added is_estimated column to token_usage table';
    ELSE
        RAISE NOTICE 'Column is_estimated already exists in token_usage table';
    END IF;
END $$;

-- ====================================
-- MIGRATION 2: Create agent_info table
-- ====================================

-- Create agent_info table if it doesn't exist
CREATE TABLE IF NOT EXISTS agent_info (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    version VARCHAR NOT NULL DEFAULT '2.0',
    prompt_service_id VARCHAR NOT NULL,
    tags VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_agent_info_is_active ON agent_info(is_active);
CREATE INDEX IF NOT EXISTS idx_agent_info_created_at ON agent_info(created_at);
CREATE INDEX IF NOT EXISTS idx_agent_info_prompt_service_id ON agent_info(prompt_service_id);

-- Create trigger for updated_at
CREATE TRIGGER IF NOT EXISTS update_agent_info_updated_at 
    BEFORE UPDATE ON agent_info 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ====================================
-- MIGRATION 3: Create team_info table
-- ====================================

-- Create team_info table if it doesn't exist
CREATE TABLE IF NOT EXISTS team_info (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    version VARCHAR NOT NULL DEFAULT '2.0',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_team_info_is_active ON team_info(is_active);
CREATE INDEX IF NOT EXISTS idx_team_info_created_at ON team_info(created_at);

-- Create trigger for updated_at
CREATE TRIGGER IF NOT EXISTS update_team_info_updated_at 
    BEFORE UPDATE ON team_info 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ====================================
-- MIGRATION 4: Create team_agent junction table
-- ====================================

-- Create team_agent table if it doesn't exist
CREATE TABLE IF NOT EXISTS team_agent (
    id SERIAL PRIMARY KEY,
    team_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    role VARCHAR,
    order_index INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_team_agent_team_id ON team_agent(team_id);
CREATE INDEX IF NOT EXISTS idx_team_agent_agent_id ON team_agent(agent_id);
CREATE INDEX IF NOT EXISTS idx_team_agent_is_active ON team_agent(is_active);
CREATE INDEX IF NOT EXISTS idx_team_agent_order ON team_agent(team_id, order_index);

-- Create unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS uq_team_agent_active 
    ON team_agent(team_id, agent_id) 
    WHERE is_active = TRUE;

-- ====================================
-- MIGRATION 5: Add missing columns to existing tables
-- ====================================

-- Add missing columns to token_usage if they don't exist
DO $$ 
BEGIN
    -- Add user_id column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'token_usage' 
        AND column_name = 'user_id'
    ) THEN
        ALTER TABLE token_usage ADD COLUMN user_id VARCHAR;
        CREATE INDEX IF NOT EXISTS idx_token_usage_user_id ON token_usage(user_id);
        RAISE NOTICE 'Added user_id column to token_usage table';
    END IF;
    
    -- Add session_id index if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename = 'token_usage' 
        AND indexname = 'idx_token_usage_session_id'
    ) THEN
        CREATE INDEX idx_token_usage_session_id ON token_usage(session_id);
        RAISE NOTICE 'Added session_id index to token_usage table';
    END IF;
END $$;

-- ====================================
-- MIGRATION 6: Data cleanup and optimization
-- ====================================

-- Remove orphaned team_agent relationships (where team or agent doesn't exist)
-- WARNING: This will delete data, run carefully in production

-- Find and report orphaned relationships first
SELECT 'Orphaned team_agent relationships found:' as message;

SELECT 
    ta.id, 
    ta.team_id, 
    ta.agent_id,
    CASE 
        WHEN t.id IS NULL THEN 'Missing team'
        WHEN a.id IS NULL THEN 'Missing agent'
        ELSE 'OK'
    END as issue
FROM team_agent ta
LEFT JOIN team_info t ON ta.team_id = t.id AND t.is_active = true
LEFT JOIN agent_info a ON ta.agent_id = a.id AND a.is_active = true
WHERE ta.is_active = true 
AND (t.id IS NULL OR a.id IS NULL);

-- Uncomment to clean up orphaned relationships
-- UPDATE team_agent SET is_active = false 
-- WHERE id IN (
--     SELECT ta.id
--     FROM team_agent ta
--     LEFT JOIN team_info t ON ta.team_id = t.id AND t.is_active = true
--     LEFT JOIN agent_info a ON ta.agent_id = a.id AND a.is_active = true
--     WHERE ta.is_active = true 
--     AND (t.id IS NULL OR a.id IS NULL)
-- );

-- ====================================
-- MIGRATION 7: Update table statistics
-- ====================================

-- Update table statistics for better query performance
ANALYZE agent_info;
ANALYZE team_info;
ANALYZE team_agent;
ANALYZE token_usage;

-- ====================================
-- ROLLBACK SCRIPTS (Use with caution)
-- ====================================

-- Rollback Migration 4: Drop team_agent table
-- DROP TABLE IF EXISTS team_agent CASCADE;

-- Rollback Migration 3: Drop team_info table  
-- DROP TABLE IF EXISTS team_info CASCADE;

-- Rollback Migration 2: Drop agent_info table
-- DROP TABLE IF EXISTS agent_info CASCADE;

-- Rollback Migration 1: Remove is_estimated column
-- ALTER TABLE token_usage DROP COLUMN IF EXISTS is_estimated;

-- ====================================
-- VERIFICATION QUERIES
-- ====================================

-- Verify all tables exist
SELECT 
    table_name,
    table_type
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('agent_info', 'team_info', 'team_agent', 'token_usage')
ORDER BY table_name;

-- Verify all indexes exist
SELECT 
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename IN ('agent_info', 'team_info', 'team_agent', 'token_usage')
ORDER BY tablename, indexname;

-- Verify all triggers exist
SELECT 
    trigger_name,
    event_object_table,
    action_timing,
    event_manipulation
FROM information_schema.triggers 
WHERE event_object_table IN ('agent_info', 'team_info', 'team_agent', 'token_usage')
ORDER BY event_object_table, trigger_name;

-- Check table constraints
SELECT 
    table_name,
    constraint_name,
    constraint_type
FROM information_schema.table_constraints 
WHERE table_name IN ('agent_info', 'team_info', 'team_agent', 'token_usage')
ORDER BY table_name, constraint_name;