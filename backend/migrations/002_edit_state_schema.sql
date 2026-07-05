-- ============================================================
-- Auteur — Edit State + Quality + Creator Memory Schema
-- Run after 001_final_schema.sql
-- ============================================================

-- ── Edit States ──────────────────────────────────────────────────────────────
-- Source of truth for every edit — timeline, clips, captions, audio, effects
CREATE TABLE IF NOT EXISTS edit_states (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id            UUID REFERENCES edit_jobs(id) ON DELETE CASCADE UNIQUE,
  user_id           UUID REFERENCES users(id) ON DELETE CASCADE,
  video_id          UUID REFERENCES videos(id) ON DELETE SET NULL,
  mode              TEXT DEFAULT 'reels',       -- 'reels' | 'vlog'
  timeline          JSONB DEFAULT '[]'::jsonb,  -- ordered list of timeline segments
  clips             JSONB DEFAULT '[]'::jsonb,  -- all source clips with metadata
  captions          JSONB DEFAULT '[]'::jsonb,  -- caption track entries
  audio_tracks      JSONB DEFAULT '[]'::jsonb,  -- music + sound effect tracks
  effects           JSONB DEFAULT '{}'::jsonb,  -- color_grade, transitions
  metadata          JSONB DEFAULT '{}'::jsonb,  -- duration, fps, dimensions
  dirty_segments    JSONB DEFAULT '[]'::jsonb,  -- timestamp ranges needing re-render
  version           INTEGER DEFAULT 1,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_edit_states_user ON edit_states(user_id);
CREATE INDEX IF NOT EXISTS idx_edit_states_job  ON edit_states(job_id);

-- ── Quality Scores ──────────────────────────────────────────────────────────
-- Per-job quality evaluation results
CREATE TABLE IF NOT EXISTS edit_quality_scores (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id            UUID REFERENCES edit_jobs(id) ON DELETE CASCADE,
  user_id           UUID REFERENCES users(id) ON DELETE CASCADE,
  hook_strength     INTEGER DEFAULT 0,        -- 1-10
  pacing_score      INTEGER DEFAULT 0,        -- 1-10
  engagement_score  INTEGER DEFAULT 0,        -- 1-10
  overall_score     FLOAT DEFAULT 0,           -- weighted avg
  passed            BOOLEAN DEFAULT FALSE,     -- passed threshold?
  details           JSONB DEFAULT '{}'::jsonb, -- per-criterion details
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quality_job ON edit_quality_scores(job_id);

-- ── Creator Memory ──────────────────────────────────────────────────────────
-- Per-user aggregated style preferences — the moat
CREATE TABLE IF NOT EXISTS creator_memories (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
  preferred_pacing  TEXT DEFAULT 'medium',      -- 'slow' | 'medium' | 'fast'
  caption_style     TEXT DEFAULT 'bold_white_center',
  music_vibe        TEXT DEFAULT 'lo-fi',
  color_grade       TEXT DEFAULT 'warm',
  energy_level      INTEGER DEFAULT 5,          -- 1-10
  avg_cut_duration  FLOAT DEFAULT 3.0,
  hook_pattern      TEXT DEFAULT 'question hook',
  vault_usage_freq  TEXT DEFAULT 'low',
  style_json        JSONB DEFAULT '{}'::jsonb,
  edit_count        INTEGER DEFAULT 0,
  last_used         TIMESTAMPTZ DEFAULT NOW(),
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_creator_memory_user ON creator_memories(user_id);

-- ── Segment Cache ───────────────────────────────────────────────────────────
-- Cached rendered segments for partial re-render
CREATE TABLE IF NOT EXISTS segment_cache (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id            UUID REFERENCES edit_jobs(id) ON DELETE CASCADE,
  user_id           UUID REFERENCES users(id) ON DELETE CASCADE,
  segment_key       TEXT NOT NULL,              -- "clip_{id}_step_{name}"
  clip_id           TEXT,
  step_name         TEXT,                       -- 'cut' | 'zoom' | 'captions' | 'grade'
  start_time        FLOAT,
  end_time          FLOAT,
  cloudinary_url    TEXT,
  cloudinary_public_id TEXT,
  hash              TEXT,                       -- content hash for invalidation
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_segment_cache_job ON segment_cache(job_id);
CREATE INDEX IF NOT EXISTS idx_segment_cache_key ON segment_cache(segment_key);

-- ── Vault Clip Timestamps ──────────────────────────────────────────────────
-- Timestamped clips within vault items for smart suggestions
CREATE TABLE IF NOT EXISTS vault_clips (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vault_item_id     UUID REFERENCES vault_items(id) ON DELETE CASCADE,
  user_id           UUID REFERENCES users(id) ON DELETE CASCADE,
  start_time        FLOAT NOT NULL,
  end_time          FLOAT NOT NULL,
  label             TEXT,                       -- 'intro' | 'highlight' | 'funny' | 'transition'
  tags              TEXT[] DEFAULT '{}',
  thumbnail_url     TEXT,
  duration          FLOAT,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vault_clips_item ON vault_clips(vault_item_id);

-- ============================================================
-- RLS
-- ============================================================
ALTER TABLE edit_states        ENABLE ROW LEVEL SECURITY;
ALTER TABLE edit_quality_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE creator_memories    ENABLE ROW LEVEL SECURITY;
ALTER TABLE segment_cache       ENABLE ROW LEVEL SECURITY;
ALTER TABLE vault_clips         ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON edit_states        FOR ALL USING (true);
CREATE POLICY "service_role_all" ON edit_quality_scores FOR ALL USING (true);
CREATE POLICY "service_role_all" ON creator_memories    FOR ALL USING (true);
CREATE POLICY "service_role_all" ON segment_cache       FOR ALL USING (true);
CREATE POLICY "service_role_all" ON vault_clips         FOR ALL USING (true);
