-- Neon PostgreSQL Schema for Mecris-Go

-- 1. Users Table (Minimal for Phase 2)
CREATE TABLE IF NOT EXISTS users (
    pocket_id_sub VARCHAR(255) PRIMARY KEY, -- From Pocket ID JWT
    beeminder_token_encrypted TEXT NOT NULL, -- Encrypted or plain for now based on Phase 2
    notification_prefs JSONB DEFAULT '{}',
    timezone VARCHAR(50) DEFAULT 'UTC',
    budget_limit NUMERIC(10, 2) DEFAULT 0.00,
    budget_spent_groq NUMERIC(10, 2) DEFAULT 0.00,
    mcp_server_url TEXT,
    beeminder_goal VARCHAR(255) DEFAULT 'bike',
    beeminder_user VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Walk Inferences Table
CREATE TABLE IF NOT EXISTS walk_inferences (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    step_count TEXT NOT NULL,
    distance_meters TEXT NOT NULL,
    distance_source TEXT NOT NULL, -- e.g., 'estimated', 'gps'
    confidence_score TEXT NOT NULL, -- e.g., 0.85
    gps_route_points TEXT DEFAULT '0',
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'logged'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Idempotency constraint: User can only have one walk starting at a given exact time window
    CONSTRAINT idx_walk_user_start UNIQUE (user_id, start_time)
);

-- 3. Notification Log Table (Placeholder for Phase 2)
CREATE TABLE IF NOT EXISTS notification_log (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
    channel VARCHAR(50) NOT NULL, -- 'Push', 'Telegram', 'WhatsApp'
    cost_usd NUMERIC(10, 5) DEFAULT 0.00,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Spam Prevention: no more than 1 per 4 hours per user logic enforced via DB checks or App logic
    CONSTRAINT spam_prevention CHECK (sent_at > NOW() - INTERVAL '4 hours')
);
