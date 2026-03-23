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

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_walk_status ON walk_inferences(status);
CREATE INDEX IF NOT EXISTS idx_walk_start_time ON walk_inferences (start_time);

-- 4. Language Stats Table
CREATE TABLE IF NOT EXISTS language_stats (
    user_id VARCHAR(255) REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
    language_name VARCHAR(50),
    current_reviews INTEGER DEFAULT 0,
    tomorrow_reviews INTEGER DEFAULT 0,
    next_7_days_reviews INTEGER DEFAULT 0,
    daily_rate NUMERIC(10, 2) DEFAULT 0,
    safebuf INTEGER DEFAULT 0,
    derail_risk VARCHAR(50) DEFAULT 'SAFE',
    pump_multiplier NUMERIC(4, 1) DEFAULT 1.0,
    beeminder_slug VARCHAR(255),
    daily_completions INTEGER DEFAULT 0,
    last_points INTEGER DEFAULT 0,
    total_points INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, language_name)
);

-- 5. Scheduler Election Table
CREATE TABLE IF NOT EXISTS scheduler_election (
    id SERIAL PRIMARY KEY,
    role VARCHAR(50) NOT NULL UNIQUE, -- 'leader'
    process_id VARCHAR(50) NOT NULL,
    heartbeat TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
