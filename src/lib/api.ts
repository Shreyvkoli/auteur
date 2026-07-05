/**
 * Centralized API client for Auteur backend.
 * All fetch calls go through here — base URL from env.
 */

export const BASE = import.meta.env.VITE_API_URL || (typeof window !== 'undefined' ? `${window.location.origin}/api` : '/api');

// ── Auth token helper ─────────────────────────────────────────────────────────

function getToken(): string | null {
  return localStorage.getItem("auteur_token");
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  isForm = false,
  timeoutMs = 30000,
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(!isForm ? { "Content-Type": "application/json" } : {}),
  };

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: isForm ? (body as FormData) : body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `API error ${res.status}`);
    }

    return res.json() as Promise<T>;
  } finally {
    clearTimeout(timeout);
  }
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface StyleBadge {
  icon: string;
  label: string;
  value: string;
}

export interface StyleAnalysisResult {
  profile_id: string;
  style_json: Record<string, unknown>;
  badges: StyleBadge[];
}

export interface EditJobResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface OutputVideo {
  version_type: string;
  url: string;
  id: string;
}

export interface ChangelogEntry {
  original_duration: number;
  edited_duration: number;
  total_removed: number;
  cuts: {
    total: number;
    avg_cut_duration: number;
    num_fillers_removed: number;
    num_silences_removed: number;
  };
  captions: {
    total: number;
    style: string;
  };
  zoom_moments: {
    total: number;
    positions: { time: number; scale: number }[];
  };
  meme_sounds: {
    total: number;
    positions: { time: number; sound: string }[];
  };
  music_vibe: string;
  color_grade: string;
  style_match_score: number;
  ref_breakdown: {
    ref_index: number;
    contributed: {
      music_vibe: string;
      color_grade: string;
      caption_style: string;
      hook_pattern: string;
      energy_level: number;
    };
    filename?: string;
  }[];
  edit_events?: EditEvent[];
}

export interface EditEvent {
  timestamp: number;
  type: "cut" | "caption" | "zoom" | "meme_sound" | "silence_removed" | "filler_removed";
  subtype: string;
  description: string;
  duration?: number;
  content?: string;
  scale?: number;
  sound?: string;
  count?: number;
  enabled: boolean;
}

export interface JobStatus {
  job_id: string;
  status: string;
  progress: number;
  message: string;
  error?: string;
  output_video?: OutputVideo;
  changelog?: ChangelogEntry;
}

export interface VaultItem {
  id: string;
  type: string;
  name: string;
  cloudinary_url?: string;
  r2_url: string;
  created_at: string;
}

export interface VaultListResponse {
  items: VaultItem[];
  total: number;
}

export interface VideoRecord {
  id: string;
  cloudinary_url: string;
  duration: number;
  status: string;
  created_at: string;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const auth = {
  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string }>("POST", "/auth/signin", {
      email,
      password,
    }),

  register: (email: string, password: string, name: string) =>
    request<{ access_token: string }>("POST", "/auth/signup", { email, password, name }),

  me: () => request<{ id: string; email: string; name: string; plan: string }>("GET", "/auth/me"),

  signout: () => request<{ message: string }>("POST", "/auth/signout"),
};

// ── Video ─────────────────────────────────────────────────────────────────────

export const video = {
  /**
   * Step 1: Get Cloudinary signed upload params.
   * Step 2: Upload file directly to Cloudinary from browser.
   * Step 3: Call complete() with the result.
   */
  initUpload: (filename: string, contentType: string, size: number) =>
    request<{
      video_id: string;
      cloudinary_upload_url: string;
      cloud_name: string;
      api_key: string;
      timestamp: number;
      signature: string;
      folder: string;
    }>("POST", "/video/upload/init", { filename, content_type: contentType, size }),

  /** Upload file directly to Cloudinary. Returns public_id + secure_url. */
  uploadToCloudinary: async (
    file: File,
    params: {
      cloudinary_upload_url: string;
      api_key: string;
      timestamp: number;
      signature: string;
      folder: string;
    },
    onProgress?: (pct: number) => void,
  ): Promise<{ public_id: string; secure_url: string }> => {
    return new Promise((resolve, reject) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("api_key", params.api_key);
      fd.append("timestamp", String(params.timestamp));
      fd.append("signature", params.signature);
      fd.append("folder", params.folder);

      const xhr = new XMLHttpRequest();
      xhr.open("POST", params.cloudinary_upload_url);

      if (onProgress) {
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
        };
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          const data = JSON.parse(xhr.responseText);
          resolve({ public_id: data.public_id, secure_url: data.secure_url });
        } else {
          reject(new Error(`Cloudinary upload failed: ${xhr.statusText}`));
        }
      };
      xhr.onerror = () => reject(new Error("Upload network error"));
      xhr.send(fd);
    });
  },

  completeUpload: (videoId: string, publicId: string, url: string) => {
    const fd = new FormData();
    fd.append("video_id", videoId);
    fd.append("cloudinary_public_id", publicId);
    fd.append("cloudinary_url", url);
    return request<{ video_id: string; duration: number; status: string }>(
      "POST",
      "/video/upload/complete",
      fd,
      true,
    );
  },

  list: () => request<VideoRecord[]>("GET", "/video/"),
  get: (id: string) => request<VideoRecord>("GET", `/video/${id}`),
  delete: (id: string) => request<{ message: string }>("DELETE", `/video/${id}`),

  importYoutube: (url: string) =>
    request<{ video_id: string; duration: number; status: string }>("POST", "/video/youtube", {
      url,
    }),
};

// ── Style ─────────────────────────────────────────────────────────────────────

export const style = {
  /** Analyze a reference YouTube video — returns style JSON + badges. */
  analyzeRef: (url: string) => request<StyleAnalysisResult>("POST", "/style/analyze-ref", { url }),

  profiles: () => request<unknown[]>("GET", "/style/profiles"),
  dna: () => request<unknown>("GET", "/style/dna"),
};

// ── Edit ──────────────────────────────────────────────────────────────────────

export const edit = {
  /** Submit an edit job — returns job_id for polling. */
  create: (payload: {
    video_id: string;
    prompt: string;
    version_type: string;
    mode?: string;
    ref_video_ids?: string[];
    style_profile?: Record<string, unknown> | null;
    vault_items?: VaultItem[];
  }) => request<EditJobResponse>("POST", "/edit/", payload),

  /** Poll job status. */
  status: (jobId: string) => request<JobStatus>("GET", `/edit/${jobId}/status`),

  /** Submit a refinement prompt — returns new job_id. */
  refine: (payload: { job_id: string; version_type: string; refinement_prompt: string; mode?: string }) =>
    request<EditJobResponse>("POST", "/edit/refine", payload),

  history: () => request<unknown[]>("GET", "/edit/history"),
};

// ── Vault ─────────────────────────────────────────────────────────────────────

export const vault = {
  list: (type?: string, limit = 50, offset = 0) =>
    request<VaultListResponse>("GET", `/vault/?limit=${limit}&offset=${offset}${type ? `&type=${type}` : ""}`),

  delete: (id: string) => request<{ message: string }>("DELETE", `/vault/${id}`),

  upload: (file: File, itemType: string, name: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("type", itemType);
    fd.append("name", name);
    return request<VaultItem>("POST", "/vault/", fd, true);
  },
};

// ── Edit State (CapCut-level timeline editor) ─────────────────────────────────

export interface EditState {
  id: string;
  job_id: string;
  user_id: string;
  video_id: string;
  mode: string;
  timeline: TimelineSegment[];
  clips: ClipMetadata[];
  captions: CaptionEntry[];
  audio_tracks: AudioTrack[];
  effects: EditEffects;
  metadata: EditMetadata;
  dirty_segments: { start: number; end: number }[];
  version: number;
  version_history: VersionEntry[];
  undo_stack: PatchAction[];
  redo_stack: PatchAction[];
  keyframes: Keyframe[];
  overlays: Overlay[];
  playback: PlaybackState;
  audio_ducking: AudioDucking | null;
}

export interface TimelineSegment {
  id: string;
  clip_id: string;
  source_start: number;
  source_end: number;
  timeline_start: number;
  timeline_end: number;
  speed: number;
  reversed: boolean;
  opacity: number;
  rotation: number;
  volume: number;
  freeze_frame: { at: number; duration: number } | null;
  crop: { x: number; y: number; width: number; height: number } | null;
}

export interface ClipMetadata {
  id: string;
  video_id: string;
  source_url: string;
  duration: number;
  fps: number;
  width: number;
  height: number;
}

export interface CaptionEntry {
  id: string;
  text: string;
  start: number;
  end: number;
  style: string;
}

export interface AudioTrack {
  id: string;
  type: string;
  source_url: string;
  start: number;
  duration: number;
  volume: number;
  name: string;
  fade_in: number;
  fade_out: number;
  loop: boolean;
  detached: boolean;
}

export interface EditEffects {
  color_grade: string;
  transitions: Transition[];
  blur_background: boolean;
  brightness: number | null;
  contrast: number | null;
  saturation: number | null;
  blur_effects: BlurEffect[];
  shake_effects: ShakeEffect[];
  glow_effects: GlowEffect[];
  vignette_effects: VignetteEffect[];
  grain_effects: GrainEffect[];
}

export interface Transition {
  id: string;
  type: string;
  transition: string;
  duration: number;
  between: [string, string];
}

export interface EditMetadata {
  total_duration: number;
  fps: number;
  width: number;
  height: number;
  mode: string;
  aspect_ratio: string;
  auto_reframe: boolean;
}

export interface Keyframe {
  id: string;
  clip_id: string;
  property: string;
  time: number;
  value: number;
  interpolation: string;
  easing_power: number;
}

export interface Overlay {
  id: string;
  type: string;
  source_url: string;
  text?: string;
  name?: string;
  start: number;
  end: number;
  x: number;
  y: number;
  scale: number;
  rotation: number;
  opacity: number;
  animation: string;
  animation_duration: number;
  layer: number;
  style?: Record<string, unknown>;
}

export interface PlaybackState {
  playhead: number;
  playing: boolean;
  speed: number;
  total_duration: number;
  fps: number;
  loop_start: number | null;
  loop_end: number | null;
  loop_enabled: boolean;
  markers: { time: number; label: string; color: string }[];
}

export interface VersionEntry {
  id: string;
  version_label: string;
  saved_at: string;
}

export interface PatchAction {
  action: string;
  [key: string]: unknown;
}

export interface BlurEffect {
  id: string;
  blur_type: string;
  intensity: number;
  start: number;
  end: number;
}

export interface ShakeEffect {
  id: string;
  intensity: number;
  frequency: number;
  start: number;
  end: number;
}

export interface GlowEffect {
  id: string;
  intensity: number;
  radius: number;
  start: number;
  end: number;
}

export interface VignetteEffect {
  id: string;
  intensity: number;
  start: number;
  end: number;
}

export interface GrainEffect {
  id: string;
  intensity: number;
  start: number;
  end: number;
}

export interface AudioDucking {
  enabled: boolean;
  music_track_id: string;
  voice_track_ids: string[];
  duck_volume: number;
  attack_time: number;
  release_time: number;
}

export interface EditStateResponse {
  state: EditState;
  dirty_ranges: { start: number; end: number }[];
}

export const editState = {
  // ── Core ──
  create: (videoId: string, mode: string = "reels") =>
    request<{ job_id: string; state: EditState; dirty_ranges: { start: number; end: number }[] }>(
      "POST",
      "/edit-state",
      { video_id: videoId, mode },
    ),

  get: (jobId: string) => request<EditStateResponse>("GET", `/edit-state/${jobId}`),

  patch: (jobId: string, actions: PatchAction[]) =>
    request<EditStateResponse>("PATCH", `/edit-state/${jobId}`, { actions }),

  render: (jobId: string) =>
    request<{ job_id: string; output_url: string; message: string }>(
      "POST",
      `/edit-state/${jobId}/render`,
    ),

  prompt: (jobId: string, prompt: string, attachments?: { id: string; type: string; label: string; url: string }[]) =>
    request<{
      job_id: string;
      applied_patches: PatchAction[];
      message: string;
      needs_render: boolean;
    }>("POST", `/edit-state/${jobId}/prompt`, { prompt, attachments }),

  // ── Chat History ──
  chat: {
    list: (jobId: string) =>
      request<{ messages: { role: string; text: string; patchesApplied?: boolean }[] }>(
        "GET", `/edit-state/${jobId}/chat`
      ),
    append: (jobId: string, role: string, text: string, patchesApplied?: boolean) =>
      request<{ messages: { role: string; text: string; patchesApplied?: boolean }[] }>(
        "POST", `/edit-state/${jobId}/chat`, { role, text, patches_applied: patchesApplied }
      ),
  },

  // ── Undo/Redo ──
  undo: (jobId: string) =>
    request<{ state: EditState; undo_remaining: number; redo_remaining: number; message: string }>(
      "POST",
      `/edit-state/${jobId}/undo`,
    ),

  redo: (jobId: string) =>
    request<{ state: EditState; undo_remaining: number; redo_remaining: number; message: string }>(
      "POST",
      `/edit-state/${jobId}/redo`,
    ),

  undoInfo: (jobId: string) =>
    request<{ undo_count: number; redo_count: number }>("GET", `/edit-state/${jobId}/undo-info`),

  // ── Versions ──
  saveVersion: (jobId: string, label?: string) =>
    request<{ versions: VersionEntry[]; current_version: number }>(
      "POST",
      `/edit-state/${jobId}/versions`,
      { label },
    ),

  listVersions: (jobId: string) =>
    request<{ versions: VersionEntry[]; current_version: number }>(
      "GET",
      `/edit-state/${jobId}/versions`,
    ),

  restoreVersion: (jobId: string, versionIndex: number) =>
    request<EditStateResponse>("POST", `/edit-state/${jobId}/versions/${versionIndex}/restore`),

  // ── Preview ──
  previewRender: (jobId: string) =>
    request<{ preview_path: string; duration_seconds: number; message: string }>(
      "POST",
      `/edit-state/${jobId}/preview-render`,
    ),

  preview: (jobId: string) =>
    request<{ job_id: string; output_url: string; version_type: string }>(
      "GET",
      `/edit-state/${jobId}/preview`,
    ),

  diff: (jobId: string, beforeVersion?: number) =>
    request<{
      changes: PatchAction[];
      summary: string;
      total_changes: number;
      stats: Record<string, unknown>;
    }>(
      "GET",
      `/edit-state/${jobId}/diff${beforeVersion !== undefined ? `?before_version=${beforeVersion}` : ""}`,
    ),

  // ── Transitions ──
  addTransition: (
    jobId: string,
    clipA: string,
    clipB: string,
    type: string = "fade",
    duration: number = 0.5,
  ) =>
    request<EditStateResponse>("POST", `/edit-state/${jobId}/transitions`, {
      clip_a_id: clipA,
      clip_b_id: clipB,
      transition_type: type,
      duration,
    }),

  updateTransition: (jobId: string, transitionId: string, type?: string, duration?: number) =>
    request<EditStateResponse>("PUT", `/edit-state/${jobId}/transitions`, {
      transition_id: transitionId,
      transition_type: type,
      duration,
    }),

  removeTransition: (jobId: string, clipA: string, clipB: string) =>
    request<EditStateResponse>("DELETE", `/edit-state/${jobId}/transitions/${clipA}/${clipB}`),

  listTransitions: (jobId: string) =>
    request<{ transitions: Transition[] }>("GET", `/edit-state/${jobId}/transitions`),

  // ── Text Overlays ──
  addTextOverlay: (
    jobId: string,
    data: {
      text: string;
      start: number;
      end: number;
      x?: number;
      y?: number;
      style?: Record<string, unknown>;
      animation?: string;
      animation_duration?: number;
      layer?: number;
    },
  ) => request<EditStateResponse>("POST", `/edit-state/${jobId}/text-overlays`, data),

  updateTextOverlay: (
    jobId: string,
    overlayId: string,
    data: Partial<{
      text: string;
      start: number;
      end: number;
      x: number;
      y: number;
      style: Record<string, unknown>;
      animation: string;
      animation_duration: number;
      layer: number;
    }>,
  ) => request<EditStateResponse>("PATCH", `/edit-state/${jobId}/text-overlays/${overlayId}`, data),

  deleteTextOverlay: (jobId: string, overlayId: string) =>
    request<EditStateResponse>("DELETE", `/edit-state/${jobId}/text-overlays/${overlayId}`),

  listTextOverlays: (jobId: string) =>
    request<{ text_overlays: Overlay[] }>("GET", `/edit-state/${jobId}/text-overlays`),

  // ── Image/GIF Overlays ──
  addOverlay: (
    jobId: string,
    data: {
      overlay_type: string;
      source_url: string;
      start: number;
      end: number;
      x?: number;
      y?: number;
      scale?: number;
      rotation?: number;
      opacity?: number;
      animation?: string;
      layer?: number;
      name?: string;
    },
  ) => request<EditStateResponse>("POST", `/edit-state/${jobId}/overlays`, data),

  updateOverlay: (
    jobId: string,
    overlayId: string,
    data: Partial<{
      source_url: string;
      start: number;
      end: number;
      x: number;
      y: number;
      scale: number;
      rotation: number;
      opacity: number;
      animation: string;
      layer: number;
    }>,
  ) => request<EditStateResponse>("PATCH", `/edit-state/${jobId}/overlays/${overlayId}`, data),

  deleteOverlay: (jobId: string, overlayId: string) =>
    request<EditStateResponse>("DELETE", `/edit-state/${jobId}/overlays/${overlayId}`),

  listOverlays: (jobId: string) =>
    request<{ overlays: Overlay[] }>("GET", `/edit-state/${jobId}/overlays`),

  // ── Keyframes ──
  addKeyframe: (
    jobId: string,
    data: {
      clip_id: string;
      property: string;
      time: number;
      value: number;
      interpolation?: string;
      easing_power?: number;
    },
  ) => request<EditStateResponse>("POST", `/edit-state/${jobId}/keyframes`, data),

  batchKeyframes: (
    jobId: string,
    clipId: string,
    property: string,
    values: { time: number; value: number }[],
  ) =>
    request<EditStateResponse>("POST", `/edit-state/${jobId}/keyframes/batch`, {
      clip_id: clipId,
      property,
      values,
    }),

  updateKeyframe: (
    jobId: string,
    keyframeId: string,
    data: Partial<{
      time: number;
      value: number;
      interpolation: string;
      easing_power: number;
    }>,
  ) => request<EditStateResponse>("PATCH", `/edit-state/${jobId}/keyframes/${keyframeId}`, data),

  deleteKeyframe: (jobId: string, keyframeId: string) =>
    request<EditStateResponse>("DELETE", `/edit-state/${jobId}/keyframes/${keyframeId}`),

  listKeyframes: (jobId: string, clipId?: string, property?: string) => {
    const params = new URLSearchParams();
    if (clipId) params.set("clip_id", clipId);
    if (property) params.set("property", property);
    const qs = params.toString();
    return request<{ keyframes: Keyframe[] }>(
      "GET",
      `/edit-state/${jobId}/keyframes${qs ? `?${qs}` : ""}`,
    );
  },

  // ── Audio ──
  addAudioTrack: (
    jobId: string,
    data: {
      source_url: string;
      track_type?: string;
      start?: number;
      duration?: number;
      volume?: number;
      name?: string;
      fade_in?: number;
      fade_out?: number;
      loop?: boolean;
    },
  ) => request<EditStateResponse>("POST", `/edit-state/${jobId}/audio`, data),

  updateAudioTrack: (
    jobId: string,
    trackId: string,
    data: Partial<{
      volume: number;
      source_url: string;
      start: number;
      fade_in: number;
      fade_out: number;
      loop: boolean;
      name: string;
    }>,
  ) => request<EditStateResponse>("PATCH", `/edit-state/${jobId}/audio/${trackId}`, data),

  deleteAudioTrack: (jobId: string, trackId: string) =>
    request<EditStateResponse>("DELETE", `/edit-state/${jobId}/audio/${trackId}`),

  detachAudio: (jobId: string, clipId: string) =>
    request<EditStateResponse>("POST", `/edit-state/${jobId}/audio/detach`, { clip_id: clipId }),

  setDucking: (
    jobId: string,
    data: {
      music_track_id: string;
      voice_track_ids: string[];
      duck_volume?: number;
      attack?: number;
      release?: number;
    },
  ) => request<EditStateResponse>("POST", `/edit-state/${jobId}/audio/ducking`, data),

  listAudioTracks: (jobId: string) =>
    request<{ audio_tracks: AudioTrack[] }>("GET", `/edit-state/${jobId}/audio`),

  // ── Effects ──
  addBlurEffect: (
    jobId: string,
    data: {
      blur_type?: string;
      intensity?: number;
      start?: number;
      end?: number;
    },
  ) => request<EditStateResponse>("POST", `/edit-state/${jobId}/effects/blur`, data),

  addShakeEffect: (
    jobId: string,
    data: {
      intensity?: number;
      frequency?: number;
      start?: number;
      end?: number;
    },
  ) => request<EditStateResponse>("POST", `/edit-state/${jobId}/effects/shake`, data),

  addGlowEffect: (
    jobId: string,
    data: {
      intensity?: number;
      radius?: number;
      start?: number;
      end?: number;
    },
  ) => request<EditStateResponse>("POST", `/edit-state/${jobId}/effects/glow`, data),

  addVignette: (
    jobId: string,
    data: {
      intensity?: number;
      start?: number;
      end?: number;
    },
  ) => request<EditStateResponse>("POST", `/edit-state/${jobId}/effects/vignette`, data),

  removeEffect: (jobId: string, effectId: string) =>
    request<EditStateResponse>("DELETE", `/edit-state/${jobId}/effects/${effectId}`),

  setColorGrade: (
    jobId: string,
    data: {
      grade?: string;
      brightness?: number;
      contrast?: number;
      saturation?: number;
      hue?: number;
      temperature?: number;
      start?: number;
      end?: number;
    },
  ) => request<EditStateResponse>("PATCH", `/edit-state/${jobId}/effects/color`, data),

  listEffects: (jobId: string) =>
    request<{ effects: EditEffects }>("GET", `/edit-state/${jobId}/effects`),

  // ── Aspect Ratio ──
  setAspectRatio: (jobId: string, ratio: string, autoReframe?: boolean) =>
    request<EditStateResponse>("PATCH", `/edit-state/${jobId}/aspect-ratio`, {
      aspect_ratio: ratio,
      auto_reframe: autoReframe ?? false,
    }),

  getAspectRatio: (jobId: string) =>
    request<{ current: Record<string, unknown>; available: Record<string, string> }>(
      "GET",
      `/edit-state/${jobId}/aspect-ratio`,
    ),

  // ── Playback ──
  getPlayback: (jobId: string) =>
    request<{ playback: PlaybackState }>("GET", `/edit-state/${jobId}/playback`),

  seek: (jobId: string, time: number) =>
    request<{ playback: PlaybackState }>("POST", `/edit-state/${jobId}/playback/seek`, { time }),

  step: (jobId: string, frames: number) =>
    request<{ playback: PlaybackState }>("POST", `/edit-state/${jobId}/playback/step`, { frames }),

  setPlaybackSpeed: (jobId: string, speed: number) =>
    request<{ playback: PlaybackState }>("POST", `/edit-state/${jobId}/playback/speed`, { speed }),

  setLoop: (jobId: string, data: { start?: number; end?: number; enabled?: boolean }) =>
    request<{ playback: PlaybackState }>("POST", `/edit-state/${jobId}/playback/loop`, data),

  getFrameInfo: (jobId: string, time: number) =>
    request<{ frame: Record<string, unknown> }>(
      "GET",
      `/edit-state/${jobId}/playback/frame?time=${time}`,
    ),

  // ── Export ──
  export: (jobId: string) =>
    request<{ job_id: string; output_url: string; download_url: string; message: string }>(
      "POST",
      `/edit-state/${jobId}/export`,
    ),

  // ── Auto Edit ──
  autoEdit: (jobId: string) =>
    request<{ job_id: string; message: string; applied_patches: string[] }>(
      "POST",
      `/edit-state/${jobId}/auto-edit`,
    ),

  // ── Highlights ──
  detectHighlights: (jobId: string, maxClips?: number) =>
    request<{
      highlights: { start: number; end: number; score: number }[];
      total_duration: number;
    }>("POST", `/edit-state/${jobId}/highlights`, { max_clips: maxClips || 10 }),

  // ── Memory ──
  saveMemory: (jobId: string) =>
    request<{ message: string }>("POST", `/edit-state/${jobId}/memory/auto-save`),
};

// ── Jobs ──────────────────────────────────────────────────────────────────────

export const jobs = {
  list: () => request<unknown[]>("GET", "/jobs/"),
  get: (jobId: string) => request<unknown>("GET", `/jobs/${jobId}`),
  retry: (jobId: string) =>
    request<{ message: string; job_id: string }>("POST", `/jobs/${jobId}/retry`),
  cancel: (jobId: string) => request<{ message: string }>("DELETE", `/jobs/${jobId}`),
};

// ── Full upload flow (convenience) ───────────────────────────────────────────

export async function uploadVideo(
  file: File,
  onProgress?: (stage: string, pct: number) => void,
  trimStart?: number,
  trimEnd?: number,
): Promise<{ video_id: string; duration: number }> {
  onProgress?.("Initialising upload...", 0);

  // 1. Get signed params
  const init = await video.initUpload(file.name, file.type, file.size);

  // Dev mode: upload directly to backend (no Cloudinary)
  if (!init.cloudinary_upload_url || init.cloudinary_upload_url === "") {
    onProgress?.("Uploading to server...", 10);

    const formData = new FormData();
    formData.append("video_id", init.video_id);
    formData.append("file", file);
    if (trimStart !== undefined) formData.append("start_time", String(trimStart));
    if (trimEnd !== undefined) formData.append("end_time", String(trimEnd));

    const token = localStorage.getItem("auteur_token");
    const result = await new Promise<{ video_id: string; duration: number }>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${BASE}/video/upload/file`);
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100);
          onProgress?.("Uploading...", 10 + pct * 0.85);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          reject(new Error(`Upload failed: ${xhr.statusText}`));
        }
      };
      xhr.onerror = () => reject(new Error("Upload network error"));
      xhr.send(formData);
    });

    onProgress?.("Done!", 100);
    return { video_id: result.video_id, duration: result.duration };
  }

  // Prod mode: upload directly to Cloudinary (browser → Cloudinary, no server hop)
  onProgress?.("Uploading to Cloudinary...", 5);

  const { public_id, secure_url } = await video.uploadToCloudinary(
    file,
    {
      cloudinary_upload_url: init.cloudinary_upload_url,
      api_key: init.api_key,
      timestamp: init.timestamp,
      signature: init.signature,
      folder: init.folder,
    },
    (pct) => onProgress?.("Uploading...", 5 + pct * 0.85),
  );

  onProgress?.("Finalising...", 95);

  // 3. Tell backend upload is done
  const result = await video.completeUpload(init.video_id, public_id, secure_url);

  onProgress?.("Done!", 100);
  return { video_id: init.video_id, duration: result.duration };
}
