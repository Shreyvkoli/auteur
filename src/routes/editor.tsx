import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useRef, useEffect, useCallback } from "react";
import { ArrowLeft, Loader2, Link2, ArrowRight, Play, Keyboard, Undo2, Redo2 } from "lucide-react";
import { video as videoApi, uploadVideo, editState, edit as editApi, BASE } from "@/lib/api";
import { useEditState } from "@/components/editor/useEditState";
import { Timeline } from "@/components/editor/Timeline";
import { PlaybackControls } from "@/components/editor/PlaybackControls";
import { RightPanel } from "@/components/editor/RightPanel";
import { VideoOverlays } from "@/components/editor/VideoOverlays";
import { ResizableDivider } from "@/components/editor/ResizableDivider";
import { ConfirmDialog } from "@/components/editor/ConfirmDialog";
import { ToastContainer, useToast, toast } from "@/components/editor/Toast";
import { LeftPanel } from "@/components/editor/LeftPanel";
import { useMediaQuery } from "@/hooks/useMediaQuery";

export const Route = createFileRoute("/editor")({ component: Editor });

function Editor() {
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const [hasVideo, setHasVideo] = useState(false);
  const [videoUrl, setVideoUrl] = useState("");
  const [vidDur, setVidDur] = useState(0);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [upPct, setUpPct] = useState(0);
  const [upMsg, setUpMsg] = useState("");
  const [ytLink, setYtLink] = useState("");
  const [showYt, setShowYt] = useState(false);
  const [vidName, setVidName] = useState(() => {
    if (typeof window === "undefined") return "No video loaded";
    return sessionStorage.getItem("auteur_video_filename") || "No video loaded";
  });
  const [drag, setDrag] = useState(false);

  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [selClipId, setSelClipId] = useState<string | null>(null);

  const [panelWidth, setPanelWidth] = useState(300);
  const [timelineHeight, setTimelineHeight] = useState(200);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [showLeftPanel, setShowLeftPanel] = useState(true);

  const {
    state,
    loading: stateLoading,
    loadState,
    createJob,
    applyActions,
    applyActionsDebounced,
    sendPrompt,
    undoAction,
    redoAction,
    renderDirty,
    exportVideo,
    autoEdit,
    previewRender,
    detectHighlights,
    jobId,
  } = useEditState();
  const isMobile = useMediaQuery("(max-width: 768px)");
  const { toasts: toastMsgs, addToast, dismiss: dismissToast } = useToast();

  const undoWithToast = useCallback(async () => {
    await undoAction();
    addToast("Undone", "info");
  }, [undoAction]);

  const redoWithToast = useCallback(async () => {
    await redoAction();
    addToast("Redone", "info");
  }, [redoAction]);

  const duration = state?.metadata?.total_duration || vidDur || 1;

  /* Boot */
  useEffect(() => {
    const vid = sessionStorage.getItem("auteur_video_id");
    const jid = sessionStorage.getItem("auteur_current_job_id");
    if (!vid) return;
    setHasVideo(true);
    setLoading(true);
    const dur = parseFloat(sessionStorage.getItem("auteur_video_duration") || "0");
    if (dur) setVidDur(dur);
    videoApi
      .get(vid)
      .then((r: any) => {
        setVideoUrl(r.cloudinary_url || `${BASE}/video/local/${vid}.mp4`);
        setLoading(false);
      })
      .catch(() => {
        setVideoUrl(`${BASE}/video/local/${vid}.mp4`);
        setLoading(false);
      });
    if (jid) {
      loadState(jid);
    } else {
      createJob(vid);
    }
  }, []);

  /* Time update */
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    const fn = () => setCurrentTime(v.currentTime);
    v.addEventListener("timeupdate", fn);
    return () => v.removeEventListener("timeupdate", fn);
  }, [videoUrl]);

  /* Keyboard shortcuts */
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.code === "Space") {
        e.preventDefault();
        togglePlay();
      }
      if (e.code === "KeyZ" && (e.metaKey || e.ctrlKey) && !e.shiftKey) {
        e.preventDefault();
        undoWithToast();
      }
      if (e.code === "KeyZ" && (e.metaKey || e.ctrlKey) && e.shiftKey) {
        e.preventDefault();
        redoWithToast();
      }
      if (e.code === "ArrowLeft") {
        e.preventDefault();
        stepBackward();
      }
      if (e.code === "ArrowRight") {
        e.preventDefault();
        stepForward();
      }
      if (e.code === "KeyS" && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        const seg = state?.timeline?.find(
          (s: any) => currentTime >= s.timeline_start && currentTime < s.timeline_end
        );
        if (seg) {
          const at = seg.source_start + (currentTime - seg.timeline_start) * (seg.speed || 1);
          applyActions([{ action: "split", clip_id: seg.clip_id, at }]);
        }
      }
      if (e.code === "Delete" && selClipId) {
        e.preventDefault();
        setConfirmDelete(selClipId);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [selClipId, state]);

  /* Upload */
  const handleFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    const f = files[0];
    if (!f.type.startsWith("video/")) {
      toast("Please upload a video file", "error");
      return;
    }
    setUploading(true);
    setUpMsg("Starting...");
    try {
      const r = await uploadVideo(f, (s, p) => {
        setUpMsg(s);
        setUpPct(p);
      });
      sessionStorage.setItem("auteur_video_id", r.video_id);
      sessionStorage.setItem("auteur_video_duration", String(r.duration));
      sessionStorage.setItem("auteur_video_filename", f.name);
      setVidName(f.name);
      setVidDur(r.duration);
      videoApi
        .get(r.video_id)
        .then((res: any) =>
          setVideoUrl(
            res.cloudinary_url || `${BASE}/video/local/${r.video_id}.mp4`,
          ),
        )
        .catch(() => setVideoUrl(`${BASE}/video/local/${r.video_id}.mp4`));
      setUploading(false);
      setHasVideo(true);
      const jid = await createJob(r.video_id);
      if (!jid) toast("Video uploaded but failed to create edit job. Check backend.", "error");
    } catch (e: any) {
      setUploading(false);
      toast(e.message, "error");
    }
  };

  const handleYt = async () => {
    if (!ytLink) return;
    setUploading(true);
    setUpMsg("Importing...");
    try {
      const r = await videoApi.importYoutube(ytLink);
      sessionStorage.setItem("auteur_video_id", r.video_id);
      sessionStorage.setItem("auteur_video_duration", String(r.duration));
      sessionStorage.setItem("auteur_video_filename", "youtube.mp4");
      setVidName("youtube.mp4");
      setVidDur(r.duration);
      videoApi
        .get(r.video_id)
        .then((res: any) =>
          setVideoUrl(
            res.cloudinary_url || `${BASE}/video/local/${r.video_id}.mp4`,
          ),
        )
        .catch(() => setVideoUrl(`${BASE}/video/local/${r.video_id}.mp4`));
      setUploading(false);
      setHasVideo(true);
      setShowYt(false);
      setYtLink("");
      const jid = await createJob(r.video_id);
      if (!jid) toast("Video imported but failed to create edit job. Check backend.", "error");
    } catch (e: any) {
      setUploading(false);
      toast(e.message, "error");
    }
  };

  const handleGenerateDraft = useCallback(async (videoId: string, refVideoIds: string[], prompt: string) => {
    try {
      const res = await editApi.create({
        video_id: videoId,
        ref_video_ids: refVideoIds,
        prompt: prompt || "Make a viral edit following the reference style",
        version_type: "viral",
        mode: state?.mode || "reels",
      });
      sessionStorage.setItem("auteur_job_id", res.job_id);
      navigate({ to: "/results" });
    } catch (e: any) {
      toast(e.message || "Failed to generate draft", "error");
    }
  }, [navigate, state]);

  const togglePlay = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) {
      v.play();
      setPlaying(true);
    } else {
      v.pause();
      setPlaying(false);
    }
  }, []);

  const handleSeek = useCallback((time: number) => {
    if (videoRef.current) videoRef.current.currentTime = time;
    setCurrentTime(time);
  }, []);

  const stepForward = useCallback(() => {
    if (videoRef.current) {
      const fps = state?.metadata?.fps || 30;
      videoRef.current.currentTime = Math.min(duration, videoRef.current.currentTime + 1 / fps);
      setCurrentTime(videoRef.current.currentTime);
    }
  }, [duration, state?.metadata?.fps]);

  const stepBackward = useCallback(() => {
    if (videoRef.current) {
      const fps = state?.metadata?.fps || 30;
      videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime - 1 / fps);
      setCurrentTime(videoRef.current.currentTime);
    }
  }, [state?.metadata?.fps]);

  const handleSpeedChange = useCallback((s: number) => {
    setSpeed(s);
    if (videoRef.current) videoRef.current.playbackRate = s;
  }, []);

  const bg0 = "#09090B";
  const bg1 = "#111113";
  const font = "'Space Grotesk','Inter',sans-serif";
  const dim = (_a?: number) => "#FAFAFA";

  if (loading)
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100vh",
          background: bg0,
          fontFamily: font,
        }}
      >
        <Loader2 size={24} color="#A1A1AA" className="spin" />
      </div>
    );

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        background: bg0,
        fontFamily: font,
        overflow: "hidden",
      }}
    >
      {/* ═══ TOP BAR ═══ */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          height: 44,
          padding: "0 12px",
          background: "#000",
          borderBottom: "1px solid rgba(255,255,255,0.07)",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
          <button
            onClick={() => navigate({ to: "/" })}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "6px 10px",
              color: dim(0.6),
              borderRadius: 4,
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.06)";
              e.currentTarget.style.color = dim(0.9);
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = "transparent";
              e.currentTarget.style.color = dim(0.6);
            }}
          >
            <ArrowLeft size={14} />
            <span style={{ fontSize: 14, fontWeight: 500, fontFamily: font }}>Home</span>
          </button>
          <div style={{ width: 1, height: 16, background: "rgba(255,255,255,0.07)" }} />
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: hasVideo ? "#22c55e" : "rgba(255,255,255,0.15)",
              }}
            />
            <span
              style={{
                fontSize: 15,
                color: dim(0.55),
                fontFamily: font,
                maxWidth: 200,
                overflow: "hidden",
                whiteSpace: "nowrap",
                textOverflow: "ellipsis",
              }}
            >
              {vidName}
            </span>
          </div>
        </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                fontSize: 13,
                fontWeight: 700,
                letterSpacing: "0.28em",
                textTransform: "uppercase",
                color: "#DFE104",
                fontFamily: font,
              }}
            >
              AUTEUR
            </span>
          </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            flex: 1,
            justifyContent: "flex-end",
          }}
        >
          {jobId && (
            <>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                  padding: "0 10px",
                  height: 28,
                  border: "1px solid rgba(223,225,4,0.35)",
                  background: "rgba(223,225,4,0.06)",
                }}
              >
                <div
                  className="pulse"
                  style={{
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    background: "#DFE104",
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: "#DFE104",
                    letterSpacing: "0.18em",
                    textTransform: "uppercase",
                    fontFamily: font,
                  }}
                >
                  v{state?.version || 1}
                </span>
              </div>
              <button
                onClick={() => setShowLeftPanel((s) => !s)}
                title="Toggle Asset Browser"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                  padding: "0 10px",
                  height: 28,
                  background: "transparent",
                  border: "1px solid rgba(255,255,255,0.08)",
                  color: showLeftPanel ? dim(0.9) : dim(0.5),
                  cursor: "pointer",
                  fontFamily: font,
                  fontSize: 15,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = dim(0.9);
                  e.currentTarget.style.borderColor = "rgba(255,255,255,0.2)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = showLeftPanel ? dim(0.9) : dim(0.5);
                  e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)";
                }}
              >
                {showLeftPanel ? "Assets" : "Assets"}
              </button>
              <button
                onClick={undoWithToast}
                title="Undo (⌘Z)"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "0 8px",
                  height: 28,
                  background: "transparent",
                  border: "1px solid rgba(255,255,255,0.08)",
                  color: dim(0.5),
                  cursor: "pointer",
                  fontSize: 15,
                  fontFamily: font,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = dim(0.9);
                  e.currentTarget.style.borderColor = "rgba(255,255,255,0.2)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = dim(0.5);
                  e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)";
                }}
              >
                <Undo2 size={11} />
              </button>
              <button
                onClick={redoWithToast}
                title="Redo (⌘⇧Z)"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "0 8px",
                  height: 28,
                  background: "transparent",
                  border: "1px solid rgba(255,255,255,0.08)",
                  color: dim(0.5),
                  cursor: "pointer",
                  fontSize: 15,
                  fontFamily: font,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = dim(0.9);
                  e.currentTarget.style.borderColor = "rgba(255,255,255,0.2)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = dim(0.5);
                  e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)";
                }}
              >
                <Redo2 size={11} />
              </button>
              <button
                onClick={exportVideo}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                  padding: "0 12px",
                  height: 28,
                  border: "none",
                  background: "#DFE104",
                  color: "#000",
                  cursor: "pointer",
                  fontFamily: font,
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  borderRadius: 0,
                  transition: "transform 120ms",
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.transform = "scale(1.04)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.transform = "scale(1)"; }}
                title="Export Video"
              >
                EXPORT
              </button>
            </>
          )}
        </div>
      </div>

      {/* ═══ MAIN CONTENT ═══ */}
      <div
        style={{
          display: "flex",
          flex: 1,
          overflow: "hidden",
          flexDirection: isMobile ? "column" : "row",
        }}
      >
        {/* ─── LEFT + VIDEO + TIMELINE COLUMN ─── */}
        <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
          {/* ─── LEFT PANEL + VIDEO AREA ROW ─── */}
          <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
            {showLeftPanel && !isMobile && <LeftPanel videoUrl={videoUrl} />}

            {/* ─── VIDEO AREA ─── */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                flex: 1,
                overflow: "hidden",
                background: "#000",
              }}
            >
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  position: "relative",
                  background: "#000",
                  overflow: "hidden",
                }}
              >
                {!hasVideo && !uploading && (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 24,
                      textAlign: "center",
                      maxWidth: 320,
                    }}
                  >
                    <div
                      onDragOver={(e) => {
                        e.preventDefault();
                        setDrag(true);
                      }}
                      onDragLeave={() => setDrag(false)}
                      onDrop={(e) => {
                        e.preventDefault();
                        setDrag(false);
                        handleFiles(e.dataTransfer.files);
                      }}
                      onClick={() => fileRef.current?.click()}
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: 16,
                        padding: "48px 32px",
                        cursor: "pointer",
                        border: `2px dashed ${drag ? "#DFE104" : "rgba(255,255,255,0.12)"}`,
                        background: drag ? "rgba(223,225,4,0.04)" : "transparent",
                        transition: "all 200ms",
                        width: 300,
                      }}
                    >
                      <input
                        ref={fileRef}
                        type="file"
                        accept="video/*"
                        style={{ display: "none" }}
                        onChange={(e) => handleFiles(e.target.files)}
                      />
                      <div
                        style={{
                          width: 52,
                          height: 52,
                          borderRadius: 0,
                          background: drag ? "#DFE104" : "rgba(255,255,255,0.04)",
                          border: drag ? "none" : "1px solid rgba(255,255,255,0.12)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          transition: "all 200ms",
                        }}
                      >
                        <Play size={18} color={drag ? "#000" : "rgba(255,255,255,0.4)"} style={{ marginLeft: 2 }} />
                      </div>
                      <div>
                        <p style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: drag ? "#DFE104" : "#FAFAFA" }}>
                          {drag ? "DROP IT ↓" : "DRAG & DROP"}
                        </p>
                        <p style={{ fontSize: 10, color: "#FAFAFA", letterSpacing: "0.14em", textTransform: "uppercase", marginTop: 6 }}>
                          MP4 · MOV · AVI
                        </p>
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 12, width: 280 }}>
                      <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.06)" }} />
                      <span
                        style={{
                          fontSize: 14,
                          color: dim(0.4),
                          letterSpacing: "0.15em",
                          textTransform: "uppercase",
                        }}
                      >
                        or
                      </span>
                      <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.06)" }} />
                    </div>
                    {!showYt ? (
                      <button
                        onClick={() => setShowYt(true)}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          padding: "8px 16px",
                          background: "transparent",
                          border: "1px solid rgba(255,255,255,0.08)",
                          color: dim(0.55),
                          cursor: "pointer",
                          fontSize: 14,
                          fontFamily: font,
                          fontWeight: 500,
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.borderColor = "rgba(255,255,255,0.15)";
                          e.currentTarget.style.color = dim(0.85);
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)";
                          e.currentTarget.style.color = dim(0.55);
                        }}
                      >
                        <Link2 size={13} /> Import from YouTube
                      </button>
                    ) : (
                      <div style={{ display: "flex", width: 280 }}>
                        <div
                          style={{
                            display: "flex",
                            flex: 1,
                            alignItems: "center",
                            gap: 8,
                            padding: "0 12px",
                            background: "rgba(255,255,255,0.04)",
                            border: "1px solid rgba(255,255,255,0.1)",
                            borderRight: "none",
                            height: 42,
                          }}
                        >
                          <Link2 size={13} color="rgba(255,255,255,0.25)" />
                          <input
                            autoFocus
                            value={ytLink}
                            onChange={(e) => setYtLink(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleYt();
                              if (e.key === "Escape") setShowYt(false);
                            }}
                            placeholder="youtube.com/watch?v=..."
                            style={{
                              flex: 1,
                              background: "transparent",
                              border: "none",
                              outline: "none",
                              color: dim(0.85),
                              fontSize: 15,
                              fontFamily: font,
                            }}
                          />
                        </div>
                        <button
                          onClick={handleYt}
                          disabled={!ytLink}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            width: 42,
                            height: 42,
                            background: ytLink ? "rgba(255,255,255,0.1)" : "transparent",
                            border: "1px solid rgba(255,255,255,0.1)",
                            cursor: ytLink ? "pointer" : "not-allowed",
                          }}
                        >
                          <ArrowRight size={14} color="rgba(255,255,255,0.5)" />
                        </button>
                      </div>
                    )}
                  </div>
                )}
                {uploading && (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 16,
                      padding: 40,
                    }}
                  >
                    <Loader2 size={28} color="rgba(255,255,255,0.25)" className="spin" />
                    <p style={{ fontSize: 14, color: dim(0.65) }}>{upMsg}</p>
                    <div style={{ width: 180 }}>
                      <div style={{ height: 1, background: "rgba(255,255,255,0.1)" }}>
                        <div
                          style={{
                            height: "100%",
                            width: `${upPct}%`,
                            background: "rgba(255,255,255,0.45)",
                            transition: "width 400ms",
                          }}
                        />
                      </div>
                      <p
                        style={{
                          fontSize: 14,
                          color: dim(0.45),
                          marginTop: 6,
                          textAlign: "center",
                        }}
                      >
                        {Math.round(upPct)}%
                      </p>
                    </div>
                  </div>
                )}
                {hasVideo && videoUrl && (
                  <div style={{ position: "relative", width: "100%", height: "100%", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }} onClick={togglePlay}>
                    <video
                      ref={videoRef}
                      src={videoUrl}
                      muted={isMuted}
                      onEnded={() => setPlaying(false)}
                      style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain", display: "block" }}
                    />
                    <VideoOverlays
                      videoRef={videoRef}
                      overlays={state?.overlays || []}
                      captions={state?.captions || []}
                      currentTime={currentTime}
                    />
                  </div>
                )}
              </div>

              <PlaybackControls
                currentTime={currentTime}
                duration={duration}
                playing={playing}
                isMuted={isMuted}
                speed={speed}
                onTogglePlay={togglePlay}
                onSeek={handleSeek}
                onToggleMute={() => setIsMuted((m) => !m)}
                onStepForward={stepForward}
                onStepBackward={stepBackward}
                onSpeedChange={handleSpeedChange}
              />
            </div>
          </div>

          {/* ─── DIVIDER + TIMELINE ─── */}
          {state && (
            <>
              {!isMobile && (
                <ResizableDivider
                  direction="vertical"
                  onResize={(delta) =>
                    setTimelineHeight((h) => Math.max(100, Math.min(500, h - delta)))
                  }
                />
              )}
              <div
                style={{
                  height: isMobile ? 150 : timelineHeight,
                  flexShrink: 0,
                }}
              >
                <Timeline
                  state={state}
                  currentTime={currentTime}
                  duration={duration}
                  selectedClipId={selClipId}
                  onSelectClip={setSelClipId}
                  onSeek={handleSeek}
                  onAction={applyActionsDebounced}
                />
              </div>
            </>
          )}
        </div>

        {/* ─── DIVIDER + RIGHT PANEL ─── */}
        {jobId && !isMobile && (
          <>
            <ResizableDivider
              direction="horizontal"
              onResize={(delta) => setPanelWidth((w) => Math.max(200, Math.min(600, w - delta)))}
            />
            <div style={{ width: panelWidth, flexShrink: 0 }}>
              <RightPanel
                state={state!}
                jobId={jobId}
                selectedClipId={selClipId}
                onAction={applyActions}
                onPrompt={sendPrompt}
                onRender={renderDirty}
                onAutoEdit={autoEdit}
                onPreviewRender={previewRender}
                onDetectHighlights={detectHighlights}
                onGenerateDraft={handleGenerateDraft}
              />
            </div>
          </>
        )}
      </div>

      {/* Confirm Delete */}
      <ConfirmDialog
        open={!!confirmDelete}
        title="Delete Clip"
        message="Are you sure you want to delete this clip? This action can be undone with ⌘Z."
        onConfirm={() => {
          if (confirmDelete) {
            applyActions([{ action: "delete", clip_id: confirmDelete }]);
            setSelClipId(null);
          }
          setConfirmDelete(null);
        }}
        onCancel={() => setConfirmDelete(null)}
      />

      {/* Toast notifications */}
      <ToastContainer toasts={toastMsgs} onDismiss={dismissToast} />

      {/* Keyboard Shortcuts Help */}
      {showShortcuts && (
        <div
          onClick={() => setShowShortcuts(false)}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 300,
            background: "rgba(0,0,0,0.8)",
            backdropFilter: "blur(8px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 16,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "#111113",
              border: "1px solid rgba(255,255,255,0.08)",
              maxWidth: 400,
              width: "100%",
              padding: 24,
            }}
          >
            <p
              style={{
                fontSize: 14,
                fontWeight: 700,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                color: "#FAFAFA",
                marginBottom: 16,
                fontFamily: font,
              }}
            >
              Keyboard Shortcuts
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {[
                ["Space", "Play / Pause"],
                ["← / →", "Step backward / forward"],
                ["⌘Z", "Undo"],
                ["⌘⇧Z", "Redo"],
                ["Delete", "Delete selected clip"],
              ].map(([key, desc]) => (
                <div
                  key={key}
                  style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
                >
                  <kbd
                    style={{
                      padding: "3px 8px",
                      background: "rgba(255,255,255,0.06)",
                      border: "1px solid rgba(255,255,255,0.1)",
                      fontSize: 14,
                      fontFamily: "monospace",
                      color: dim(0.8),
                    }}
                  >
                    {key}
                  </kbd>
                  <span style={{ fontSize: 15, color: dim(0.5) }}>{desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

