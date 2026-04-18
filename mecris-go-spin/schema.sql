-- Neon PostgreSQL Schema for Mecris-Go

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    pocket_id_sub VARCHAR(255) PRIMARY KEY, -- From Pocket ID JWT
    familiar_id VARCHAR(255) UNIQUE,        -- e.g., 'yebyen'
    beeminder_token_encrypted TEXT,
    beeminder_user_encrypted TEXT,          -- Encrypted PII (changed from plaintext beeminder_user)
    beeminder_goal VARCHAR(255) DEFAULT 'bike',
    clozemaster_email_encrypted TEXT,
    clozemaster_password_encrypted TEXT,
    phone_number_encrypted TEXT,            -- Encrypted PII for Twilio delivery
    phone_verified BOOLEAN DEFAULT FALSE,   -- Set true after SMS verification flow completes
    vacation_mode_until TIMESTAMPTZ,        -- NULL = Boris & Fiona mode; timestamp = Generic Physical mode
    location_lat DOUBLE PRECISION,          -- User's latitude for per-user weather checks (nullable)
    location_lon DOUBLE PRECISION,          -- User's longitude for per-user weather checks (nullable)
    notification_prefs JSONB DEFAULT '{}',  -- Tier settings, sleep windows, thresholds
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
    status VARCHAR(50),
    error_msg TEXT,
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
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost NUMERIC(10, 6) DEFAULT 0.00,
    summary TEXT,
    outcome VARCHAR(50) DEFAULT 'success',
    container_id VARCHAR(100) DEFAULT 'local'
);

-- 8. Token Bank
CREATE TABLE IF NOT EXISTS token_bank (
    user_id TEXT PRIMARY KEY REFERENCES users(pocket_id_sub),
    available_tokens BIGINT NOT NULL DEFAULT 0,
    monthly_limit BIGINT NOT NULL DEFAULT 1000000,
    last_refill TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. Budget Tracking
CREATE TABLE IF NOT EXISTS budget_tracking (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
    total_budget DOUBLE PRECISION NOT NULL DEFAULT 0,
    remaining_budget DOUBLE PRECISION NOT NULL DEFAULT 0,
    budget_period_start TEXT NOT NULL DEFAULT '2025-08-06',
    budget_period_end TEXT NOT NULL DEFAULT '2025-09-30',
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 9. Scheduler Election (multi-user: unique per user+role)
CREATE TABLE IF NOT EXISTS scheduler_election (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,  -- 'leader', 'android_client'
    process_id VARCHAR(50) NOT NULL,
    heartbeat TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, role)
);

-- 10. Phone Verifications (SMS 6-digit code flow)
CREATE TABLE IF NOT EXISTS phone_verifications (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
    code_hash TEXT NOT NULL,            -- SHA1 of the 6-digit code
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    attempts INTEGER DEFAULT 0,
    UNIQUE (user_id)                    -- one pending verification per user at a time
);
