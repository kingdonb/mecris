CREATE TABLE IF NOT EXISTS jet_divergence (
    id SERIAL PRIMARY KEY,
    component_name TEXT NOT NULL,
    user_id TEXT NOT NULL,
    source_result JSONB,
    jet_result JSONB,
    input_params JSONB,
    detected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
