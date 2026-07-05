# Auteur — Complete Agent Guide

## Project Overview

Auteur is an AI-powered video editor that turns raw footage into polished reels/vlogs.
User uploads video → optionally provides reference videos for style → writes a prompt → AI generates a first draft → user approves, tweaks via prompt, or manually edits.

---

## 1. What Has Been Built So Far

### 1.1 Frontend — Routes & Pages

| Route | File | Status | Description |
|---|---|---|---|
| `/` | `src/routes/index.tsx` | ✅ Done | Landing page. Video upload (file or YouTube). After upload shows GENERATE REEL / MANUAL EDIT choice |
| `/editor` | `src/routes/editor.tsx` | ✅ Done | Full CapCut-level editor. Timeline, preview, keyframes, audio, transitions, overlays, effects |
| `/results` | `src/routes/results.tsx` | ✅ Done | Job polling (2s). Summary screen with stat cards, ref breakdown, style match score. 3 buttons: Approve & Download / Tweak with Prompt / Manual Edit |
| `/projects` | `src/routes/projects.tsx` | ⚠️ Minimal | List of projects from API. No delete/search/pagination. "More" button just shows alert |
| `/profile` | `src/routes/profile.tsx` | ⚠️ Partial | User info, plan badge, stat cards. Edits stat is "--". Notifications/Settings show alert "coming soon" |
| `/vault` | `src/routes/vault.tsx` | ✅ Functional | B-roll/meme library. CRUD + search. Play buttons are decorative (no actual playback) |
| `/train` | `src/routes/train.tsx` | ❌ Placeholder | 9 upload slots but files NEVER uploaded to backend. No training pipeline. Badges hardcoded. "Use My Style" does nothing |

### 1.2 Frontend — Components

| Component | File | Status | Description |
|---|---|---|---|
| RightPanel | `src/components/editor/RightPanel.tsx` | ✅ Done (1866 lines) | AI tab: mode switch, ref video upload, prompt chat, GENERATE DRAFT, APPLY & RENDER. Has 7 hidden tabs (transitions, text, effects, audio, keyframes, props, versions) coded but never rendered in UI |
| Timeline | `src/components/editor/Timeline.tsx` | ✅ Done (932 lines) | Multi-track timeline with clip selection, trim handles, zoom, snap, context menu |
| PlaybackControls | `src/components/editor/PlaybackControls.tsx` | ✅ Done (242 lines) | Play/pause, seek, speed, mute, step. Volume state managed locally (not passed as prop) |
| useEditState | `src/components/editor/useEditState.ts` | ✅ Done (154 lines) | Full state management: create, patch, undo/redo, render, versions, chat |
| api.ts | `src/lib/api.ts` | ✅ Done (995 lines) | All API types + clients. Covers every endpoint. `uploadVideo()` handles dev + prod |
| VideoOverlays | `src/components/editor/VideoOverlays.tsx` | ❌ DOES NOT EXIST | Listed in old AGENTS.md but file was never created. The overlay logic is inlined in editor.tsx |
| LeftPanel | `src/components/editor/LeftPanel.tsx` | ⚠️ Partial (257 lines) | Asset browser. Shows vault items but audio/image items have no click-to-add behavior |
| ResizableDivider | `src/components/editor/ResizableDivider.tsx` | ✅ Done (90 lines) | Draggable divider for panel resizing |
| ConfirmDialog | `src/components/editor/ConfirmDialog.tsx` | ✅ Done (102 lines) | Modal confirmation dialog |
| Toast | `src/components/editor/Toast.tsx` | ✅ Done (71 lines) | Toast notification system |

### 1.3 Backend — API Routes

| Endpoint | File | Status | Description |
|---|---|---|---|
| `POST /auth/signin` | `auth.py` | ⚠️ Working | Calls Supabase Auth. **No dev mode** — can't sign up without real Supabase |
| `POST /auth/signup` | `auth.py` | ⚠️ Working | Calls Supabase Auth. **No dev mode** |
| `POST /auth/oauth` | `auth.py` | ✅ Done | Google/GitHub OAuth flow |
| `POST /auth/refresh` | `auth.py` | ✅ Done | Refresh token exchange |
| `GET /auth/me` | `auth.py` | ✅ Done | Current user info |
| `POST /auth/signout` | `auth.py` | ✅ Done | Supabase sign-out |
| `POST /video/upload/init` | `video.py` | ✅ Done | Returns signed params or dev fallback |
| `POST /video/upload/file` | `video.py` | ✅ Done | Direct file upload (dev mode) |
| `POST /video/upload/complete` | `video.py` | ⚠️ Dev no-op | Dev returns `duration: 0` even though computed earlier |
| `POST /video/upload-ref` | `video.py` | ✅ Done | Upload ref video file → returns ref_id |
| `POST /video/youtube` | `video.py` | ⚠️ Dev mock | Dev: creates dead record with "use file upload" message |
| `GET /video/` | `video.py` | ✅ Done | List user's videos |
| `GET /video/{id}` | `video.py` | ✅ Done | Get single video |
| `DELETE /video/{id}` | `video.py` | ✅ Done | Delete video |
| `GET /video/{id}/thumbnails` | `video.py` | ✅ Done | FFmpeg thumbnail strip. URL hardcoded to localhost |
| `POST /edit/` | `edit.py` | ✅ Done | Create edit job. Accepts ref_video_ids array |
| `GET /edit/{id}/status` | `edit.py` | ✅ Done | Poll job status. Returns changelog + output video |
| `POST /edit/refine` | `edit.py` | ⚠️ Bug | Doesn't pass ref_video_ids to new job. Missing created_at/updated_at |
| `GET /edit/history` | `edit.py` | ✅ Done | List user's edit jobs (last 50) |
| `POST /style/analyze-ref` | `style.py` | ✅ Done | Analyze single YouTube ref for style |
| `GET /style/profiles` | `style.py` | ✅ Done | List style profiles |
| `GET /style/dna` | `style.py` | ✅ Done | Get user's style DNA |
| `POST /edit-state/` | `edit_state.py` | ✅ Done | Create edit state for manual editor |
| `GET /edit-state/{id}` | `edit_state.py` | ✅ Done | Get edit state |
| `PATCH /edit-state/{id}` | `edit_state.py` | ⚠️ Bug | `update_text_overlay` and `move_clip` actions missing from Pydantic Union — will be rejected at validation |
| All edit-state sub-routes... | `edit_state.py` | ✅ Done | Transitions, text overlays, overlays, keyframes, audio, effects, aspect ratio, playback, auto-edit, highlights, memory, chat |
| `POST /edit-state/{id}/analyze` | `edit_state.py` | ❌ Bug | Hardcoded `DEV_MODE = True` on line 1909 — always uses localhost URLs even in production |
| `POST /vault/` | `vault.py` | ⚠️ Bug | Missing `import os` at top — will crash on line 66 |
| `GET /vault/` | `vault.py` | ⚠️ Bug | Line 135: `user = supabase = get_supabase()` overwrites supabase variable |
| `DELETE /vault/{id}` | `vault.py` | ✅ Done | Delete vault item |
| `POST /vault/presets` | `vault.py` | ✅ Done | Create prompt template presets |
| `GET /jobs/` | `jobs.py` | ✅ Done | List jobs with optional status filter |
| `GET /jobs/{id}` | `jobs.py` | ✅ Done | Get single job with output videos |
| `DELETE /jobs/{id}` | `jobs.py` | ✅ Done | Cancel queued/running job (uses DELETE — non-RESTful) |
| `POST /jobs/{id}/retry` | `jobs.py` | ⚠️ Bug | Doesn't pass ref_video_ids, vault_items, mode, target_duration to retry payload |
| `GET /payments/plans` | `payments.py` | ✅ Done | List available plans |
| `POST /payments/razorpay/create-order` | `payments.py` | ✅ Done | Razorpay order creation |
| `POST /payments/stripe/create-checkout` | `payments.py` | ✅ Done | Stripe checkout session |
| Webhooks | `payments.py` | ✅ Done | Razorpay + Stripe webhook handlers |

### 1.4 Backend — Services

| Service | File | Lines | Description | Production Ready? |
|---|---|---|---|---|
| Edit Pipeline | `services/edit_pipeline.py` | 645 | Main orchestrator: ref analysis → transcribe → plan → quality → render → changelog | ✅ Yes |
| Refine Pipeline | `services/edit_pipeline.py` | (same) | Partial re-render with prompt-based changes | ✅ Yes |
| Style Merger | `services/style_merger.py` | 228 | Merge ref profiles, generate changelog, store composite | ✅ Yes |
| GPT Service | `services/gpt_service.py` | 526 | GPT-4o Vision for style + text. DEV_MODE returns mock | ⚠️ Dev-only mock |
| FFmpeg Service | `services/ffmpeg_service.py` | 919 | All video processing (25 functions) | ✅ Yes |
| Whisper Service | `services/whisper_service.py` | 103 | Audio transcription. DEV_MODE returns mock | ⚠️ Dev-only mock |
| Queue | `services/queue.py` | 127 | Redis job queue with pub/sub progress | ✅ Yes |
| Creator Memory | `services/creator_memory.py` | 279 | Per-user style learning (pacing, captions, frequency) | ✅ Yes |
| Edit Intelligence | `services/edit_intelligence.py` | 335 | Multi-pass edit plan generation with self-critique | ✅ Yes |
| Edit Quality | `services/edit_quality.py` | 248 | Quality scoring + auto-regeneration feedback | ✅ Yes |
| Partial Render | `services/partial_render.py` | 671 | Dirty segment render (only changed parts) | ✅ Yes |
| Style Consistency | `services/style_consistency.py` | 132 | Global style enforcement | ✅ Yes |
| Prompt Editor | `services/prompt_editor.py` | 570 | AI prompt on edit state | ✅ Yes |
| Edit State | `services/edit_state.py` | 893 | Edit state CRUD + undo/redo + versioning | ✅ Yes |
| Vault Enhanced | `services/vault_enhanced.py` | 381 | Vault suggestion + ranking | ✅ Yes |
| Metrics | `services/metrics.py` | 173 | Edit quality + vault usage tracking | ✅ Yes |
| Cloudinary | `services/cloudinary_service.py` | 199 | Cloudinary upload/delete. Dev: local copy fallback | ⚠️ Dev fallback |
| yt-dlp | `services/yt_dlp_service.py` | 100 | YouTube download | ✅ Yes |
| Reference Analyzer | `services/reference_analyzer.py` | 104 | Dev-only ref analysis (less robust than pipeline inlining) | ❌ Dev-only |

### 1.5 Extra Engine Files (NOT in old AGENTS.md)

These 16 modularized sub-services exist in `backend/services/` and are called by edit_state API routes:

| File | Key Function | Purpose |
|---|---|---|
| `aspect_ratio_engine.py` | `set_aspect_ratio()`, `auto_reframe_segment()` | Aspect ratio + auto reframe |
| `audio_engine.py` | `add_audio_track()`, `set_audio_ducking()` | Audio CRUD + ducking |
| `chat_history.py` | `get_chat_history()`, `append_chat_message()` | Chat history |
| `diff_engine.py` | `compute_edit_diff()`, `format_diff_for_display()` | Version diffing |
| `effects_engine.py` | `set_color_grading()`, `add_blur/shake/glow/vignette/grain()` | Visual effects |
| `highlight_engine.py` | `detect_highlights()` | Highlight detection |
| `keyframe_engine.py` | `add_keyframe()`, `interpolate_keyframes()`, `batch_add_keyframes()` | Keyframe animation |
| `overlay_engine.py` | `add_overlay()`, `update_overlay()`, `reorder_overlay()` | Image/GIF overlays |
| `playback_engine.py` | `set_playhead()`, `seek()`, `step_forward()`, `set_playback_speed()` | Playback state |
| `preview_render.py` | `render_preview()`, `render_segment_preview()` | Preview rendering |
| `r2.py` | `generate_presigned_upload_url()`, `upload_to_r2()` | Cloudflare R2 storage (superseded by Cloudinary) |
| `story_builder.py` | `build_story()`, `chunk_video()`, `_prioritize_emotional_moments()` | Vlog story assembly |
| `text_overlay_engine.py` | `add_text_overlay()`, `build_text_style_string()` | Text overlay CRUD |
| `transitions_engine.py` | `add_transition()`, `build_transition_filter()` | Transitions |
| `video_understanding_ai.py` | `analyze_video()`, `_detect_scenes()`, `_detect_silences()`, `get_summary_stats()` | Full video analysis |
| `vlog_engine.py` | `build_vlog_structure()` | Vlog structure |

---

## 2. Complete User Flow (Step by Step)

### Flow: Upload → Editor → Ref + Prompt → Generate Draft → Results → Approve/Tweak/Manual

```
┌──────────┐    ┌──────────┐    ┌──────────────────────┐    ┌──────────┐
│  LANDING  │───▶│  EDITOR  │───▶│  RIGHT PANEL (AI)   │───▶│  RESULTS │
│  /        │    │  /editor │    │  Ref Upload + Prompt │    │  /results│
│  Upload   │    │  Timeline│    │  GENERATE DRAFT btn  │    │  Summary │
└──────────┘    └──────────┘    └──────────────────────┘    └──────────┘
                                                                    │
                                               ┌────────────────────┤
                                               ▼                    ▼
                                         ┌──────────┐        ┌──────────┐
                                         │ APPROVE  │        │  TWEAK   │
                                         │Download   │        │Prompt    │
                                         │ MP4      │        │more      │
                                         └──────────┘        └──────────┘
                                               │                    │
                                               ▼                    ▼
                                         ┌──────────┐        ┌──────────┐
                                         │ MANUAL   │        │(back to  │
                                         │ Full     │        │ editor)  │
                                         │ Editor   │        │          │
                                         └──────────┘        └──────────┘
```

### Step 1: Upload Video (Landing Page)
- User drops file or pastes YouTube URL in upload modal
- `src/routes/index.tsx:handleFiles` → `uploadVideo()` (api.ts:888)
- Backend: `POST /video/upload/file` → saves locally (dev) or Cloudinary (prod)
- `sessionStorage` stores: `auteur_video_id`, `auteur_video_duration`
- After upload: shows GENERATE REEL / MANUAL EDIT buttons

### Step 2: Enter Editor
- Click MANUAL EDIT → navigates to `/editor`
- `editor.tsx` boot: loads video from sessionStorage, calls `createJob(videoId)` to create EditState
- RightPanel opens with AI tab

### Step 3: Add Reference Videos (RightPanel AI Tab)
- **File upload**: User selects video file → `RightPanel.tsx:uploadRefVideo()`
  - `POST /video/upload-ref` with FormData → backend saves file, returns `ref_id`
  - `refVideoIds` state updated, ref shown in list
- **YouTube URL**: User pastes URL → `RightPanel.tsx:handleRefUrlImport()`
  - `POST /video/youtube` → imports video, returns `video_id`
  - Note: in DEV_MODE, YouTube import returns mock. Use file upload instead.
- Refs shown as chips with filename, removable via X button

### Step 4: Write Prompt
- Bottom of RightPanel: textarea + send button
- This prompt is for **tweaking** the edit state (after a draft is generated)
- For the initial draft, the prompt is passed along with ref_video_ids via GENERATE DRAFT

### Step 5: Click GENERATE DRAFT
- Yellow button at top of AI tab
- `RightPanel.tsx:handleGenerateDraft()` → calls `onGenerateDraft(videoId, refVideoIds, prompt)`
- Parent (`editor.tsx:handleGenerateDraft`):
  ```typescript
  const res = await editApi.create({
    video_id: videoId,
    ref_video_ids: refVideoIds,
    prompt: prompt || "Make a viral edit following the reference style",
    version_type: "viral",
  });
  sessionStorage.setItem("auteur_job_id", res.job_id);
  navigate({ to: "/results" });
  ```

### Step 6: Backend Receives Job
- `POST /edit/` (edit.py:52):
  1. Validates video exists
  2. Creates `edit_jobs` row in DB with status="queued"
  3. Pushes to Redis queue via `queue.enqueue_edit_job()`
  4. Returns `{job_id, status: "queued"}` immediately

### Step 7: Async Pipeline (Worker)
- `worker.py` → `queue.start_worker()` → polls Redis every 1s
- `process_edit_job()` → `edit_pipeline.run_edit_pipeline()`

### Step 8: Frontend Polls Results
- `results.tsx:useEffect` polls `GET /edit/{id}/status` every 2 seconds
- Shows progress bar + 6 step indicators (Queued → Transcribe → Analyze → Plan → Render → Done)

### Step 9: Summary Screen
- Job complete → `changelog` returned in status response
- Results page shows:
  - Video player with output
  - 4 stat cards: Cuts Made, Captions, Duration Change, Music Vibe
  - Reference contributions breakdown (per ref: what they contributed style-wise)
  - Style match score (progress bar 0-100%)
  - **3 buttons: Approve & Download / Tweak with Prompt / Manual Edit**

### Step 10: User Decision
- **Approve** → downloads MP4 directly
- **Tweak** → navigates to `/editor` with `auteur_current_job_id` set (can send more prompts)
- **Manual** → opens full CapCut-level editor with timeline

---

## 3. Async Pipeline Detailed (Backend)

### 3a. `edit_pipeline.run_edit_pipeline(job_id, payload)`

```
Input: {video_id, user_id, prompt, version_type, ref_video_ids, mode}

1. _analyze_ref_videos(ref_video_ids, user_id, job_id)
   For each ref_id:
     ├─ Fetch video record from DB
     ├─ Download video (yt-dlp for YouTube, direct HTTP for file)
     ├─ ffmpeg extract_frames(interval_sec=3, max_frames=20)
     ├─ gpt_service.analyze_style_from_frames(frame_paths)
     │   DEV_MODE: returns hardcoded mock
     │   PROD: sends base64 frames to GPT-4o Vision → returns style JSON
     └─ Append profile to list
   
   merge_style_profiles(profiles):
     ├─ Numeric fields (cut_speed, energy_level): weighted average
     ├─ Categorical fields (hook_pattern, music_vibe, color_grade): highest-weight wins
     ├─ Caption style: plurality vote
     ├─ Blur background: majority rule
     └─ Returns composite style + per-ref contribution tracking
   
   store_composite_style(user_id, job_id, composite, ref_ids):
     ├─ Save to DB style_profiles table
     └─ Update user's style_dna

2. Download main video (HTTP)

3. ffmpeg extract_audio → whisper transcribe
   ├─ Returns [{word, start, end}, ...]
   ├─ Falls back to placeholder if no audio track
   └─ Saves transcript to videos table

4. generate_intelligent_edit_plan(transcript, style, prompt, ref_context)
   ├─ Builds ref_context string: "Ref 1 (filename): {music_vibe, color_grade, ...}"
   ├─ Multi-pass: generate → self-critique → improve → lock
   ├─ Returns edit_plan: {cuts, captions, zoom, music, color, meme_sounds, ...}
   └─ Saves to edit_jobs table

5. Quality Check Loop (max 3 attempts)
   ├─ evaluate_edit_plan(plan, transcript, mode, version)
   │   └─ Scores: readability, pacing, hook strength, engagement, etc.
   ├─ If score < threshold:
   │   ├─ build_regeneration_feedback(quality) → what's wrong + how to fix
   │   └─ Re-generate plan with feedback context
   └─ Save final quality score

6. enforce_global_style(edit_plan, style_profile, user_id, mode)
   └─ Apply consistency rules across all edit elements

7. edit_plan_to_state(edit_plan, job_id, ...) → EditState
   └─ Convert plan to full timeline edit state

8. update_memory_from_edit(user_id, edit_plan)
   ├─ store_pacing_curve(user_id, duration, cuts)
   ├─ store_caption_density(user_id, duration, captions)
   └─ store_editing_frequency(user_id, duration, edits_per_minute)

9. render_edit_state(job_id, user_id, video_url) → output_url
   └─ ffmpeg render → upload to Cloudinary (or local storage in dev)

10. generate_changelog(original_duration, edited_duration, composite_style, profiles, edit_plan)
    └─ Returns {original_duration, edited_duration, total_removed,
         cuts: {total, avg_cut_duration, num_fillers_removed, num_silences_removed},
         captions: {total, style},
         zoom_moments: {total, positions},
         meme_sounds: {total, positions},
         music_vibe, color_grade, style_match_score,
         ref_breakdown: [{ref_index, filename, contributed: {...}}]}

11. DB: edit_jobs.status = "completed", changelog populated
```

### 3b. Refine Pipeline (`run_refine_pipeline`)
- Triggered when user sends a refinement prompt after draft is generated
- First tries: `prompt_editor.process_prompt()` → applies patches to existing EditState → partial re-render
- Fallback: old refinement path using GPT + ffmpeg

---

## 4. Frontend Architecture

### 4.1 Routing (TanStack Router)
- File-based routing: `src/routes/` directory
- `routeTree.gen.ts` auto-generated (run dev server to regenerate)
- All routes wrapped in `<QueryClientProvider>` + `<ThemeProvider>`

### 4.2 State Management
- **Edit State**: `useEditState` hook manages the full timeline state
  - Patches (actions) are undoable via undo/redo stack
  - Version history support
  - Chat history with AI prompts
- **Session Storage**: video_id, job_id, duration, filename
- **API calls**: centralized `api.ts` with typed request wrappers

### 4.3 RightPanel AI Tab Structure
```
┌──────────────────────┐
│  VLOG │ REELS toggle  │  ← mode switch
│        [Style]        │  ← save to memory
├──────────────────────┤
│  Reference Videos     │
│  ┌─ Ref 1 (file.mp4) │  ← ref video list
│  │   [X]             │     removable
│  ├─ Ref 2 (yt_...)   │
│  └─ [Upload] [URL]   │  ← add refs
├──────────────────────┤
│  ╔══════════════════╗ │
│  ║ GENERATE DRAFT   ║ │  ← YELLOW BUTTON
│  ╚══════════════════╝ │
│  ╔══════════════════╗ │
│  ║ APPLY & RENDER   ║ │  ← GREEN BUTTON
│  ╚══════════════════╝ │
├──────────────────────┤
│  ┌──────────────────┐│
│  │ Ask AI to edit... ││  ← chat history
│  └──────────────────┘│
│  [Attach] [textarea]▶ │  ← prompt input
└──────────────────────┘
```

Note: RightPanel has 7 additional tabs (transitions, text, effects, audio, keyframes, props, versions) fully coded in JSX but NEVER rendered — only `ai` tab is in the `TABS` array.

---

## 5. Dev Mode vs Production

| Feature | Dev Mode | Production |
|---|---|---|
| Database | File-based JSON (`backend/.dev_db.json`) | Supabase PostgreSQL |
| AI Model | Ollama (localhost:11434) | OpenAI GPT-4o |
| Vision Analysis | Mock data returned | Real GPT-4o Vision API |
| Video Storage | Local files (`backend/dev_uploads/`) | Cloudinary |
| File Serving | `http://localhost:8000/api/video/local/` | Cloudinary URLs |
| YouTube Import | Mock (returns "use file upload") | yt-dlp + Cloudinary upload |
| Video Size Limit | None | 2GB |
| Auth | ❌ BROKEN — can't sign up without Supabase | Supabase Auth |
| Vault | ❌ BROKEN — missing `import os`; no R2 fallback | Cloudflare R2 |
| Payments | ❌ BROKEN — will throw 500 if keys not set | Stripe / Razorpay |

---

## 6. Known Bugs (Must Fix)

### Critical (✅ All Fixed — Phase A Complete)
- [x] **`auth.py` has no dev mode** — `POST /auth/signup` calls real Supabase Auth. If Supabase isn't configured, users can't sign up/log in in dev mode
  - ✅ Fixed: Dev mode mock auth added (signup + signin both return dev-token without hitting Supabase)
- [x] **`vault.py` missing `import os`** — Line 66 will throw `NameError: name 'os' is not defined` on any file upload
  - ✅ Fixed: `import os` present at line 1
- [x] **`edit_state.py:1909` hardcoded `DEV_MODE = True`** — production traffic will get `localhost` video URLs. Should read from `settings`
  - ✅ Fixed: Uses `settings.dev_mode` and `cfg.dev_mode` from config
- [x] **`edit_state.py` Pydantic Union bug** — `update_text_overlay` and `move_clip` actions are handled in code but missing from `BatchEditRequest` Union type, so Pydantic rejects them
  - ✅ Fixed: Both `UpdateTextOverlayAction` (line 310) and `MoveClipAction` (line 302) are in the Union
- [x] **`vault.py:135` typo** — `user = supabase = get_supabase()` overwrites the `supabase` variable
  - ✅ Fixed: Line 149 correctly uses `supabase = get_supabase()`

### Important (✅ Most Fixed — Phase A Complete)
- [x] **RightPanel ref upload uses hardcoded `localhost:8000`** — should use `VITE_API_URL` env var (line 204)
  - ✅ Fixed: No hardcoded localhost found in RightPanel.tsx
- [x] **Timeline thumbnails use hardcoded `localhost:8000`** — should use `BASE` URL from api.ts
  - ✅ Fixed: No hardcoded localhost found in Timeline.tsx
- [ ] **`edit.py:refine` doesn't pass `ref_video_ids`** — retry/refine loses original reference context
- [ ] **`jobs.py:retry` doesn't pass `ref_video_ids`, `vault_items`, `mode`, `target_duration`** — retry loses context
- [ ] **`train.tsx` is a UI mockup** — files never uploaded, no training pipeline, badges hardcoded
- [x] **`VideoOverlays.tsx` doesn't exist** — listed in docs but never created (logic inlined in editor.tsx instead)
  - ✅ No action needed: Logic is inlined in editor.tsx, remove from file index only
- [x] **RightPanel has 1866 lines with 7 inactive tabs** — dead code for transitions/text/effects/audio/keyframes/props/versions tabs that are never shown
  - ✅ Fixed: TABS array only contains "ai" tab

---

## 7. Pending Work for Production Level

### 7.1 Critical
- [ ] **Background worker in production** — current worker.py runs as single process. Needs:
  - Docker containerization
  - Multiple workers for concurrency
  - Graceful shutdown handling
  - Error recovery (job retry with exponential backoff)
  - Dead letter queue for failed jobs
- [ ] **Redis persistence** — current config is ephemeral. Needs RDB/AOF for crash recovery
- [ ] **Cloudinary setup** — replace local video storage with Cloudinary upload + CDN
- [ ] **Supabase tables migration** — file-based DB is for dev only. Production needs proper Supabase schema with:
  - Users table (already exists)
  - Videos table (already exists)
  - Edit jobs table (already exists)
  - Style profiles table (exists in code)
  - Output videos table (exists in code)
  - Creator memory tables
  - Vault tables
- [ ] **Auth improvements** — current JWT-based auth is basic. Needs:
  - Email verification
  - Password reset
  - OAuth (Google, Apple)
  - Session refresh
  - Rate limiting
- [ ] **Error handling** — current error handling is basic. Needs:
  - Structured error responses
  - Client-side error recovery
  - Graceful degradation when services are down

### 7.2 Important
- [ ] **Multi-output (reels + shorts)** — generate both 9:16 and 16:9 versions from same edit
- [ ] **Ref caching** — each ref video re-analyzed every time. Cache style profiles by video hash
- [ ] **Tweak flow** — clicking "Tweak" from results should:
  - Load the edit state into the editor
  - Allow sending more prompts
  - Support re-rendering with changes
- [ ] **Progress indicators** — current polling is basic. Add:
  - SSE (Server-Sent Events) for real-time progress
  - Estimated time remaining
  - Cancel job button
- [ ] **Video processing timeouts** — current pipeline has no hard timeout. Add:
  - Per-stage timeouts
  - Total job timeout (e.g., 10 minutes)
  - Early failure detection
- [ ] **File cleanup** — temp files accumulate. Add:
  - TTL-based cleanup
  - Post-processing cleanup in all code paths

### 7.3 Nice to Have
- [ ] **Usage tracking** — track API usage per user/plan
- [ ] **Analytics** — edit quality trends, user engagement
- [ ] **Team collaboration** — shared projects, team vault
- [ ] **Mobile app** — React Native or Flutter
- [ ] **Template marketplace** — premade style templates
- [ ] **Batch editing** — edit multiple videos at once with same style
- [ ] **Webhook notifications** — notify external services on job complete
- [ ] **UI polish** — loading states, empty states, error states, animations
- [ ] **Pricing/Plans page** — show plans, upgrade/downgrade flow
- [ ] **Auth UI polish** — signup/login forms proper, OAuth buttons (Google, GitHub)
- [ ] **Onboarding flow** — pehli baar user ko guide karo (tooltips, walkthrough)
- [ ] **Compare before/after** — original vs edited video side by side
- [ ] **Share to social** — YouTube/Instagram/TikTok direct export
- [ ] **Project thumbnails** — projects page mein video thumbnails dikho
- [ ] **Video trimming on upload** — user upload karte time trim kar sake
- [ ] **Audio library** — built-in music tracks select karne ko (genre/mood based)

### 7.4 Results Page — Visual Timeline Summary (Planned)

Current results page shows stat cards (cuts/captions/duration/music) + ref breakdown + 3 buttons. User can only approve all or tweak blindly.

**Problem:** User ko nahi pata chalta *kahan kya hua*. Ek number (e.g., "12 cuts") se timeline ka visual nahi banta.

**Planned redesign — Interactive Timeline Summary:**

```
┌─────────────────────────────────────────────────────────┐
│                Video Player (output)                     │
└─────────────────────────────────────────────────────────┘

Timeline: ═══════════════════ 00:00 → 02:30 ══════════════
          🔴🔴    🟢     🔴🟡     🔴      🟢     🔴
          cut  caption  cut+zoom  sil.  caption  cut

                 [ 🖱️ Click any marker to inspect ]

┌─────────────────────────────────────────────────────────┐
│   Added       │  Kept      │  Removed     │  Modified   │
│   🟢 12 cuts   │ 🟢 8 clips │ 🔴 5 silences │ 🟡 3 zooms │
│   🟢 8 caps    │ 🟢 full    │ 🔴 2 fillers │ 🟡 warm     │
└─────────────────────────────────────────────────────────┘

┌─ @00:15 ────────────────────────────────────────────────┐
│  [✓] Cut silence (0.4s removed)                         │
│  [✓] Added caption: "So basically..."                   │
│  [✗] Zoom at 1.5x  ← toggled off by user               │
└─────────────────────────────────────────────────────────┘

┌─ Targeted Prompt ───────────────────────────────────────┐
│ At [00:15 ──] type: "ye scene slow karo aur zoom       │
│ hata do"                                                │
│ [Apply to Selection]                                    │
└─────────────────────────────────────────────────────────┘
```

**Key features:**
- **Timeline visualization** — har edit ka marker with time, type, color code. 2 second mein pata chal jaye kya kara hai
- **Toggle per edit** — user kisi bhi cut/zoom/caption ko on/off kar sake
- **Segment detail** — marker pe click → detail list of every change at that timestamp
- **Targeted prompt** — specific timestamp ya segment ke liye precise prompt de sake
- **Summary cards** — quick glance: kitna add kiya, kitna hataoya, kitna modify kiya

**Implementation needed:**
- Backend `generate_changelog()` ko har segment ke bare mein detail dena hoga (per-timestamp edit events)
- Frontend naya `TimelineSummary` component with clickable markers
- Toggle state local (optimistic) + batch API call on "Apply"
- New endpoint: `POST /edit-state/{id}/batch-toggle` ya existing PATCH handle kare

---

### 7.5 AI Limitations — Practical Solutions

| Limitation | Solution | Priority |
|---|---|---|
| **Emotional intuition** — AI ko nahi pata kaunsa moment emotionally important hai | Sentiment analysis on transcript + audio tone detection (excitement vs flat) + face expression detection → mark "emotional peaks" aur unhe preserve karo na ki cut karo | Medium |
| **Context outside frame** — AI sirf video + transcript dekhta hai | User generate karne se pehle ek **brief** de — "ye farewell party hai, 2:30 pe cake cutting important hai" → AI wahan skip nahi karega | High |
| **Creative risks** — AI rule-based quality check (threshold 6.0) unconventional edits ko reject karega | **Two modes**: "Safe" (current threshold 6.0) aur "Creative" (threshold 3.0 ya full disable). Ya user ko slider de quality strictness ka | High |
| **Non-verbal subtlety** — silence ko "dead air" treat karta hai, dramatic pause preserve nahi karta | Silence ko do category mein classify karo: **dead air** (cut) vs **dramatic pause** (preserve). Audio energy + transcript analysis se differentiate | Medium |
| **Client feedback** — "ye thoda off hai" jaise vague feedback AI nahi samjhega | Prompt refinement ko improve karo — user bolta hai "ye scene zyada lamba hai" → AI specific segment identify kare aur shorten kare | High |
| **Last-mile polish** — FFmpeg filters basic hain, DaVinci Resolve level control nahi | **EDL/XML export** — DaVinci Resolve / Premiere Pro mein open kar sakte ho. AI ka 80% kaam, human 20% polish apne tool mein | High |
| **Novel techniques** — AI trained patterns follow karta hai, naya effect invent nahi kar sakta | User **custom templates** save kar sake. Ek baar human editor ne koi specific transition banaya — AI use seekh le aur future mein offer kare | Low |

**Overall strategy:** AI = **first draft engine**. Human = **final polish**. Dono ke beech mein **EDL export + feedback loop** — har baar human tweak karta hai, AI seekhta hai. Vibe coding jaisa hi: AI likhta hai, human review + fix karta hai.

---

### 7.6 Scalability — Current Bottlenecks & Fixes

Current system can handle **~1-5 concurrent users**. Primary bottlenecks and fixes:

#### Critical (system crashes under load)

| # | Bottleneck | File:Line | Fix | Capacity Before | After |
|---|---|---|---|---|---|
| 1 | **Single worker** — processes 1 job at a time | `worker.py:19` | Multi-worker via Redis streams consumer groups, or Celery | 1 job/60s | N jobs/60s |
| 2 | **Unlimited FFmpeg processes** — 10 renders spawn 100+ subprocesses | `ffmpeg_service.py:25` | Global `asyncio.Semaphore` (max 4 FFmpeg processes) + `FFMPEG_THREADS=1` | ~3-5 concurrent renders | ~10+ |
| 3 | **Entire file in memory** on upload — 2GB file = 2GB RAM | `video.py:139` | Stream write in chunks (8MB buffer) | ~5-10 uploads (OOM) | ~100+ |
| 4 | **No Redis fallback** — Redis down = jobs lost silently | `queue.py:25` | Postgres-backed fallback queue | 0 during downtime | Unlimited |
| 5 | **No rate limiting on OpenAI** — 5 concurrent calls get 429 | `gpt_service.py:43` | Token bucket (`aiolimiter`) + retry with backoff + cache by video hash | ~2-3 GPT calls | ~50+ |
| 6 | **Race conditions on edit state** — 2 concurrent PATCHes lose data | `edit_state.py:372` | Optimistic locking with version field, or asyncio.Lock per job_id | Data loss at 2+ users | Safe |
| 7 | **Full state read/write per edit** — 500KB JSON on every trim | `edit_state.py:137` | Postgres JSONB partial updates instead of read-modify-write | ~50 edits/min | ~500 edits/min |
| 8 | **No polling backoff** — 30k req/min at 1000 users | `results.tsx:46` | Exponential backoff with jitter (2s → 30s), recursive setTimeout | Server saturates | Stable |
| 9 | **Silent error swallow** — 429/503 makes polling worse | `results.tsx:57` | Parse Retry-After, show user feedback, circuit breaker | Compounds problem | Graceful |

#### High (significant degradation under load)

| # | Bottleneck | File:Line | Fix |
|---|---|---|---|
| 10 | **No CDN, no range requests** — single Python serves all videos/thumbs | `video.py:167` | nginx X-Accel-Redirect + Cloudinary CDN + Cache-Control headers |
| 11 | **Synchronous `subprocess.run`** for thumbnails blocks event loop | `video.py:440` | Replace with `asyncio.create_subprocess_exec` |
| 12 | **New HTTPX client per download** — TCP + TLS overhead per request | `partial_render.py:497` | Single global `httpx.AsyncClient` with connection pooling |
| 13 | **No style analysis cache** — same ref video analyzed every time | `edit_pipeline.py:122` | Cache by content hash in style_profiles table |
| 14 | **N+1 queries** — sequential DB calls per ref video | `edit_pipeline.py:129` | Batch fetch + concurrent processing via `asyncio.gather` |
| 15 | **Frontend full-state re-fetch** after every mutation | `useEditState.ts:41` | Incremental PATCH responses + TanStack React Query (already installed but unused) |
| 16 | **No vault pagination** — all items loaded in one API call | `vault.tsx:23` | Server-side pagination (`?limit=50&offset=0`) + virtual scrolling |
| 17 | **Dead code in bundle** — 51 unused packages, 7 hidden tab JSX | `package.json` | Tree-shake unused deps, remove hidden tabs, actually use React Query |
| 18 | **No request AbortController** — in-flight requests on navigation | `api.ts` | Add `AbortSignal.timeout(10000)` + abort on unmount |
| 19 | **No job idempotency** — worker crash loses current job | `queue.py:122` | BRPOPLPUSH pattern + heartbeat + processing queue |

#### Medium (optimization needed)

| # | Bottleneck | File:Line | Fix |
|---|---|---|---|
| 20 | **Sequential FFmpeg passes** — cut → zoom → captions → grade = 4 passes | `partial_render.py:349` | Combine into single `filter_complex` FFmpeg call |
| 21 | **Temp file explosion** — 20-30 temp files per job | `ffmpeg_service.py:43` | Per-job temp dir + aggressive cleanup |
| 22 | **Deep copy on every undo** — 25MB per edit state (50 versions × 500KB) | `edit_state.py:673` | Operation-based undo (store diff, not full state) |
| 23 | **No re-render optimization** — 1157-line RightPanel re-renders fully | `RightPanel.tsx` | Split into `React.memo` components + `useMemo` derived data |
| 24 | **Dev mode JSON DB** — read-modify-write locks on every request | `database.py:13` | Replace with SQLite (dev) or always use Supabase |
| 25 | **Big bundle** — 60+ dependencies, many unused | `package.json` | Tree-shake unused packages (recharts, framer-motion, cmdk, embla-carousel, etc.) |

#### Estimated capacity after fixes

| Stage | Concurrent Users |
|---|---|
| **Current** | **~1-5** |
| After critical + high fixes | ~50-100 |
| After all fixes | ~200-500 |

**#1 priority:** Multi-worker support with job idempotency (changes from 1 job/60s to N jobs/60s). **#2 priority:** Stream file uploads + FFmpeg semaphore (OOM and system thrashing).

---

### 7.7 Security Audit

#### Critical (Fix Immediately)

| # | Issue | File:Line | Fix |
|---|---|---|---|
| C1 | **Hardcoded JWT secret** — `auteur-dev-secret-key` committed | `.env:3`, `security.py:19` | Generate `openssl rand -hex 64`, add `.env` to `.gitignore` |
| C2 | **Dev mode auth bypass** — `get_current_user()` returns hardcoded `DEV_USER` | `security.py:47-48` | Remove dev bypass, require valid JWT signature even in dev |
| C3 | **Path traversal** — `/api/video/local/{filename}` reads arbitrary files | `video.py:167-179` | Validate resolved path stays within `DEV_STORAGE` |
| C4 | **Same path traversal** in thumbnail serving | `video.py:457-463` | Same fix — confine to `DEV_STORAGE/thumbs/` |
| C5 | **Auth token in localStorage** — any XSS leaks JWT permanently | `api.ts:11`, `index.tsx:61` | Use `HttpOnly` cookies or BFF pattern |
| C6 | **No rate limiting anywhere** — brute-force auth, flood endpoints | All endpoints | Add `slowapi` middleware: 5/min auth, 60/min reads, 10/min uploads |
| C7 | **Command injection vector** — URL passed to yt-dlp subprocess | `reference_analyzer.py:29-31` | Validate URL starts with `http(s)://`, reject URLs starting with `-` |

#### High

| # | Issue | File:Line | Fix |
|---|---|---|---|
| H1 | **Fragile dev detection** — `"your-" in supabase_anon_key` | `security.py:12` | Use explicit `APP_ENV` env var |
| H2 | **Stack traces leaked** — `str(e)[:200]` returned in API responses | Multiple files | Log server-side, return generic messages to client |
| H3 | **Missing auth on file endpoints** — thumbs/videos accessible without token | `video.py:167,391,457` | Add `Depends(get_current_user)` to file-serving endpoints |
| H4 | **Cloudinary API key + signature exposed to browser** | `api.ts:159-164` | Short TTL (60s), upload presets, restrict folders per-user |
| H5 | **No CSRF protection** — if cookie auth is ever used | All API calls | `SameSite=Strict`, custom `X-CSRF-Token` header |
| H6 | **IDOR** — user can change IDs in sessionStorage to access others' data | `api.ts:223,257,502` | Server-side ownership check on EVERY endpoint |
| H7 | **7-day JWT expiry** with no refresh token rotation | `security.py:17` | Reduce to 1 hour + proper refresh/rotate flow |
| H8 | **No file size validation** — 10GB upload causes OOM | `video.py:125-164` | Check `Content-Length`, stream in 8MB chunks |
| H9 | **Filenames not sanitized** — raw `file.filename` used in paths | `video.py:136`, `vault.py:67` | Strip path separators, use UUID filenames server-side |
| H10 | **`.env` not in `.gitignore`** — secrets can be committed | `.gitignore` | Add `.env`, `.env.local`, `.env.*.local` |

#### Medium

| # | Issue | File:Line | Fix |
|---|---|---|---|
| M1 | **Prompt injection** — unsanitized user prompts go to LLM | `RightPanel.tsx:163`, `editor.tsx:228` | Strict prompt delimiters, filter injection patterns, output schema validation |
| M2 | **Dev DB in plaintext JSON** — all data unencrypted | `database.py:14` | Use SQLite (dev) or always use Supabase |
| M3 | **Webhook doesn't verify user/plan existence** | `payments.py:176-178` | Validate `user_id` and `plan_id` exist before applying |
| M4 | **CORS too permissive** — `allow_methods=["*"]` | `main.py:32-45` | Restrict to GET, POST, PUT, PATCH, DELETE + required headers |
| M5 | **Worker Redis has no auth** — anyone can inject jobs | `queue.py:28` | Require `REDIS_PASSWORD` in production, use TLS |
| M6 | **No CSP headers** — no defense-in-depth against XSS | Frontend (none set) | Add `default-src 'self'; script-src 'self'; ...` |
| M7 | **Weak client-side file type validation** — MIME spoofable | `index.tsx:309`, `vault.tsx:73-89` | Backend must validate magic bytes; frontend is UX-only |
| M8 | **YouTube URL not validated** before backend call | `index.tsx:320-329` | Add regex validation for youtube.com/watch URLs |
| M9 | **URL.createObjectURL memory leak** — never revoked | `RightPanel.tsx:835` | Track and revoke blob URLs via cleanup useEffect |
| M10 | **Zombie processes** — 120s FFmpeg timeout, no preexec_fn | `video.py:440` | Reduce timeout to 30s, use `preexec_fn` for process groups |

#### Low (14 items)

- `alert()` used instead of Toast (18 instances) — `Toast.tsx` already exists but unused
- Sidebar cookie set without `Secure`/`HttpOnly`/`SameSite` flags
- `__pycache__`, `*.pyc`, `venv/` not in `.gitignore`
- Dev mode silently falls back on misconfiguration (no warning log)
- No log rotation or sampling for high-frequency logs
- Predictable dev refresh tokens (`f"dev_refresh_{user_id}"`)
- No CSRF idempotency key on payment webhooks
- Video thumbnail generation no timeout guard rails
- Dev Cloudinary down = silent prod-quality loss
- `os.makedirs` without `exist_ok=True` in some paths
- Backup .env.example missing from repo root
- No pre-commit hooks for secret leak detection
- Telemetry/logging opt-out mechanism missing
- No SSL/TLS enforcement in dev mode

#### Priority order to fix

```
C1 → C2 → C3 → C4 → C5 → C6 → C7  (critical — system actively exploitable)
  ↓
H1 → H10  (high — significant risk)
  ↓
M1 → M10  (medium — should fix before production launch)
```

---

### 7.8 Additional Production Audits Needed

| Audit | Status | Why Important | Effort |
|---|---|---|---|
| **Performance/Load Testing** | ❌ Not done | Actual benchmarking with k6/artillery — identify slow endpoints, verify scalability fixes work under real load | Medium |
| **Database/Data Integrity** | ❌ Not done | Migration strategy (Supabase schema → production), backup plan, data loss scenarios, rollback plan | Medium |
| **Dependency Vulnerability Scan** | ❌ Not done | Run `npm audit`, `pip audit`, `safety check` — fix known CVEs, outdated packages with security patches | Low |
| **Cost Analysis** | ❌ Not done | OpenAI API cost per job (GPT-4o Vision ~$0.10/analysis, Whisper ~$0.006/min), Cloudinary bandwidth, infra per user. Set budget alerts | High |
| **Monitoring / Logging / Alerting** | ❌ Not done | Error tracking (Sentry), uptime monitoring, API latency alerts, worker failure alerts, OpenAI cost spike alerts | High |
| **Disaster Recovery** | ❌ Not done | DB backup strategy + restore runbook, Redis persistence (RDB/AOF), temp file cleanup on crash, dead letter queue monitoring | Medium |
| **Error Handling & Recovery** | ❌ Not done | Graceful degradation — agar OpenAI down ho toh kya? Agar Cloudinary down ho? Agar Redis down? Show user-friendly messages | High |
| **API Documentation** | ❌ Not done | Swagger/OpenAPI docs complete karo, developer onboarding guide, webhook integration docs | Low |
| **Legal / Privacy Compliance** | ❌ Not done | GDPR compliance, privacy policy, cookie consent banner, Terms of Service, data retention policy, user data export/deletion | Medium |
| **Mobile / Browser Compatibility** | ❌ Not done | Test on Chrome/Safari/Firefox, mobile responsive, touch support for timeline, video playback on iOS | Low |
| **Configuration & Secrets Management** | ❌ Not done | Feature flags, env segregation (dev/staging/prod), secrets vault (Vault/AWS Secrets Manager), zero-trust config validation | Medium |
| **CI/CD Pipeline** | ❌ Not done | Automated lint + typecheck + test + build on push, staging deploy, production deploy with rollback | High |
| **SLA & Rate Limit Policy** | ❌ Not done | Define API rate limits per plan (free: 10 jobs/day, pro: 100), publish SLA, handle overages gracefully | Low |

#### Top 5 priority before launch

1. **Cost Analysis** — AI API costs calculate karo per job. GPT-4o Vision + Whisper = ~$0.15/job. 1000 jobs/month = $150. Ensure pricing covers this.
2. **Dependency Vulnerability Scan** — `npm audit` + `pip audit` chalao, critical CVEs fix karo before going public
3. **Monitoring** — Error tracking (Sentry) + uptime monitoring + worker heartbeat — production mein andhe nahi reh sakte
4. **Disaster Recovery** — DB backup strategy, temp file cleanup, dead letter queue monitoring — kya hoga agar kuch fail ho jaye
5. **Error Handling & Recovery** — Har third-party dependency ke liye fallback plan: OpenAI down → queue jobs for later, Cloudinary down → local fallback, Redis down → Postgres fallback queue

---

## 8. How to Run

### Terminal 1: Redis
```bash
redis-server
```

### Terminal 2: Backend
```bash
cd backend && uvicorn main:app --reload --port 8000
```

### Terminal 3: Worker
```bash
cd backend && python worker.py
```

### Terminal 4: Frontend
```bash
cd . && npx vite dev --port 4444
```

### Environment Variables (`backend/.env`)
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=llama3.2
REDIS_URL=redis://localhost:6379
CLOUDINARY_CLOUD_NAME=your-cloud
CLOUDINARY_API_KEY=your-key
CLOUDINARY_API_SECRET=your-secret
```

For DEV_MODE, leave Supabase URLs as placeholders and set OPENAI_API_KEY to "ollama".

---

## 9. Key Design Decisions

1. **Single job per edit** — one edit request = one pipeline run. No multiple versions per job (keeps it simple)
2. **Redis for queue** — lightweight, fast, pub/sub support for progress
3. **Edit State pattern** — full timeline state object with undoable patches. Makes manual editing and AI tweaks composable
4. **DEV_MODE detection** — auto-detected from Supabase URL. No env toggle needed. But this heuristic is fragile (`"your-" in supa_key`)
5. **Style merging** — weighted averages for numbers, plurality for categories. Simple but effective
6. **Changelog as JSON** — stored in edit_jobs table, returned in status endpoint. No join needed
7. **SessionStorage** — used instead of state management library for simplicity. video_id, job_id survive page refresh

---

## 10. File Index

```
auteur/
├── AGENTS.md                    ← This file
├── backend/
│   ├── main.py                  ← FastAPI app
│   ├── worker.py                ← Background worker entry point
│   ├── .env                     ← Environment variables
│   ├── .dev_db.json             ← File-based DB (dev mode)
│   ├── dev_uploads/             ← Local video storage
│   ├── core/
│   │   ├── config.py            ← Settings from .env
│   │   ├── database.py          ← Supabase + DevSupabaseClient
│   │   └── security.py          ← Auth helpers
│   ├── api/routes/
│   │   ├── auth.py              ← Login/register
│   │   ├── video.py             ← Upload, ref upload, YouTube import, CRUD, thumbnails
│   │   ├── edit.py              ← Edit job create, status, refine, history
│   │   ├── edit_state.py        ← Full edit state CRUD (2329 lines, 80+ endpoints)
│   │   ├── style.py             ← Style analysis, profiles, DNA
│   │   ├── vault.py             ← Vault CRUD (⚠️ missing import os)
│   │   ├── jobs.py              ← Job list, retry, cancel
│   │   └── payments.py          ← Stripe/Razorpay subscriptions
│   └── services/
│       ├── edit_pipeline.py     ← Main + refine pipeline
│       ├── style_merger.py      ← Ref style merge + changelog
│       ├── gpt_service.py       ← GPT-4o Vision + text generation (mock in dev)
│       ├── ffmpeg_service.py    ← All video processing (25 functions)
│       ├── whisper_service.py   ← Audio transcription (mock in dev)
│       ├── queue.py             ← Redis job queue
│       ├── creator_memory.py    ← Per-user style learning
│       ├── edit_intelligence.py ← Edit plan generation
│       ├── edit_quality.py      ← Quality scoring + regen
│       ├── partial_render.py    ← Dirty segment render
│       ├── style_consistency.py ← Global style enforcement
│       ├── prompt_editor.py     ← AI prompt on edit state
│       ├── edit_state.py        ← Edit state helpers
│       ├── vault_enhanced.py    ← Vault suggestion
│       ├── metrics.py           ← Tracking
│       ├── cloudinary_service.py ← Cloudinary upload (local fallback in dev)
│       ├── yt_dlp_service.py    ← YouTube download
│       ├── reference_analyzer.py ← Dev-only ref analysis
│       ├── aspect_ratio_engine.py
│       ├── audio_engine.py
│       ├── chat_history.py
│       ├── diff_engine.py
│       ├── effects_engine.py
│       ├── highlight_engine.py
│       ├── keyframe_engine.py
│       ├── overlay_engine.py
│       ├── playback_engine.py
│       ├── preview_render.py
│       ├── r2.py               ← Cloudflare R2
│       ├── story_builder.py
│       ├── text_overlay_engine.py
│       ├── transitions_engine.py
│       ├── video_understanding_ai.py
│       └── vlog_engine.py
└── src/
    ├── router.tsx               ← Router setup
    ├── routeTree.gen.ts         ← Auto-generated route tree
    ├── routes/
    │   ├── __root.tsx           ← Root layout
    │   ├── index.tsx            ← Landing page + upload (573 lines)
    │   ├── editor.tsx           ← Full manual editor (1022 lines)
    │   ├── results.tsx          ← Summary/changelog (356 lines)
    │   ├── projects.tsx         ← Edit history (83 lines, minimal)
    │   ├── profile.tsx          ← User profile (190 lines, partial)
    │   ├── vault.tsx            ← Clip library (233 lines)
    │   └── train.tsx            ← Style training (196 lines, placeholder)
    ├── components/
    │   └── editor/
    │       ├── RightPanel.tsx   ← AI tab (1866 lines, 7 hidden tabs)
    │       ├── Timeline.tsx     ← Timeline editor (932 lines)
    │       ├── PlaybackControls.tsx
    │       ├── useEditState.ts  ← Edit state hook
    │       ├── VideoOverlays.tsx ← ❌ DOES NOT EXIST
    │       ├── ResizableDivider.tsx
    │       ├── ConfirmDialog.tsx
    │       ├── Toast.tsx
    │       └── LeftPanel.tsx
    └── lib/
        └── api.ts              ← All API types + clients (995 lines)

---

## 11. Master Execution Plan — Step by Step (Agent-Proof)

### How to use this plan

- **Har step ek task hai** — ek saath ek karo, never parallel
- **Har step ke 4 parts hain:**
  1. `FIND` — exact grep/search pattern to locate code
  2. `CHANGE` — exact old string → new string replacement
  3. `TEST` — command ya manual check to verify it worked
  4. `SAFEGUARD` — verify existing flow didn't break
- **Agar test fail hota hai:** revert the change (`git checkout <file>` ya CTRL+Z in editor), debug, retry
- **Har step ke baad:** backend restart karo (uvicorn auto-reload hai, but worker ko manual restart chahiye)
- **1 step = 1 atomic change** — kabhi multiple files ek saath change mat karo

---

### PHASE A: DEMO CRASH-PROOF ✅ COMPLETE

**Status:** All 9 items verified fixed in code + tested.

| Step | File | Status | Test |
|---|---|---|---|
| A1 | vault.py — `import os` | ✅ Done | Grep confirms `import os` at line 1 |
| A2 | vault.py — typo fix | ✅ Done | Line 149: `supabase = get_supabase()` correct |
| A3 | edit_state.py — hardcoded DEV_MODE | ✅ Done | Uses `settings.dev_mode` and `cfg.dev_mode` |
| A4 | edit_state.py — Pydantic Union | ✅ Done | Both actions in Union (lines 302, 310) |
| A5 | RightPanel.tsx — hardcoded localhost | ✅ Done | No `localhost:8000` found |
| A6 | Timeline.tsx — hardcoded thumbnails | ✅ Done | No `localhost:8000` found |
| A7 | auth.py — dev mode mock | ✅ Done | Signup/signin return dev-token in DEV_MODE |
| A8 | RightPanel.tsx — 7 hidden tabs | ✅ Done | TABS array only has "ai" |
| A9 | Frontend — dev auth flow | ✅ Done | Token stored in localStorage + sent via request() |

**Note:** These were already fixed in code but AGENTS.md docs were stale. Updated now.

---

### PHASE B: IMPRESS INVESTORS (ye features dikhane layak hain) ✅ COMPLETE

**Status:** All 5 items implemented, built, and live-tested.

#### B1: Results page — Interactive Timeline Summary ✅ DONE

**Why:** Current results page shows boring numbers. Investor ko "AI ne kya kara" visual chahiye.

```
FILES:  
  - src/routes/results.tsx (frontend component)
  - backend/services/style_merger.py (backend changelog)
  - src/lib/api.ts (type definitions)
  - src/components/editor/TimelineSummary.tsx (new component)

CHANGES:

  Step 1: Backend — update generate_changelog() in style_merger.py
  Added _build_edit_events() helper that creates timestamp-sorted edit events
  from cuts, captions, zoom_moments, meme_sounds, removed silences, fillers.
  Added edit_events to changelog dict.

  Step 2: Frontend — added EditEvent type in api.ts
  Added EditEvent interface + edit_events field on ChangelogEntry.

  Step 3: Frontend — new TimelineSummary component
  - Horizontal timeline bar with colored markers
  - Green = added, Red = removed, Yellow = modified
  - Click marker → show detail popup with enabled/disabled toggle
  - Summary cards: Added/Kept/Modified/Removed counts
  - "Active" toggle to filter only enabled events
  - "Apply Changes" button when edits are toggled off

  Step 4: Frontend — render TimelineSummary in results.tsx
  Replaced 4 stat cards (Cuts/Captions/Duration/Music) with TimelineSummary.
  Kept ref breakdown and style match score sections.

TEST:   Build passes. Visual timeline with markers on canvas.
        Click marker → detail popup appears below.
        Toggle on/off → summary counts update.
        "Apply Changes" button appears when edits are toggled off.
```

#### B2: Fix "Tweak with Prompt" flow ✅ DONE

**Why:** Clicking "Tweak" from results should load edit state + allow re-prompting

```
FIND:   grep -n "handleTweak\|auteur_current_job_id" src/routes/results.tsx
        grep -n "loadState\|createJob" src/routes/editor.tsx

CHANGE: File: src/routes/results.tsx
        In handleTweak():
        - store job_id in sessionStorage as "auteur_current_job_id"
        - navigate to /editor
        
        File: src/routes/editor.tsx
        On mount, check for "auteur_current_job_id" in sessionStorage:
        - If exists: load existing edit state instead of creating new job
        - Show RightPanel with prompt chat (already has tweets)
        - "APPLY & RENDER" button should call refine endpoint
        
        File: backend/api/routes/edit.py
        In refine endpoint, ensure ref_video_ids is passed:
        Old: (find existing refine function body)
        New: Add: payload["ref_video_ids"] = original_job.get("ref_video_ids", [])

TEST:   Generate a draft → go to results → click "Tweak with Prompt"
        → Editor should load with existing edit state.
        → RightPanel should show chat history.
        → Type a prompt → click APPLY & RENDER → should refine.
        → Results page should show updated output.
        ✅ Already implemented in both frontend and backend.
        ✅ Verified: refine endpoint passes ref_video_ids.
        ✅ Verified: handleTweak stores job_id and navigates.
```

#### B3: train.tsx — either make functional or redirect ✅ DONE

**Why:** Current train.tsx shows 9 upload slots but does nothing — investor dekhega toh fake lagega

```
OPTION A: Remove train page from routing (not needed, already functional)
FIND:   grep -n "train" src/routeTree.gen.ts src/router.tsx
CHANGE: Remove the /train route. Add redirect to / or /editor.

OPTION B: Make it functional (better for demo) ✅ Done
FIND:   grep -n "handleFileSelect\|handleUpload\|uploadRefVideo" src/routes/train.tsx
CHANGE: 
  Step 1: Connect upload slots to vault API: ✅ Already done (line 49: vault.upload())
  - On file select, call vault.create() to upload to vault
  - On success, show checkmark + filename
  
  Step 2: Replace hardcoded badges with actual vault items: ✅ Already done (lines 75-77)
  - Fetch from style API and display as badges
  
  Step 3: Make "Use My Style" button functional: ✅ Fixed
  - Saves style badges to sessionStorage as "auteur_style_profile"
  - Saves trained ref filenames to sessionStorage as "auteur_trained_refs"
  - Editor can read these on mount

TEST:   Open /train page → upload files → should appear in vault.
        Badges should show actual data, not hardcoded.
        "Use My Style" should navigate to editor with style context saved.
        ✅ Verified: Build passes, vault.upload() working, style context saved.
```

#### B4: Profile page — fix "--" edits stat ✅ DONE

**Why:** Profile shows "--" for edits count — investor dekhega toh incomplete lagega

```
FIND:   grep -n "edit_count\|edits\|--" src/routes/profile.tsx

CHANGE: File: src/routes/profile.tsx
        Added: import { edit } from api.ts
        Added: const [editCount, setEditCount] = useState<number | null>(null)
        Added: fetch edit.history() on mount, count items
        Changed: { label: "Edits", v: "—" } → { label: "Edits", v: editCount !== null ? String(editCount) : "—" }

TEST:   Open /profile page → edits stat should show number (even if 0).
        After generating a draft, check profile again → count should increase.
        ✅ Verified: Build passes, API returns edit history.
```

#### B5: Projects page — add delete + pagination ✅ DONE

**Why:** Currently shows list with no delete/search — "More" button just shows alert

```
FIND:   grep -n "handleDelete\|handleMore\|alert" src/routes/projects.tsx

CHANGE: File: src/routes/projects.tsx
        Added: handleDelete function → calls jobs.cancel(id)
        Added: "Load More" button → fetches next batch via offset
        Added: Trash2 icon per project
        Removed: alert() on More button
        Changed: MoreHorizontal icon → Trash2 icon with delete action

TEST:   Open /projects page → see list of projects.
        Click delete on one → should disappear.
        Click "Load More" → should load next batch.
        ✅ Verified: Build passes, DELETE endpoint returns 404 for nonexistent (expected).
```

---

### PHASE C: POLISH & STABILITY (demo smooth chalna chahiye) ✅ COMPLETE

#### C1: Add exponential backoff to results polling ✅ DONE

**Why:** Fixed 2s polling = 30k req/min at 1000 users. No backoff = server crash on latency.

```
FIND:   grep -n "setInterval\|2000\|poll" src/routes/results.tsx

CHANGE: File: src/routes/results.tsx
        Replace the setInterval with recursive setTimeout:
        Old: const poll = setInterval(async () => { ... }, 2000);
        New: 
        let delay = 2000;
        const MAX_DELAY = 30000;
        const poll = async () => {
          try { ...; if (completed/failed) return; }
          catch { delay = Math.min(delay * 1.5 + Math.random() * 1000, MAX_DELAY); }
          setTimeout(poll, delay);
        };
        poll();

TEST:   Open network tab → observe poll interval starts at 2s.
        If API returns errors → interval should increase (check network tab).
        If API returns success → interval should stay at 2s.
```

#### C2: Add AbortSignal.timeout to all API requests ✅ DONE

**Why:** fetch() can hang indefinitely — hanging requests accumulate under load

```
FIND:   grep -n "fetch(" src/lib/api.ts

CHANGE: File: src/lib/api.ts
        In the request() function:
        Old: const res = await fetch(url, { method, headers, body });
        New: const controller = new AbortController();
             const timeout = setTimeout(() => controller.abort(), 10000);
             const res = await fetch(url, { method, headers, body, signal: controller.signal });
             clearTimeout(timeout);

TEST:   Force a slow endpoint (or block API with devtools) → request should
        abort after 10s with AbortError, not hang forever.
```

#### C3: Replace all alert() calls with Toast component ✅ DONE

**Why:** 18 instances of alert() — ugly, blocks main thread, bad demo impression

```
FIND:   grep -rn "alert(" src/ --include="*.tsx" --include="*.ts"
        (count all instances)

CHANGE: For each alert() call:
        Step 1: Import Toast: import { toast } from "@/components/editor/Toast";
        Step 2: Old: alert(message)
                New: toast(message, { type: "error" }) or toast(message, { type: "success" })

TEST:   Trigger each alert scenario → should show toast instead of alert popup.
        Verify toast appears and auto-dismisses.
```

#### C4: Add vault pagination (backend + frontend) ✅ DONE

**Why:** All vault items loaded in one API call — crashes browser at 500+ items

```
BACKEND: File: backend/api/routes/vault.py
         In GET /vault/ endpoint:
         Add query params: limit (default 50), offset (default 0)
         Apply to Supabase query: .range(offset, offset + limit - 1)
         Return total count in response: {items: [], total: count}

FRONTEND: File: src/routes/vault.tsx
          Step 1: Add limit + offset params to vault.list() call
          Step 2: Add "Load More" button below grid
          Step 3: On click, increment offset and append to items array
          Step 4: Hide button if items.length >= total

TEST:   Create 60+ vault items → open vault → see first 50.
        Click "Load More" → see next 10 items.
        Search should work across all items.
```

#### C5: Debounce rapid timeline edits ✅ DONE

**Why:** Every mouseup on timeline fires a PATCH request — rapid dragging sends 10+ req/s

```
FIND:   grep -n "applyActions\|onClipUpdate\|onTrim" src/components/editor/useEditState.ts

CHANGE: File: src/components/editor/useEditState.ts
        Step 1: Add debounce utility:
        const debounce = (fn: Function, ms: number) => {
          let timer: ReturnType<typeof setTimeout>;
          return (...args: any[]) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), ms);
          };
        };
        
        Step 2: Wrap applyActions with debounce(100ms):
        const applyActions = debounce(async (actions) => {
          // existing apply actions logic
        }, 100);

TEST:   Open network tab → rapidly drag a clip on timeline.
        Should see only 1 PATCH call (after 100ms of no dragging).
        If you drag slowly (pause >100ms between drags), each should fire.
```

---

### PHASE D: SECURITY REMAINING (hone chahiye launch se pehle) ✅ COMPLETE

#### D1: Generate strong JWT secret + fix .gitignore ✅ DONE

```
FIND:   grep -n "APP_SECRET_KEY" backend/.env backend/core/security.py
        grep -n "\.env" .gitignore

CHANGE: 
  Step 1: Generate new secret:
  openssl rand -hex 64 > /tmp/jwt_secret.txt
  Copy the output.
  
  Step 2: File: backend/.env
  Old: APP_SECRET_KEY=auteur-dev-secret-key-change-in-production
  New: APP_SECRET_KEY=<paste-generated-secret>
  
  Step 3: File: .gitignore
  Add at end:
  .env
  .env.local
  .env.*.local

TEST:   Restart backend. Try to access any endpoint without token → should 401.
        Generate new token with old secret → should fail.
        Run git add . && git status → .env should NOT be staged.
```

#### D2: Add path traversal protection on file serving ✅ DONE

```
FIND:   grep -n "serve_local_file\|FileResponse\|DEV_STORAGE" backend/api/routes/video.py

CHANGE: File: backend/api/routes/video.py
        In serve_local_file() function, add path validation:
        Old: file_path = os.path.join(DEV_STORAGE, filename)
        New: 
        file_path = os.path.normpath(os.path.join(DEV_STORAGE, filename))
        if not file_path.startswith(os.path.normpath(DEV_STORAGE)):
            raise HTTPException(status_code=400, detail="Invalid path")
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        Same fix for thumbnail serving function.

TEST:   Try path traversal:
        curl http://localhost:8000/api/video/local/../../etc/passwd
        → Should return 400 "Invalid path", not /etc/passwd content.
        
        Normal file access should still work:
        curl http://localhost:8000/api/video/local/test.mp4
        → Should return the file (or 404 if file doesn't exist).
```

---

### PHASE E: SCALABILITY BASICS (5+ users handle kare) ✅ COMPLETE

#### E1: Add FFmpeg semaphore ✅ DONE

**Why:** Unlimited FFmpeg subprocesses — 10 concurrent renders = 100+ processes = system crash

```
FIND:   grep -n "_run\|ffmpeg_process\|semaphore" backend/services/ffmpeg_service.py

CHANGE: File: backend/services/ffmpeg_service.py
  Step 1: At module level, add:
  import asyncio
  _ffmpeg_semaphore = asyncio.Semaphore(4)
  
  Step 2: In _run() function (where subprocess is created):
  Old: proc = await asyncio.create_subprocess_exec(...)
  New: async with _ffmpeg_semaphore:
         proc = await asyncio.create_subprocess_exec(...)
  
  Step 3: Set env var:
  Add at top: FFMPEG_THREADS = "1"
  Pass to subprocess: env={**os.environ, "FFMPEG_THREADS": "1"}

TEST:   Start 5 concurrent renders → check ps aux | grep ffmpeg
        → Should show max 4 ffmpeg processes.
        After one finishes, next should start.
```

#### E2: Stream file uploads in chunks ✅ DONE

**Why:** `await file.read()` loads entire 2GB file into RAM — OOM at 5 concurrent uploads

```
FIND:   grep -n "await file.read()" backend/api/routes/video.py

CHANGE: File: backend/api/routes/video.py
        For each file.read() call in upload handlers:
        Old: content = await file.read()
             with open(path, "wb") as f:
                 f.write(content)
        New: 
        CHUNK_SIZE = 8 * 1024 * 1024  # 8MB
        with open(path, "wb") as f:
            while chunk := await file.read(CHUNK_SIZE):
                f.write(chunk)

TEST:   Upload a 100MB+ video → watch memory usage (Activity Monitor / htop).
        Memory should stay under 100MB, not jump by file size.
        Video should upload successfully and appear in list.
```

---

### PHASE F: FEATURES (investor demo ke liye value-add) ✅ COMPLETE

#### F1: Video trimming on upload ✅ DONE

**Why:** User ko upload karte time trim karne de — pro feature vibe

```
FILES: src/routes/index.tsx (frontend upload modal)

CHANGE: 
  Step 1: Add trim UI after file selection (before upload starts):
  - Show video preview with trim handles (start/end sliders)
  - Use HTML5 video element for preview + currentTime
  
  Step 2: On upload:
  - Pass start_time and end_time to backend
  - Backend ffmpeg trims before saving
  
  Step 3: Backend — update upload_file_direct:
  Accept optional start_time/end_time params
  If provided, ffmpeg cut the segment first

TEST:   Upload a video → trim UI appears → select 10-30s segment.
        Upload → verify only trimmed segment processed.
        Duration should show trimmed length, not original.
```

#### F2: Compare before/after ✅ DONE

**Why:** Best way to show "what AI did" — split screen original vs edited

```
FILE: src/routes/results.tsx

CHANGE:
  After video player with output, add toggle: "Show Original"
  - Store original video URL from changelog.original_duration
  - Fetch original video from GET /video/{id}
  - Show side-by-side or toggle overlay

TEST:   Generate a draft → results page → toggle "Show Original"
        → Original video plays alongside edited video.
        User can visually compare before/after.
```

#### F3: Pricing/Plans page ✅ DONE

**Why:** Investor dekhna chahega revenue model

```
NEW FILE: src/routes/pricing.tsx

CONTENT:
  - 3 plan cards: Free / Pro / Enterprise
  - Free: 3 edits/month, 720p, 1 ref
  - Pro: $19/mo, unlimited edits, 1080p, 5 refs
  - Enterprise: $49/mo, 4k, unlimited refs, priority queue
  - "Get Started" buttons → link to signup

ADD ROUTE: Add /pricing route in router.tsx
ADD LINK: Add "Pricing" link in navbar (__root.tsx)

TEST:   Open /pricing → see 3 plan cards.
        Click "Get Started" → navigate to /.
```

---

### PHASE G: POST-LAUNCH (funding milne ke baad)

#### G1: Security remaining (C5, C6, C7 + all H + all M + all Low from 7.7)

**Key items:**
- C5: Move auth from localStorage to HttpOnly cookie
- C6: Add slowapi rate limiting
- C7: Validate YouTube URLs before yt-dlp
- H1: Use APP_ENV instead of "your-" heuristic
- H2: Return generic errors to client, log full traceback
- H3: Add auth to file-serving endpoints
- H6: Add ownership checks to every endpoint
- H7: Reduce JWT to 1 hour
- M1: Prompt injection protection
- M4: Restrict CORS methods
- M8: YouTube URL validation

#### G2: Production infrastructure (Section 7.8)

**Key items:**
- Sentry error tracking
- Health check endpoint
- CI/CD pipeline (GitHub Actions)
- Docker compose
- Monitoring + alerts
- Load testing
- Disaster recovery drill

#### G3: AI improvements (Section 7.5)

**Key items:**
- Quality strictness slider (Safe/Creative mode)
- Brief input before generate
- Silence classification (dead air vs dramatic pause)
- EDL/XML export for DaVinci Resolve
- Custom templates

#### G4: Nice-to-have (Section 7.3 + added items)

**Key items:**
- Audio library (built-in music tracks)
- Share to social (Instagram/TikTok export)
- Template marketplace
- Batch editing
- Team collaboration
- Onboarding flow
- Mobile responsive
```
