-- Migration 004: CapCut-level Editor Extensions
-- Adds keyframes, overlays, playback state, and audio ducking to edit_states

-- New JSONB columns for CapCut-level features
ALTER TABLE edit_states ADD COLUMN IF NOT EXISTS keyframes JSONB DEFAULT '[]';
ALTER TABLE edit_states ADD COLUMN IF NOT EXISTS overlays JSONB DEFAULT '[]';
ALTER TABLE edit_states ADD COLUMN IF NOT EXISTS playback JSONB DEFAULT '{}';
ALTER TABLE edit_states ADD COLUMN IF NOT EXISTS audio_ducking JSONB DEFAULT NULL;

-- Extend existing JSONB columns with new fields
-- timeline segments now support: reversed, opacity, rotation, volume, freeze_frame, crop
-- effects now support: blur_effects, shake_effects, glow_effects, vignette_effects, grain_effects
-- audio_tracks now support: fade_in, fade_out, loop, detached
-- metadata now supports: aspect_ratio, auto_reframe

-- Index for faster keyframe lookups
CREATE INDEX IF NOT EXISTS idx_edit_states_keyframes ON edit_states USING GIN (keyframes);
CREATE INDEX IF NOT EXISTS idx_edit_states_overlays ON edit_states USING GIN (overlays);

-- Comment for documentation
COMMENT ON COLUMN edit_states.keyframes IS 'Keyframe animations for clip properties (zoom, opacity, position, etc)';
COMMENT ON COLUMN edit_states.overlays IS 'Image, sticker, GIF, and text overlays on the timeline';
COMMENT ON COLUMN edit_states.playback IS 'Playback state (playhead position, speed, loop regions, markers)';
COMMENT ON COLUMN edit_states.audio_ducking IS 'Audio ducking configuration (lower music when voice speaks)';
