-- Migration 003: Intelligence Layer Schema
-- Adds: metrics table, version history support, vault intelligence fields

-- Internal metrics tracking
CREATE TABLE IF NOT EXISTS metrics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_type TEXT NOT NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id UUID REFERENCES edit_jobs(id) ON DELETE SET NULL,
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metrics_event_type ON metrics(event_type);
CREATE INDEX IF NOT EXISTS idx_metrics_user_id ON metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_metrics_created_at ON metrics(created_at);

-- Edit intelligence metrics (per edit plan generation)
CREATE TABLE IF NOT EXISTS edit_intelligence_metrics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    project_id UUID REFERENCES edit_jobs(id) ON DELETE SET NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    passes_completed INT DEFAULT 4,
    story_confidence FLOAT DEFAULT 6.0,
    quality_scores JSONB DEFAULT '{}',
    elapsed_seconds FLOAT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_intel_metrics_project ON edit_intelligence_metrics(project_id);

-- Add version_history column to edit_states (if not exists)
DO $$ BEGIN
    ALTER TABLE edit_states ADD COLUMN IF NOT EXISTS version_history JSONB DEFAULT '[]';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE edit_states ADD COLUMN IF NOT EXISTS undo_stack JSONB DEFAULT '[]';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE edit_states ADD COLUMN IF NOT EXISTS redo_stack JSONB DEFAULT '[]';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Add pacing_curve and caption_density_pattern to creator_memories (if not exists)
DO $$ BEGIN
    ALTER TABLE creator_memories ADD COLUMN IF NOT EXISTS pacing_curve JSONB DEFAULT '[]';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE creator_memories ADD COLUMN IF NOT EXISTS caption_density_pattern JSONB DEFAULT '[]';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE creator_memories ADD COLUMN IF NOT EXISTS editing_frequency JSONB DEFAULT '[]';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Add relevance_score to vault_clips (if not exists)
DO $$ BEGIN
    ALTER TABLE vault_clips ADD COLUMN IF NOT EXISTS relevance_score FLOAT DEFAULT 0;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE vault_clips ADD COLUMN IF NOT EXISTS relevance_reason TEXT DEFAULT '';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Add story_confidence to vlog analysis results (via edit_jobs if needed)
DO $$ BEGIN
    ALTER TABLE edit_jobs ADD COLUMN IF NOT EXISTS story_confidence FLOAT DEFAULT 0;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- RLS policies for metrics (users can only see their own)
ALTER TABLE metrics ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    CREATE POLICY "Users can view own metrics" ON metrics
        FOR SELECT USING (user_id = auth.uid());
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE POLICY "Users can insert own metrics" ON metrics
        FOR INSERT WITH CHECK (user_id = auth.uid());
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE POLICY "Service role can manage all metrics" ON metrics
        FOR ALL USING (auth.role() = 'service_role');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- RLS for edit_intelligence_metrics
ALTER TABLE edit_intelligence_metrics ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    CREATE POLICY "Users can view own intel metrics" ON edit_intelligence_metrics
        FOR SELECT USING (user_id = auth.uid());
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE POLICY "Users can insert own intel metrics" ON edit_intelligence_metrics
        FOR INSERT WITH CHECK (user_id = auth.uid());
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE POLICY "Service role can manage all intel metrics" ON edit_intelligence_metrics
        FOR ALL USING (auth.role() = 'service_role');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
