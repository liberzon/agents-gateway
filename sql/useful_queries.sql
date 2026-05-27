-- ====================================
-- USEFUL QUERIES FOR AGENT API
-- ====================================

-- Collection of useful SQL queries for managing and monitoring the Agent API

-- ====================================
-- 1. AGENT MANAGEMENT QUERIES
-- ====================================

-- Get all active agents with their details
SELECT 
    id,
    name,
    description,
    prompt_service_id,
    tags,
    created_at,
    updated_at
FROM agent_info 
WHERE is_active = true 
ORDER BY name;

-- Get agent by ID with full details
SELECT * FROM agent_info WHERE id = 'customer-support-agent' AND is_active = true;

-- Find agents by tag (JSON search)
SELECT id, name, tags 
FROM agent_info 
WHERE is_active = true 
AND tags LIKE '%"support"%'
ORDER BY name;

-- Get recently created agents (last 7 days)
SELECT id, name, created_at 
FROM agent_info 
WHERE is_active = true 
AND created_at >= NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;

-- ====================================
-- 2. TEAM MANAGEMENT QUERIES
-- ====================================

-- Get all active teams with agent count
SELECT 
    t.id,
    t.name,
    t.description,
    COUNT(ta.agent_id) as agent_count,
    t.created_at
FROM team_info t
LEFT JOIN team_agent ta ON t.id = ta.team_id AND ta.is_active = true
WHERE t.is_active = true
GROUP BY t.id, t.name, t.description, t.created_at
ORDER BY t.name;

-- Get team with all its agents (detailed view)
SELECT 
    t.id as team_id,
    t.name as team_name,
    t.description as team_description,
    a.id as agent_id,
    a.name as agent_name,
    ta.role as agent_role,
    ta.order_index
FROM team_info t
JOIN team_agent ta ON t.id = ta.team_id
JOIN agent_info a ON ta.agent_id = a.id
WHERE t.id = 'support-team' 
AND t.is_active = true 
AND ta.is_active = true 
AND a.is_active = true
ORDER BY ta.order_index, ta.created_at;

-- Get all teams an agent belongs to
SELECT 
    a.id as agent_id,
    a.name as agent_name,
    t.id as team_id,
    t.name as team_name,
    ta.role as role_in_team,
    ta.order_index
FROM agent_info a
JOIN team_agent ta ON a.id = ta.agent_id
JOIN team_info t ON ta.team_id = t.id
WHERE a.id = 'technical-writer-agent'
AND a.is_active = true 
AND ta.is_active = true 
AND t.is_active = true
ORDER BY t.name;

-- Find teams without agents
SELECT t.id, t.name 
FROM team_info t
LEFT JOIN team_agent ta ON t.id = ta.team_id AND ta.is_active = true
WHERE t.is_active = true 
AND ta.team_id IS NULL;

-- Find agents not assigned to any team
SELECT a.id, a.name 
FROM agent_info a
LEFT JOIN team_agent ta ON a.id = ta.agent_id AND ta.is_active = true
WHERE a.is_active = true 
AND ta.agent_id IS NULL;

-- ====================================
-- 3. TOKEN USAGE ANALYTICS
-- ====================================

-- Token usage summary by agent
SELECT 
    agent_id,
    COUNT(*) as total_requests,
    SUM(prompt_tokens) as total_prompt_tokens,
    SUM(completion_tokens) as total_completion_tokens,
    SUM(total_tokens) as total_tokens,
    ROUND(AVG(total_tokens), 2) as avg_tokens_per_request,
    COUNT(CASE WHEN is_estimated = true THEN 1 END) as estimated_requests,
    MIN(created_at) as first_request,
    MAX(created_at) as last_request
FROM token_usage 
GROUP BY agent_id 
ORDER BY total_tokens DESC;

-- Token usage by day (last 30 days)
SELECT 
    DATE(created_at) as usage_date,
    COUNT(*) as total_requests,
    SUM(total_tokens) as total_tokens,
    COUNT(DISTINCT agent_id) as unique_agents,
    COUNT(DISTINCT user_id) as unique_users
FROM token_usage 
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY usage_date DESC;

-- Top users by token consumption
SELECT 
    user_id,
    COUNT(*) as total_requests,
    SUM(total_tokens) as total_tokens,
    COUNT(DISTINCT agent_id) as agents_used,
    ROUND(AVG(total_tokens), 2) as avg_tokens_per_request
FROM token_usage 
WHERE user_id IS NOT NULL
GROUP BY user_id 
ORDER BY total_tokens DESC
LIMIT 10;

-- Token usage by model
SELECT 
    model,
    COUNT(*) as total_requests,
    SUM(total_tokens) as total_tokens,
    ROUND(AVG(total_tokens), 2) as avg_tokens_per_request
FROM token_usage 
WHERE model IS NOT NULL
GROUP BY model 
ORDER BY total_tokens DESC;

-- ====================================
-- 4. MAINTENANCE QUERIES
-- ====================================

-- Soft delete an agent (deactivate)
-- UPDATE agent_info SET is_active = false WHERE id = 'agent-to-deactivate';

-- Soft delete a team and its relationships
-- UPDATE team_info SET is_active = false WHERE id = 'team-to-deactivate';
-- UPDATE team_agent SET is_active = false WHERE team_id = 'team-to-deactivate';

-- Remove an agent from a specific team
-- UPDATE team_agent 
-- SET is_active = false 
-- WHERE team_id = 'support-team' AND agent_id = 'agent-to-remove';

-- Reactivate a soft-deleted agent
-- UPDATE agent_info SET is_active = true WHERE id = 'agent-to-reactivate';

-- Clean up old token usage data (older than 90 days)
-- DELETE FROM token_usage WHERE created_at < NOW() - INTERVAL '90 days';

-- ====================================
-- 5. MONITORING QUERIES
-- ====================================

-- Database health check - table sizes
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats 
WHERE schemaname = 'public' 
AND tablename IN ('agent_info', 'team_info', 'team_agent', 'token_usage');

-- Check for data integrity issues
-- Agents referenced in team_agent but not in agent_info
SELECT DISTINCT ta.agent_id 
FROM team_agent ta 
LEFT JOIN agent_info a ON ta.agent_id = a.id 
WHERE a.id IS NULL AND ta.is_active = true;

-- Teams referenced in team_agent but not in team_info
SELECT DISTINCT ta.team_id 
FROM team_agent ta 
LEFT JOIN team_info t ON ta.team_id = t.id 
WHERE t.id IS NULL AND ta.is_active = true;

-- Check for duplicate active team-agent relationships (should be empty)
SELECT team_id, agent_id, COUNT(*) 
FROM team_agent 
WHERE is_active = true 
GROUP BY team_id, agent_id 
HAVING COUNT(*) > 1;

-- ====================================
-- 6. PERFORMANCE QUERIES
-- ====================================

-- Most active agents (by request count)
SELECT 
    agent_id,
    COUNT(*) as request_count,
    MAX(created_at) as last_used
FROM token_usage 
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY agent_id 
ORDER BY request_count DESC
LIMIT 5;

-- Peak usage hours
SELECT 
    EXTRACT(HOUR FROM created_at) as hour_of_day,
    COUNT(*) as request_count,
    SUM(total_tokens) as total_tokens
FROM token_usage 
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY EXTRACT(HOUR FROM created_at)
ORDER BY request_count DESC;

-- Session activity analysis
SELECT 
    session_id,
    COUNT(*) as request_count,
    SUM(total_tokens) as total_tokens,
    COUNT(DISTINCT agent_id) as agents_used,
    MIN(created_at) as session_start,
    MAX(created_at) as session_end,
    EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at)))/60 as session_duration_minutes
FROM token_usage 
WHERE session_id IS NOT NULL
AND created_at >= NOW() - INTERVAL '24 hours'
GROUP BY session_id 
HAVING COUNT(*) > 1
ORDER BY total_tokens DESC
LIMIT 10;