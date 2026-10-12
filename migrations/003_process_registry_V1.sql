-- Additive: legacy tables/bundles and their rows remain untouched.
CREATE TABLE IF NOT EXISTS encrypted_process_registry (
 id UUID PRIMARY KEY,
 cnj_hash TEXT NOT NULL UNIQUE,
 payload_cipher TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 1,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS encrypted_process_events (
 id BIGSERIAL PRIMARY KEY,
 process_id UUID NOT NULL REFERENCES encrypted_process_registry(id),
 payload_cipher TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
