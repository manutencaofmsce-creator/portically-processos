-- OTP schema V1. Additive migration; no changes to process/Radar data.
CREATE TABLE IF NOT EXISTS auth_otp_challenges (
    id UUID PRIMARY KEY,
    subject_hash TEXT NOT NULL,
    browser_hash TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 5),
    state TEXT NOT NULL CHECK (state IN ('pending','active','used','invalidated','failed','expired','exhausted')),
    CHECK (expires_at > created_at)
);
CREATE INDEX IF NOT EXISTS auth_otp_browser_idx ON auth_otp_challenges(browser_hash, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS auth_otp_active_idx ON auth_otp_challenges(browser_hash) WHERE state = 'active';
CREATE TABLE IF NOT EXISTS auth_rate_events (
    id BIGSERIAL PRIMARY KEY,
    scope TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS auth_rate_scope_idx ON auth_rate_events(scope, occurred_at);
CREATE TABLE IF NOT EXISTS auth_events (
    id BIGSERIAL PRIMARY KEY,
    event TEXT NOT NULL,
    subject_hash TEXT NOT NULL,
    client_hash TEXT NOT NULL,
    challenge_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS auth_events_time_idx ON auth_events(created_at);
