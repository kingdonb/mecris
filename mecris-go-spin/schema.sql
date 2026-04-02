-- Neon PostgreSQL Schema for Mecris-Go

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    pocket_id_sub VARCHAR(255) PRIMARY KEY, -- From Pocket ID JWT
    familiar_id VARCHAR(255) UNIQUE,        -- e.g., 'yebyen'
    beeminder_token_encrypted TEXT,
    beeminder_user VARCHAR(255),
    beeminder_goal VARCHAR(255) DEFAULT 'bike',
    clozemaster_email_encrypted TEXT,
    clozemaster_password_encrypted TEXT,
    notification_prefs JSONB DEFAULT '{}',
    timezone VARCHAR(50) DEFAULT 'UTC',
    budget_limit NUMERIC(10, 2) DEFAULT 0.00,
    budget_spent_groq NUMERIC(10, 2) DEFAULT 0.00,
    mcp_server_url TEXT,
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
    
    CONSTRAINT idx_walk_user_start UNIQUE (user_id, start_time)
);

CREATE INDEX IF NOT EXISTS idx_walk_status ON walk_inferences(status);
CREATE INDEX IF NOT EXISTS idx_walk_start_time ON walk_inferences (start_time);

-- 3. Language Stats Table
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

-- 4. Goals Table (Proactive tracking)
CREATE TABLE IF NOT EXISTS goals (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    priority VARCHAR(50) DEFAULT 'medium',
    status VARCHAR(50) DEFAULT 'active',
    due_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- 5. Message Log Table
CREATE TABLE IF NOT EXISTS message_log (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
    date DATE DEFAULT CURRENT_DATE,
    type VARCHAR(100) NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    content TEXT,
    channel VARCHAR(50) DEFAULT 'whatsapp'
);

-- 6. Usage Sessions (LLM Cost Tracking)
CREATE TABLE IF NOT EXISTS usage_sessions (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    model VARCHAR(100),
    input_tokens INTEGER,
    output_tokens INTEGER,
    estimated_cost NUMERIC(10, 6),
    session_type VARCHAR(50),
    notes TEXT
);

-- 7. Autonomous Turns
CREATE TABLE IF NOT EXISTS autonomous_turns (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    agent_type VARCHAR(100) NOT NULL,
    agenda_slug VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'success',
    tokens_consumed INTEGER DEFAULT 0,
    cost NUMERIC(10, 6) DEFAULT 0.00,
    output TEXT
);

-- 8. Budget Tracking
CREATE TABLE IF NOT EXISTS budget_tracking (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
    period_start DATE DEFAULT CURRENT_DATE,
    period_end DATE,
    total_budget NUMERIC(10, 2),
    remaining_budget NUMERIC(10, 2),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. Scheduler Election
CREATE TABLE IF NOT EXISTS scheduler_election (
    id SERIAL PRIMARY KEY,
    role VARCHAR(50) NOT NULL UNIQUE, -- 'leader'
    process_id VARCHAR(50) NOT NULL,
    heartbeat TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
