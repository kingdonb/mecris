-- Migration 004: Add per-user location columns for per-user OpenWeather weather checks.
--
-- Context: yebyen/mecris#156
-- Previously, openweather_lat and openweather_lon were global Spin variables, meaning
-- all users shared the same weather coordinates. This migration adds nullable columns
-- so each user can have their own location for accurate per-user weather checks.
-- The global Spin variables remain as a fallback for backward compatibility.
--
-- Run: psql $NEON_DB_URL -f scripts/migrations/004_user_location.sql

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS location_lat DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS location_lon DOUBLE PRECISION;

COMMENT ON COLUMN users.location_lat IS 'Latitude for per-user OpenWeather weather checks. NULL falls back to global Spin variables.';
COMMENT ON COLUMN users.location_lon IS 'Longitude for per-user OpenWeather weather checks. NULL falls back to global Spin variables.';
