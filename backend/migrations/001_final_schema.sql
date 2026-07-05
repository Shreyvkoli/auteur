-- ============================================================
-- Auteur — Final Schema Migration
-- Run this in your NeonDB / Supabase SQL editor
-- ============================================================

-- Enable pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── Users ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email        TEXT UNIQUE NOT NULL,
  name         TEXT,
  avatar_url   TEXT,
  plan         TEXT DEFAULT 'free',   -- 'free' | 'creator' | 'pro'
  videos_used  INTEGER DEFAULT 0,
  style_dna    JSONB,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Videos ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS videos (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              UUID REFERENCES users(id) ON DELETE CASCADE,
  cloudinary_url       TEXT,
  cloudinary_public_id TEXT,
  duration             FLOAT DEFAULT 0,
  status               TEXT DEFAULT 'uploading',
  -- 'uploading' | 'uploaded' | 'downloading' | 'processed' | 'failed'
  transcript           JSONB,   -- [{word, start, end}]
  created_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_videos_user ON videos(user_id);

-- ── Edit Jobs ─────────────────────────────────────────────────────────────────
-- One job = one perfect edit (one version_type chosen by creator)
CREATE TABLE IF NOT EXISTS edit_jobs (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID REFERENCES users(id) ON DELETE CASCADE,
  video_id          UUID REFERENCES videos(id) ON DELETE SET NULL,
  prompt            TEXT,
  version_type      TEXT,   -- 'funny' | 'viral' | 'serious'
  ref_style_profile JSONB,  -- Style JSON from /style/analyze-ref
  edit_plan         JSONB,  -- GPT-4o generated plan
  status            TEXT DEFAULT 'queued',
  -- 'queued' | 'transcribing' | 'generating_plan' | 'rendering' | 'finalizing' | 'completed' | 'failed'
  progress          INTEGER DEFAULT 0,   -- 0-100
  error             TEXT,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_edit_jobs_user ON edit_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_edit_jobs_status ON edit_jobs(status);

-- ── Output Videos ─────────────────────────────────────────────────────────────
-- The final rendered video for a job
CREATE TABLE IF NOT EXISTS output_videos (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id               UUID REFERENCES edit_jobs(id) ON DELETE CASCADE,
  version_type         TEXT,
  cloudinary_url       TEXT,
  cloudinary_public_id TEXT,
  edit_plan            JSONB,   -- The plan used to render this output
  created_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_output_videos_job ON output_videos(job_id);

-- ── Iterations (Vibe Refinement History) ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS iterations (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id            UUID REFERENCES edit_jobs(id) ON DELETE CASCADE,
  version           TEXT,
  refinement_prompt TEXT,
  updated_plan      JSONB,
  output_url        TEXT,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_iterations_job ON iterations(job_id);

-- ── Vault Items ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vault_items (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              UUID REFERENCES users(id) ON DELETE CASCADE,
  type                 TEXT,   -- 'meme' | 'sound' | 'music' | 'preset'
  name                 TEXT NOT NULL,
  cloudinary_url       TEXT,
  cloudinary_public_id TEXT,
  created_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vault_user ON vault_items(user_id);

-- ── Style Profiles ────────────────────────────────────────────────────────────
-- Style profiles extracted from reference YouTube videos
CREATE TABLE IF NOT EXISTS style_profiles (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
  source_url TEXT,
  style_json JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_style_profiles_user ON style_profiles(user_id);

-- ============================================================
-- Row Level Security (if using Supabase)
-- ============================================================
ALTER TABLE users          ENABLE ROW LEVEL SECURITY;
ALTER TABLE videos         ENABLE ROW LEVEL SECURITY;
ALTER TABLE edit_jobs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE output_videos  ENABLE ROW LEVEL SECURITY;
ALTER TABLE iterations     ENABLE ROW LEVEL SECURITY;
ALTER TABLE vault_items    ENABLE ROW LEVEL SECURITY;
ALTER TABLE style_profiles ENABLE ROW LEVEL SECURITY;

-- Service role has full access (backend uses service_role_key)
CREATE POLICY "service_role_all" ON users          FOR ALL USING (true);
CREATE POLICY "service_role_all" ON videos         FOR ALL USING (true);
CREATE POLICY "service_role_all" ON edit_jobs      FOR ALL USING (true);
CREATE POLICY "service_role_all" ON output_videos  FOR ALL USING (true);
CREATE POLICY "service_role_all" ON iterations     FOR ALL USING (true);
CREATE POLICY "service_role_all" ON vault_items    FOR ALL USING (true);
CREATE POLICY "service_role_all" ON style_profiles FOR ALL USING (true);
