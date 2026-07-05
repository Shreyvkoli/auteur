import { useState, useRef, useEffect, useCallback } from "react";
import {
  Scissors,
  Type,
  Palette,
  Volume2,
  Sparkles,
  Layers,
  Zap,
  ChevronDown,
  Plus,
  Trash2,
  RotateCcw,
  Move,
  Loader2,
  Link2,
  Image,
  Music,
  FileText,
  Youtube,
  X,
  Send,
  Film,
  Wand2,
  Upload,
} from "lucide-react";
import type { EditState, Transition, Overlay, Keyframe, AudioTrack } from "@/lib/api";
import { editState as editStateApi, video as videoApi, BASE } from "@/lib/api";
import { ConfirmDialog } from "./ConfirmDialog";
import type { ChatAttachment } from "./useEditState";
import { toast } from "./Toast";

const TABS = [
  { key: "ai", label: "AI", icon: Sparkles },
] as const;

const TRANSITIONS = [
  "fade",
  "dissolve",
  "wipe_left",
  "wipe_right",
  "wipe_up",
  "wipe_down",
  "slide_left",
  "slide_right",
  "cross_fade",
  "luma_wipe",
  "spin",
];
const COLOR_GRADES = [
  "none",
  "warm",
  "cool",
  "cinematic",
  "vibrant",
  "matte",
  "vintage",
  "noir",
  "sunset",
  "neon",
  "dramatic",
];
const ASPECT_RATIOS = ["9:16", "16:9", "1:1", "4:5", "2.35:1"];
const TEXT_ANIMATIONS = ["none", "fade_in", "pop", "typewriter", "slide_up", "bounce", "zoom_in"];
const KEYFRAME_PROPERTIES = [
  "zoom",
  "x",
  "y",
  "opacity",
  "rotation",
  "blur",
  "brightness",
  "contrast",
  "saturation",
];

interface RightPanelProps {
  state: EditState;
  jobId: string;
  selectedClipId: string | null;
  onAction: (actions: any[]) => Promise<void>;
  onPrompt: (prompt: string, attachments?: ChatAttachment[]) => Promise<any>;
  onRender: () => Promise<any>;
  onAutoEdit?: () => Promise<any>;
  onPreviewRender?: () => Promise<any>;
  onDetectHighlights?: () => Promise<any>;
  onGenerateDraft?: (videoId: string, refVideoIds: string[], prompt: string) => Promise<void>;
}

export function RightPanel({
  state,
  jobId,
  selectedClipId,
  onAction,
  onPrompt,
  onRender,
  onAutoEdit,
  onPreviewRender,
  onDetectHighlights,
  onGenerateDraft,
}: RightPanelProps) {
  const [tab, setTab] = useState<string>("ai");
  const [prompt, setPrompt] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = inputRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = el.scrollHeight + "px";
    }
  }, [prompt]);
  const [aiPending, setAiPending] = useState(false);
  const [aiHistory, setAiHistory] = useState<{ role: "user" | "ai"; text: string; attachments?: ChatAttachment[]; patchesApplied?: boolean }[]>([]);

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [aiHistory]);

  useEffect(() => {
    if (!jobId) return;
    editStateApi.chat.list(jobId).then((res) => {
      if (res?.messages?.length) setAiHistory(res.messages as any);
    }).catch(() => {});
  }, [jobId]);
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [showAttach, setShowAttach] = useState(false);
  const [attachUrl, setAttachUrl] = useState("");
  const [attachType, setAttachType] = useState<ChatAttachment["type"]>("link");
  const [saving, setSaving] = useState(false);
  const [autoEditing, setAutoEditing] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [confirmDel, setConfirmDel] = useState<{ type: string; payload: any } | null>(null);
  const [refVideos, setRefVideos] = useState<string[]>([]);
  const [refVideoIds, setRefVideoIds] = useState<string[]>([]);
  const [refFilenames, setRefFilenames] = useState<Record<string, string>>({});
  const [showRefInput, setShowRefInput] = useState(false);
  const [refUrl, setRefUrl] = useState("");
  const [uploadingRef, setUploadingRef] = useState(false);
  const [generatingDraft, setGeneratingDraft] = useState(false);
  const refFileInputRef = useRef<HTMLInputElement>(null);
  const [editingTextId, setEditingTextId] = useState<string | null>(null);


  const segments = state?.timeline || [];
  const transitions = (state?.effects?.transitions || []).filter(
    (t: any) => t.type === "transition",
  );
  const textOverlays = (state?.overlays || []).filter((o) => o.type === "text");
  const audioTracks = state?.audio_tracks || [];
  const keyframes = state?.keyframes || [];
  const effects = state?.effects || {};

  const selectedSeg = segments.find((s) => s.id === selectedClipId);
  const selectedClip = selectedSeg ? state.clips.find((c) => c.id === selectedSeg.clip_id) : null;

  const saveMsg = useCallback((role: string, text: string, patchesApplied?: boolean) => {
    if (!jobId) return;
    editStateApi.chat.append(jobId, role, text, patchesApplied).catch(() => {});
  }, [jobId]);

  const handlePrompt = async () => {
    if (!prompt.trim() || aiPending) return;
    const msg = prompt.trim();
    const attachCopy = [...attachments];
    setPrompt("");
    setAttachments([]);
    const userMsg = { role: "user" as const, text: msg, attachments: attachCopy.length ? attachCopy : undefined };
    setAiHistory((h) => [...h, userMsg]);
    saveMsg("user", msg);
    setAiPending(true);
    const res = await onPrompt(msg, attachCopy.length ? attachCopy : undefined);
    const patchesApplied = (res?.applied_patches?.length ?? 0) > 0;
    setAiHistory((h) => [...h, {
      role: "ai",
      text: res?.message || "Done",
      patchesApplied,
    }]);
    saveMsg("ai", res?.message || "Done", patchesApplied);
    setAiPending(false);
  };

  const addAttachment = () => {
    if (!attachUrl.trim()) return;
    const id = `att_${Date.now()}`;
    let label = attachUrl.split("/").pop() || attachUrl;
    if (label.length > 30) label = label.slice(0, 30) + "...";
    setAttachments((prev) => [...prev, { id, type: attachType, label, url: attachUrl.trim() }]);
    setAttachUrl("");
    setShowAttach(false);
  };

  const removeAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  };



  const uploadRefVideo = async (file: File) => {
    setUploadingRef(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const token = localStorage.getItem("auteur_token");
      const res = await fetch(`${BASE}/video/upload-ref`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });
      if (!res.ok) throw new Error("Upload failed");
      const data = await res.json();
      setRefVideoIds((prev) => [...prev, data.ref_id]);
      setRefFilenames((prev) => ({ ...prev, [data.ref_id]: file.name }));
      setRefVideos((prev) => [...prev, data.ref_id]);
    } catch (e) {
      console.error("Ref upload failed:", e);
    }
    setUploadingRef(false);
  };

  const handleRefFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files?.length) return;
    for (const f of Array.from(files)) {
      await uploadRefVideo(f);
    }
    e.target.value = "";
  };

  const handleRefUrlImport = async () => {
    if (!refUrl.trim()) return;
    setUploadingRef(true);
    try {
      const res = await videoApi.importYoutube(refUrl.trim());
      setRefVideoIds((prev) => [...prev, res.video_id]);
      setRefFilenames((prev) => ({ ...prev, [res.video_id]: `yt_${res.video_id.slice(0, 8)}` }));
      setRefVideos((prev) => [...prev, res.video_id]);
      setRefUrl("");
      setShowRefInput(false);
    } catch (e) {
      console.error("YouTube import failed:", e);
    }
    setUploadingRef(false);
  };

  const handleGenerateDraft = async () => {
    if (!onGenerateDraft || generatingDraft) return;
    setGeneratingDraft(true);
    const params = new URLSearchParams(window.location.search);
    const vid = params.get("video_id") || sessionStorage.getItem("auteur_video_id");
    if (!vid) { setGeneratingDraft(false); return; }
    await onGenerateDraft(vid, refVideoIds, prompt);
    setGeneratingDraft(false);
  };

  const handleRender = async () => {
    setSaving(true);
    await onRender();
    setSaving(false);
  };

  const handleAutoEdit = async () => {
    if (!onAutoEdit || autoEditing) return;
    setAutoEditing(true);
    await onAutoEdit();
    setAutoEditing(false);
  };

  const handlePreviewRender = async () => {
    if (!onPreviewRender || previewing) return;
    setPreviewing(true);
    await onPreviewRender();
    setPreviewing(false);
  };

  const handleDetectHighlights = async () => {
    if (!onDetectHighlights || detecting) return;
    setDetecting(true);
    await onDetectHighlights();
    setDetecting(false);
  };

  const font = "'Space Grotesk',sans-serif";
  const dim = (_a?: number) => "#FAFAFA";
  const border = "rgba(255,255,255,0.07)";
  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "8px 10px",
    fontSize: 12,
    fontWeight: 500,
    background: "rgba(0,0,0,0.6)",
    border: "1px solid rgba(255,255,255,0.1)",
    color: "#FAFAFA",
    fontFamily: font,
    outline: "none",
    boxSizing: "border-box",
    borderRadius: 0,
  };
  const btnStyle = (color: string): React.CSSProperties => ({
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    padding: "7px 0",
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: "0.1em",
    textTransform: "uppercase" as const,
    fontFamily: font,
    background: color === "#DFE104" ? "#DFE104" : `${color}18`,
    border: color === "#DFE104" ? "1px solid #DFE104" : `1px solid ${color}40`,
    color: color === "#DFE104" ? "#000" : "#FAFAFA",
    cursor: "pointer",
    width: "100%",
    borderRadius: 0,
    transition: "all 0.15s ease",
  });
  const labelStyle: React.CSSProperties = {
    fontSize: 10,
    color: "#FAFAFA",
    letterSpacing: "0.16em",
    textTransform: "uppercase" as const,
    fontWeight: 700,
    marginTop: 2,
  };


  return (
    <>
      <style>{`
        @keyframes autoEditProgress {
          0% { width: 0; }
          50% { width: 70%; }
          100% { width: 90%; }
        }
        @keyframes dashHead {
          to { stroke-dashoffset: -4000; }
        }
        @keyframes dashTrail {
          to { stroke-dashoffset: -4008; }
        }
        @keyframes dashFaint {
          to { stroke-dashoffset: -4030; }
        }
        .dash-head { animation: dashHead 2.8s linear infinite; }
        .dash-trail { animation: dashTrail 2.8s linear infinite; }
        .dash-faint { animation: dashFaint 2.8s linear infinite; }
      `}</style>

      <div
        style={{
          width: "100%",
          display: "flex",
          flexDirection: "column",
          background: "#000",
          borderLeft: `1px solid ${border}`,
        }}
      >
      {/* Tab strip */}
  
        <div style={{
          display: "flex",
          flexShrink: 0,
          borderBottom: `1px solid ${border}`,
          overflowX: "auto",
          background: "#050507",
        }}>

        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            style={{
              flex: "0 0 auto",
              padding: "10px 14px",
              background: "transparent",
              border: "none",
              borderBottom: tab === key ? "2px solid #DFE104" : "2px solid transparent",
              color: tab === key ? "#DFE104" : "#FAFAFA",
              fontFamily: font,
              fontWeight: 700,
              fontSize: 10,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 5,
              transition: "color 150ms",
            }}
          >
            <Icon size={10} />
            {label}
          </button>
        ))}
      </div>

      {/* Panel body */}
      <div
        style={{
          flex: 1,
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          position: "relative",
        }}
      >
        {/* Scrollable content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "14px 14px 0 14px" }}>
            <div>
              {/* ── AI TAB ── */}
              {tab === "ai" && (
                <>
                  {/* Creator Memory */}
              <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                <button
                  onClick={async () => {
                    try {
                      await editStateApi.saveMemory(jobId);
                      toast("Style saved!", "success");
                    } catch {
                      toast("Failed to save style", "error");
                    }
                  }}
                  style={{
                    padding: "6px 12px",
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                    border: "1px solid rgba(223,225,4,0.3)",
                    cursor: "pointer",
                    background: "rgba(223,225,4,0.08)",
                    color: "#DFE104",
                    whiteSpace: "nowrap",
                    borderRadius: 0,
                    transition: "all 0.15s",
                  }}
                  title="Learn My Style"
                >
                  <Sparkles size={10} style={{ marginRight: 4 }} /> Style
                </button>
              </div>




              {/* ── Reference Videos Section ── */}
              <div style={{ marginBottom: 8 }}>
                <input
                  ref={refFileInputRef}
                  type="file"
                  accept="video/*"
                  multiple
                  style={{ display: "none" }}
                  onChange={handleRefFileSelect}
                />
                <div style={{
                  display: "flex", alignItems: "center", gap: 4, marginBottom: 4,
                  padding: "4px 0",
                }}>
                  <Film size={10} color="#DFE104" />
                  <span style={{ fontSize: 9, color: "#FAFAFA", letterSpacing: "0.15em", textTransform: "uppercase", fontWeight: 700 }}>
                    Reference Videos
                  </span>
                </div>

                {/* Ref list */}
                {refVideoIds.length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 3, marginBottom: 6 }}>
                    {refVideoIds.map((id, i) => (
                      <div key={id} style={{
                        display: "flex", alignItems: "center", gap: 4,
                        padding: "3px 6px", background: "rgba(223,225,4,0.06)",
                        border: "1px solid rgba(223,225,4,0.15)", fontSize: 10, color: "#FAFAFA",
                      }}>
                        <Film size={8} color="#DFE104" />
                        <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {refFilenames[id] || `Ref ${i + 1}`}
                        </span>
                        <button
                          onClick={() => {
                            setRefVideoIds((prev) => prev.filter((r) => r !== id));
                            setRefVideos((prev) => prev.filter((r) => r !== id));
                          }}
                          style={{ background: "none", border: "none", color: "#FAFAFA", cursor: "pointer", padding: 0, opacity: 0.5, lineHeight: 1 }}
                        >
                          <X size={8} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Add ref buttons */}
                <div style={{ display: "flex", gap: 4 }}>
                  <button
                    onClick={() => refFileInputRef.current?.click()}
                    disabled={uploadingRef}
                    style={{
                      display: "flex", alignItems: "center", justifyContent: "center", gap: 3,
                      flex: 1, padding: "5px 0", fontSize: 9, fontWeight: 700,
                      letterSpacing: "0.1em", textTransform: "uppercase",
                      border: "1px dashed rgba(255,255,255,0.2)", cursor: "pointer",
                      background: uploadingRef ? "rgba(255,255,255,0.03)" : "transparent",
                      color: uploadingRef ? "#A1A1AA" : "#FAFAFA", fontFamily: font, borderRadius: 0,
                      transition: "all 0.15s",
                    }}
                  >
                    {uploadingRef ? <Loader2 size={8} className="spin" /> : <Upload size={8} />}
                    Upload
                  </button>
                  <button
                    onClick={() => setShowRefInput((s) => !s)}
                    style={{
                      display: "flex", alignItems: "center", justifyContent: "center", gap: 3,
                      flex: 1, padding: "5px 0", fontSize: 9, fontWeight: 700,
                      letterSpacing: "0.1em", textTransform: "uppercase",
                      border: "1px dashed rgba(255,255,255,0.2)", cursor: "pointer",
                      background: showRefInput ? "rgba(223,225,4,0.08)" : "transparent",
                      color: showRefInput ? "#DFE104" : "#FAFAFA", fontFamily: font, borderRadius: 0,
                      transition: "all 0.15s",
                    }}
                  >
                    <Link2 size={8} /> URL
                  </button>
                </div>

                {/* YouTube URL input popup */}
                {showRefInput && (
                  <div style={{ display: "flex", gap: 4, alignItems: "center", marginTop: 4 }}>
                    <input
                      autoFocus
                      value={refUrl}
                      onChange={(e) => setRefUrl(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleRefUrlImport();
                        if (e.key === "Escape") { setShowRefInput(false); setRefUrl(""); }
                      }}
                      placeholder="youtube.com/watch?v=..."
                      style={{
                        flex: 1, padding: "3px 6px", fontSize: 10,
                        background: "rgba(0,0,0,0.6)", border: "1px solid rgba(223,225,4,0.3)",
                        color: "#FAFAFA", outline: "none", fontFamily: font,
                      }}
                    />
                    <button
                      onClick={handleRefUrlImport}
                      disabled={!refUrl.trim() || uploadingRef}
                      style={{
                        padding: "3px 8px", fontSize: 9, fontWeight: 700, border: "none",
                        cursor: refUrl.trim() && !uploadingRef ? "pointer" : "not-allowed",
                        background: refUrl.trim() && !uploadingRef ? "#DFE104" : "rgba(255,255,255,0.04)",
                        color: refUrl.trim() && !uploadingRef ? "#000" : "#FAFAFA",
                        fontFamily: font,
                      }}
                    >
                      Add
                    </button>
                  </div>
                )}
              </div>

              {/* ── Generate Draft Button ── */}
              <div
                style={{
                  width: "100%",
                  background: generatingDraft ? "rgba(223,225,4,0.08)" : "#DFE104",
                  borderRadius: 0,
                  overflow: "hidden",
                  cursor: generatingDraft ? "not-allowed" : "pointer",
                  border: generatingDraft ? "1px solid rgba(223,225,4,0.3)" : "1px solid #DFE104",
                  transition: "all 0.2s",
                }}
              >
                <button
                  onClick={handleGenerateDraft}
                  disabled={generatingDraft}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 6,
                    padding: "9px 20px",
                    fontSize: 11,
                    fontWeight: 700,
                    letterSpacing: "0.14em",
                    textTransform: "uppercase",
                    border: "none",
                    cursor: "inherit",
                    width: "100%",
                    background: "transparent",
                    color: generatingDraft ? "#DFE104" : "#000",
                    position: "relative",
                    zIndex: 1,
                    fontFamily: font,
                  }}
                >
                  <Wand2 size={12} />
                  {generatingDraft ? "GENERATING..." : "GENERATE DRAFT"}
                </button>
                {generatingDraft && (
                  <div
                    style={{
                      height: 2,
                      background: "#DFE104",
                      borderRadius: 0,
                      animation: "autoEditProgress 2s ease-in-out infinite",
                      transformOrigin: "left",
                    }}
                  />
                )}
              </div>

              {/* ── Apply & Render ── */}
              <button
                onClick={async () => {
                  try {
                    await onRender();
                  } catch {}
                }}
                disabled={saving}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                  padding: "9px 0",
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  borderRadius: 0,
                  border: saving ? "1px solid rgba(16,185,129,0.3)" : "1px solid #10b981",
                  cursor: "pointer",
                  width: "100%",
                  background: saving ? "rgba(16,185,129,0.08)" : "#10b981",
                  color: saving ? "#10b981" : "#000",
                  fontFamily: font,
                  transition: "all 0.2s",
                }}
              >
                {saving ? "RENDERING..." : "APPLY & RENDER"}
              </button>
            </>
          )}
            </div>
          </div>
      </div>
          {/* ── CHAT (always visible at bottom) ── */}
          <div
            style={{
              flexShrink: 0,
              display: "flex",
              flexDirection: "column",
              gap: 8,
              padding: "14px 14px 14px 14px",
              borderTop: "1px solid rgba(255,255,255,0.08)",
            }}
          >
              {/* Chat History */}
            <div
              ref={chatRef}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 8,
                maxHeight: 160,
                overflowY: "auto",
                padding: "4px 0",
              }}
            >
              {aiHistory.length === 0 && (
                <div style={{ textAlign: "center", padding: "10px 0", opacity: 0.4 }}>
                  <p style={{ fontSize: 10, color: "#FAFAFA", letterSpacing: "0.15em", textTransform: "uppercase" }}>Ask AI to edit</p>
                </div>
              )}
              {aiHistory.slice(-8).map((h, i) => (
                <div key={i} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 6, fontSize: 11 }}>
                    <div
                      style={{
                        width: 4,
                        height: 4,
                        marginTop: 5,
                        flexShrink: 0,
                        background: h.role === "user" ? "#DFE104" : "#A1A1AA",
                        clipPath: h.role === "user" ? "none" : "polygon(50% 0%, 100% 100%, 0% 100%)",
                      }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      {h.attachments && h.attachments.length > 0 && (
                        <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 4 }}>
                          {h.attachments.map((att) => (
                            <span
                              key={att.id}
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 3,
                                padding: "2px 6px",
                                fontSize: 10,
                                background: "rgba(37,99,235,0.1)",
                                border: "1px solid rgba(37,99,235,0.15)",
                                borderRadius: 4,
                                color: "#93c5fd",
                              }}
                            >
                              {att.type === "youtube" ? <Youtube size={9} /> : att.type === "image" ? <Image size={9} /> : att.type === "music" ? <Music size={9} /> : <Link2 size={9} />}
                              {att.label}
                            </span>
                          ))}
                        </div>
                      )}
                      <span style={{ color: h.role === "user" ? dim(0.85) : dim(0.55), lineHeight: 1.5 }}>
                        {h.text}
                      </span>
                    </div>
                  </div>
                  {h.role === "ai" && h.patchesApplied && (
                    <div style={{ marginLeft: 11, paddingLeft: 8, borderLeft: "1px solid rgba(255,255,255,0.06)" }}>
                      <span style={{ fontSize: 11, color: "#22c55e" }}>✓ Applied</span>
                    </div>
                  )}
                </div>
              ))}
              {aiPending && (
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: dim(0.4) }}>
                  <Loader2 size={10} className="spin" /> AI is thinking...
                </div>
              )}
            </div>

            {/* Attachments chips */}
            {attachments.length > 0 && (
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap", padding: "2px 0" }}>
                {attachments.map((att) => (
                  <span
                    key={att.id}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 3,
                      padding: "3px 8px",
                      fontSize: 11,
                      background: "rgba(37,99,235,0.12)",
                      border: "1px solid rgba(37,99,235,0.2)",
                      borderRadius: 4,
                      color: "#93c5fd",
                    }}
                  >
                    {att.type === "youtube" ? <Youtube size={9} /> : att.type === "image" ? <Image size={9} /> : att.type === "music" ? <Music size={9} /> : <Link2 size={9} />}
                    {att.label}
                    <button
                      onClick={() => removeAttachment(att.id)}
                      style={{
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        color: "#93c5fd",
                        padding: 0,
                        display: "flex",
                        opacity: 0.6,
                      }}
                    >
                      <X size={9} />
                    </button>
                  </span>
                ))}
              </div>
            )}

            {/* Input area */}
            <div
              className={`prompt-box-glass ${isFocused ? "focused" : ""} ${prompt.trim() ? "has-text" : ""}`}
              style={{
                display: "flex",
                gap: 4,
                alignItems: "stretch",
                borderRadius: "14px",
                padding: "4px",
                position: "relative",
                transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
              }}
            >
              {/* Animated borders for the entire capsule */}
              <svg
                style={{
                  position: "absolute",
                  top: -1,
                  left: -1,
                  width: "calc(100% + 2px)",
                  height: "calc(100% + 2px)",
                  pointerEvents: "none",
                  zIndex: 1,
                }}
              >
                <rect x="1" y="1" width="calc(100% - 2)" height="calc(100% - 2)" rx="14" fill="none" stroke="rgba(223,225,4,0.02)" strokeWidth="1.5" strokeDasharray="60 2000" strokeLinecap="round" className="dash-faint" />
                <rect x="1" y="1" width="calc(100% - 2)" height="calc(100% - 2)" rx="14" fill="none" stroke="rgba(223,225,4,0.15)" strokeWidth="1.5" strokeDasharray="18 2000" strokeLinecap="round" className="dash-trail" />
                <rect x="1" y="1" width="calc(100% - 2)" height="calc(100% - 2)" rx="14" fill="none" stroke="#DFE104" strokeWidth="2" strokeDasharray="5 2000" strokeLinecap="round" className="dash-head" />
              </svg>

              <div style={{ position: "relative", display: "flex", alignItems: "center", zIndex: 2 }}>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*,video/*,audio/*"
                  multiple
                  style={{ display: "none" }}
                  onChange={(e) => {
                    const files = Array.from(e.target.files || []);
                    files.forEach((f) => {
                      const id = `att_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
                      const type = f.type.startsWith("image/") ? "image" : f.type.startsWith("video/") ? "file" : f.type.startsWith("audio/") ? "music" : "file";
                      setAttachments((prev) => [...prev, { id, type: type as ChatAttachment["type"], label: f.name, url: URL.createObjectURL(f) }]);
                    });
                    e.target.value = "";
                  }}
                />
                <button
                  onClick={() => setShowAttach(!showAttach)}
                  className={`btn-plus-spin ${showAttach ? "active" : ""}`}
                  style={{
                    width: 32,
                    height: 32,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: showAttach ? "rgba(223,225,4,0.15)" : "transparent",
                    border: "none",
                    cursor: "pointer",
                    color: showAttach ? "#DFE104" : "rgba(250, 250, 250, 0.6)",
                    borderRadius: "10px",
                  }}
                  onMouseEnter={(e) => {
                    if (!showAttach) {
                      e.currentTarget.style.color = "#DFE104";
                      e.currentTarget.style.background = "rgba(223,225,4,0.08)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!showAttach) {
                      e.currentTarget.style.color = "rgba(250, 250, 250, 0.6)";
                      e.currentTarget.style.background = "transparent";
                    }
                  }}
                >
                  <Plus size={16} />
                </button>
                {showAttach && (
                  <div
                    style={{
                      position: "absolute",
                      bottom: 44,
                      left: 4,
                      width: 240,
                      background: "rgba(20, 20, 25, 0.85)",
                      backdropFilter: "blur(20px)",
                      WebkitBackdropFilter: "blur(20px)",
                      border: "1px solid rgba(223, 225, 4, 0.2)",
                      borderRadius: "12px",
                      zIndex: 100,
                      padding: 10,
                      boxShadow: "0 10px 30px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)",
                    }}
                  >
                    <p style={{ fontSize: 9, color: "rgba(250, 250, 250, 0.4)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 6 }}>Attach Reference</p>
                    <div style={{ display: "flex", gap: 4, marginBottom: 8, flexWrap: "wrap" }}>
                      <button
                        onClick={() => { fileInputRef.current?.click(); setShowAttach(false); }}
                        style={{
                          padding: "5px 8px",
                          fontSize: 10,
                          fontWeight: 600,
                          borderRadius: "6px",
                          border: "1px solid rgba(255, 255, 255, 0.05)",
                          cursor: "pointer",
                          background: "rgba(255,255,255,0.04)",
                          color: "rgba(250, 250, 250, 0.8)",
                          display: "flex",
                          alignItems: "center",
                          gap: 3,
                          transition: "all 0.15s",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = "rgba(255,255,255,0.08)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                        }}
                      >
                        <FileText size={10} /> File
                      </button>
                      {[
                        { t: "youtube" as const, l: "YouTube", i: Youtube },
                        { t: "image" as const, l: "Image URL", i: Image },
                        { t: "music" as const, l: "Music URL", i: Music },
                        { t: "link" as const, l: "Link", i: Link2 },
                      ].map(({ t, l, i: Icon }) => (
                        <button
                          key={t}
                          onClick={() => setAttachType(t)}
                          style={{
                            padding: "5px 8px",
                            fontSize: 10,
                            fontWeight: 600,
                            borderRadius: "6px",
                            border: "1px solid " + (attachType === t ? "rgba(37,99,235,0.3)" : "rgba(255,255,255,0.05)"),
                            cursor: "pointer",
                            background: attachType === t ? "rgba(37,99,235,0.25)" : "rgba(255,255,255,0.04)",
                            color: attachType === t ? "#93c5fd" : "rgba(250, 250, 250, 0.6)",
                            display: "flex",
                            alignItems: "center",
                            gap: 3,
                            transition: "all 0.15s",
                          }}
                        >
                          <Icon size={10} /> {l}
                        </button>
                      ))}
                    </div>
                    <div style={{ display: "flex", gap: 4 }}>
                      <input
                        autoFocus
                        value={attachUrl}
                        onChange={(e) => setAttachUrl(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") addAttachment(); if (e.key === "Escape") setShowAttach(false); }}
                        placeholder={attachType === "youtube" ? "youtube.com/watch?v=..." : attachType === "image" ? "https://..." : "Paste URL..."}
                        style={{
                          flex: 1,
                          padding: "5px 8px",
                          fontSize: 11,
                          background: "rgba(0,0,0,0.3)",
                          borderRadius: "6px",
                          border: "1px solid rgba(255,255,255,0.1)",
                          color: "#FAFAFA",
                          outline: "none",
                        }}
                      />
                      <button
                        onClick={addAttachment}
                        disabled={!attachUrl.trim()}
                        style={{
                          padding: "5px 10px",
                          fontSize: 11,
                          fontWeight: 600,
                          borderRadius: "6px",
                          border: "none",
                          cursor: attachUrl.trim() ? "pointer" : "not-allowed",
                          background: attachUrl.trim() ? "#DFE104" : "rgba(255,255,255,0.04)",
                          color: attachUrl.trim() ? "#000" : "#FAFAFA",
                        }}
                      >
                        Add
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div style={{ position: "relative", flex: 1, display: "flex", alignItems: "center", zIndex: 2 }}>
                <textarea
                  ref={inputRef}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handlePrompt();
                    }
                  }}
                  onFocus={() => setIsFocused(true)}
                  onBlur={() => setIsFocused(false)}
                  placeholder='e.g. "zoom at 0:15, add bold yellow caption"'
                  rows={1}
                  disabled={aiPending}
                  className="prompt-textarea-custom"
                  style={{
                    resize: "none",
                    width: "100%",
                    minHeight: 32,
                    maxHeight: 120,
                    overflowY: "auto",
                    border: "none",
                    background: "transparent",
                    fontSize: 11,
                    color: "#FAFAFA",
                    fontFamily: font,
                    outline: "none",
                    padding: "8px 4px 6px 4px",
                    boxSizing: "border-box",
                    lineHeight: 1.4,
                  }}
                />
              </div>

              <div style={{ display: "flex", alignItems: "center", paddingRight: 2, zIndex: 2 }}>
                <button
                  onClick={handlePrompt}
                  disabled={!prompt.trim() || aiPending}
                  className={prompt.trim() && !aiPending ? "btn-float-active" : ""}
                  style={{
                    width: 32,
                    height: 32,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: prompt.trim() && !aiPending ? "linear-gradient(135deg, #DFE104 0%, #00f0ff 100%)" : "transparent",
                    border: "none",
                    cursor: prompt.trim() && !aiPending ? "pointer" : "not-allowed",
                    color: prompt.trim() && !aiPending ? "#000" : "rgba(250, 250, 250, 0.3)",
                    borderRadius: "10px",
                    transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                    boxShadow: prompt.trim() && !aiPending ? "0 0 15px rgba(0, 240, 255, 0.45), 0 4px 10px rgba(223, 225, 4, 0.3)" : "none",
                  }}
                >
                  {aiPending ? <Loader2 size={12} className="spin" /> : <Send size={12} />}
                </button>
              </div>
            </div>

            {/* ── Reference URL Input ── */}
            {showRefInput && (
              <div style={{ display: "flex", gap: 4, alignItems: "center", paddingTop: 4 }}>
                <input
                  autoFocus
                  value={refUrl}
                  onChange={(e) => setRefUrl(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && refUrl.trim()) {
                      setRefVideos((prev) => [...prev, refUrl.trim()]);
                      setRefUrl("");
                      setShowRefInput(false);
                    }
                    if (e.key === "Escape") { setShowRefInput(false); setRefUrl(""); }
                  }}
                  placeholder="Paste YouTube / video URL..."
                  style={{
                    flex: 1,
                    padding: "3px 6px",
                    fontSize: 10,
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(223,225,4,0.3)",
                    color: "#FAFAFA",
                    outline: "none",
                    fontFamily: font,
                  }}
                />
                <button
                  onClick={() => {
                    if (refUrl.trim()) {
                      setRefVideos((prev) => [...prev, refUrl.trim()]);
                      setRefUrl("");
                      setShowRefInput(false);
                    }
                  }}
                  disabled={!refUrl.trim()}
                  style={{
                    padding: "3px 8px",
                    fontSize: 10,
                    fontWeight: 700,
                    border: "none",
                    cursor: refUrl.trim() ? "pointer" : "not-allowed",
                    background: refUrl.trim() ? "#DFE104" : "rgba(255,255,255,0.04)",
                    color: refUrl.trim() ? "#000" : "#FAFAFA",
                    fontFamily: font,
                  }}
                >
                  Add
                </button>
              </div>
            )}

            {/* ── Reference Videos ── */}
            <div style={{ display: "flex", alignItems: "center", gap: 4, paddingTop: 2 }}>
              {refVideos.map((url, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 3,
                    padding: "2px 6px",
                    background: "rgba(223,225,4,0.08)",
                    border: "1px solid rgba(223,225,4,0.2)",
                    fontSize: 10,
                    color: "#FAFAFA",
                    fontFamily: font,
                  }}
                >
                  <Film size={9} color="#DFE104" />
                  <span style={{ maxWidth: 80, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    Ref {i + 1}
                  </span>
                  <button
                    onClick={() => setRefVideos((prev) => prev.filter((_, j) => j !== i))}
                    style={{ background: "none", border: "none", color: "#FAFAFA", cursor: "pointer", padding: 0, opacity: 0.5 }}
                  >
                    <X size={8} />
                  </button>
                </div>
              ))}
              {Array.from({ length: Math.max(0, 5 - refVideos.length) }).map((_, i) => (
                <div key={`slot_${i}`} style={{ position: "relative" }}>
                  <button
                    onClick={() => setShowRefInput(true)}
                    onMouseEnter={(e) => {
                      const tooltip = e.currentTarget.parentElement?.querySelector(".ref-tooltip") as HTMLElement;
                      if (tooltip) tooltip.style.display = "block";
                    }}
                    onMouseLeave={(e) => {
                      const tooltip = e.currentTarget.parentElement?.querySelector(".ref-tooltip") as HTMLElement;
                      if (tooltip) tooltip.style.display = "none";
                    }}
                    style={{
                      width: 22,
                      height: 22,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      background: "rgba(255,255,255,0.06)",
                      border: "1px dashed rgba(255,255,255,0.15)",
                      cursor: "pointer",
                      color: "#FAFAFA",
                      transition: "all 120ms",
                    }}
                  >
                    <Plus size={10} />
                  </button>
                  <div
                    className="ref-tooltip"
                    style={{
                      display: "none",
                      position: "absolute",
                      bottom: 28,
                      left: "50%",
                      transform: "translateX(-50%)",
                      whiteSpace: "nowrap",
                      background: "#1a1a1e",
                      border: "1px solid rgba(255,255,255,0.1)",
                      padding: "4px 8px",
                      fontSize: 10,
                      color: "#FAFAFA",
                      fontFamily: font,
                      zIndex: 50,
                      pointerEvents: "none",
                    }}
                  >
                    Add reference video for accurate AI results
                  </div>
                </div>
              ))}
            </div>
          </div>
      </div>

      {/* Confirm Delete */}
      <ConfirmDialog
        open={!!confirmDel}
        title={`Delete ${confirmDel?.type || "item"}`}
        message={
          confirmDel?.type === "clip"
            ? "Delete this clip from the timeline? (⌘Z to undo)"
            : confirmDel?.type === "transition"
              ? "Remove this transition?"
              : `Delete this ${confirmDel?.type}?`
        }
        onConfirm={() => {
          if (!confirmDel) return;
          const { type, payload } = confirmDel;
          if (type === "clip") onAction([{ action: "delete", clip_id: payload.clip_id }]);
          else if (type === "transition") {
            const between = payload.between;
            if (between?.length >= 2)
              onAction([
                { action: "remove_transition", clip_a_id: between[0], clip_b_id: between[1] },
              ]);
          } else if (type === "text_overlay") onAction([{ action: "delete", clip_id: payload.id }]);
          else if (type === "effect")
            onAction([{ action: "remove_effect", effect_id: payload.id }]);
          else if (type === "audio") onAction([{ action: "delete", clip_id: payload.id }]);
          else if (type === "keyframe")
            onAction([{ action: "remove_keyframe", keyframe_id: payload.id }]);
          setConfirmDel(null);
        }}
        onCancel={() => setConfirmDel(null)}
      />
    </>
  );
}
