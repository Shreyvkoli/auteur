import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import {
  ArrowLeft, Download, Loader2, CheckCircle2, AlertCircle, Wand2, Clock,
  Brain, Film, Edit3, ThumbsUp, Target,
} from "lucide-react";
import { edit, jobs, video as videoApi, type JobStatus, type ChangelogEntry } from "@/lib/api";
import { TimelineSummary } from "@/components/editor/TimelineSummary";

export const Route = createFileRoute("/results")({ component: ResultsScreen });

const STEP_KEYS = ["queued", "transcribing", "analyzing_style", "generating_plan", "rendering", "completed"];
const STEP_LABELS = ["QUEUED", "TRANSCRIBE", "ANALYZE", "PLAN", "RENDER", "DONE"];

function ResultsScreen() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("queued");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("Waiting in queue...");
  const [error, setError] = useState("");
  const [outputUrl, setOutputUrl] = useState("");
  const [changelog, setChangelog] = useState<ChangelogEntry | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);
  const [originalUrl, setOriginalUrl] = useState("");
  const [jobId, setJobId] = useState<string | null>(() => sessionStorage.getItem("auteur_job_id"));

  useEffect(() => {
    if (!jobId) { navigate({ to: "/" }); return; }
    let delay = 2000;
    const MAX_DELAY = 30000;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      if (cancelled) return;
      try {
        const res: JobStatus = await edit.status(jobId);
        if (cancelled) return;
        setStatus(res.status);
        setProgress(res.progress || 0);
        setMessage(res.message || "");
        if (res.error) setError(res.error);
        if (res.output_video) setOutputUrl(res.output_video.url || "");
        if (res.changelog) setChangelog(res.changelog);
        if (res.changelog && !originalUrl) {
          const vid = sessionStorage.getItem("auteur_video_id");
          if (vid) videoApi.get(vid).then(v => { if (v?.cloudinary_url) setOriginalUrl(v.cloudinary_url); }).catch(() => {});
        }
        if (res.status === "completed" || res.status === "rendered" || res.status === "failed") return;
        delay = 2000;
      } catch { delay = Math.min(delay * 1.5 + Math.random() * 1000, MAX_DELAY); }
      if (!cancelled) timer = setTimeout(poll, delay);
    };
    timer = setTimeout(poll, delay);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [jobId]);

  const currentStepIdx = STEP_KEYS.indexOf(status);

  const handleRetry = async () => {
    if (!jobId || retrying) return;
    setRetrying(true);
    try {
      const res = await jobs.retry(jobId);
      if (res.job_id) { sessionStorage.setItem("auteur_job_id", res.job_id); setJobId(res.job_id); }
      setStatus("queued"); setProgress(0); setMessage("Retrying..."); setError(""); setRetrying(false);
    } catch (e: any) { setError(e.message || "Retry failed"); setRetrying(false); }
  };

  const handleApprove = () => {
    if (!outputUrl) return;
    const a = document.createElement("a");
    a.href = outputUrl; a.download = "auteur-edit.mp4"; a.click();
  };

  const handleTweak = () => {
    if (jobId) sessionStorage.setItem("auteur_current_job_id", jobId);
    navigate({ to: "/editor" });
  };

  const handleManual = () => {
    if (jobId) sessionStorage.setItem("auteur_current_job_id", jobId);
    navigate({ to: "/editor" });
  };

  return (
    <div style={{ background: "#09090B", color: "#FAFAFA", minHeight: "100vh", fontFamily: "'Space Grotesk',sans-serif" }}>
      <nav style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"0 24px", height:56, borderBottom:"2px solid #3F3F46" }}>
        <Link to="/" style={{ display:"flex", alignItems:"center", gap:8, color:"#A1A1AA", fontSize:11, fontWeight:700, letterSpacing:"0.12em", textTransform:"uppercase", textDecoration:"none" }}>
          <ArrowLeft size={14} /> AUTEUR
        </Link>
        <span style={{ fontSize:10, color:"#6B7280", fontWeight:600, letterSpacing:"0.15em", textTransform:"uppercase" }}>
          {status === "completed" ? "EDIT READY" : "PROCESSING"}
        </span>
        <div style={{ width:60 }} />
      </nav>

      <div style={{ padding:"40px 24px 80px" }}>
        {status === "failed" ? (
          <div style={{ border:"2px solid #ef4444", padding:32, textAlign:"center" }}>
            <AlertCircle size={32} style={{ color:"#ef4444", margin:"0 auto 12px" }} />
            <p style={{ fontWeight:700, fontSize:16, textTransform:"uppercase", letterSpacing:"-0.02em" }}>Something went wrong</p>
            <p style={{ fontSize:12, color:"#A1A1AA", marginTop:4 }}>{error || "Unknown error"}</p>
            <div style={{ display:"flex", gap:12, justifyContent:"center", marginTop:20 }}>
              <button onClick={() => navigate({ to: "/editor" })}
                style={{ padding:"10px 24px", background:"transparent", border:"2px solid #3F3F46", color:"#FAFAFA", fontWeight:700, fontSize:10, letterSpacing:"0.12em", textTransform:"uppercase", cursor:"pointer" }}>
                TRY AGAIN
              </button>
              <button onClick={handleRetry} disabled={retrying}
                style={{ padding:"10px 24px", background:"#DFE104", color:"#000", border:"none", fontWeight:700, fontSize:10, letterSpacing:"0.12em", textTransform:"uppercase", cursor:retrying?"not-allowed":"pointer" }}>
                {retrying ? "RETRYING..." : "RETRY JOB"}
              </button>
            </div>
          </div>
        ) : status === "completed" && outputUrl ? (
          <>
            <div style={{ border:"2px solid #3F3F46" }}>
              {showOriginal && originalUrl ? (
                <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:1, background:"#3F3F46" }}>
                  <div style={{ position:"relative" }}>
                    <span style={{ position:"absolute", top:4, left:4, zIndex:10, fontSize:9, fontWeight:700, letterSpacing:"0.10em", textTransform:"uppercase", background:"rgba(0,0,0,0.7)", color:"#A1A1AA", padding:"2px 8px" }}>ORIGINAL</span>
                    <video src={originalUrl} controls style={{ width:"100%", display:"block" }} />
                  </div>
                  <div style={{ position:"relative" }}>
                    <span style={{ position:"absolute", top:4, left:4, zIndex:10, fontSize:9, fontWeight:700, letterSpacing:"0.10em", textTransform:"uppercase", background:"rgba(0,0,0,0.7)", color:"#DFE104", padding:"2px 8px" }}>EDITED</span>
                    <video src={outputUrl} controls style={{ width:"100%", display:"block" }} />
                  </div>
                </div>
              ) : (
                <video src={outputUrl} controls style={{ width:"100%", display:"block" }} />
              )}
              {originalUrl && (
                <button onClick={() => setShowOriginal(p => !p)}
                  style={{ width:"100%", padding:"10px 0", background:"transparent", border:"none", borderTop:"2px solid #3F3F46", color:"#6B7280", fontWeight:700, fontSize:10, letterSpacing:"0.12em", textTransform:"uppercase", cursor:"pointer" }}>
                  {showOriginal ? "HIDE ORIGINAL" : "SHOW ORIGINAL"}
                </button>
              )}
            </div>

            {changelog && (
              <div style={{ marginTop:32 }}>
                <TimelineSummary changelog={changelog} />

                {changelog.ref_breakdown?.length > 0 && (
                  <div style={{ marginTop:24, border:"2px solid #3F3F46", padding:20 }}>
                    <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:16 }}>
                      <Brain size={14} style={{ color:"#DFE104" }} />
                      <span style={{ fontSize:10, fontWeight:700, letterSpacing:"0.15em", textTransform:"uppercase", color:"#A1A1AA" }}>REFERENCE CONTRIBUTIONS</span>
                    </div>
                    <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
                      {changelog.ref_breakdown.map((ref, i) => (
                        <div key={i} style={{ border:"1px solid #3F3F46", padding:12 }}>
                          <div style={{ display:"flex", justifyContent:"space-between", marginBottom:8 }}>
                            <span style={{ fontSize:11, fontWeight:600, color:"#A1A1AA" }}>REF #{ref.ref_index + 1}{ref.filename ? ` — ${ref.filename}` : ""}</span>
                            <span style={{ fontSize:10, color:"#DFE104", fontWeight:700 }}>ENERGY: {ref.contributed.energy_level}/10</span>
                          </div>
                          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:8, fontSize:11 }}>
                            <Contribution label="VIBE" value={ref.contributed.music_vibe} />
                            <Contribution label="COLOR" value={ref.contributed.color_grade} />
                            <Contribution label="CAPTIONS" value={ref.contributed.caption_style} />
                            <Contribution label="HOOK" value={ref.contributed.hook_pattern} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div style={{ marginTop:16, border:"2px solid #3F3F46", padding:"12px 16px", display:"flex", alignItems:"center", gap:12 }}>
                  <Target size={14} style={{ color:"#22c55e" }} />
                  <span style={{ fontSize:10, fontWeight:700, letterSpacing:"0.12em", textTransform:"uppercase", color:"#A1A1AA" }}>STYLE MATCH</span>
                  <div style={{ flex:1, height:6, background:"#27272A" }}>
                    <div style={{ height:"100%", background:"#22c55e", transition:"width 700ms", width:`${changelog.style_match_score || 85}%` }} />
                  </div>
                  <span style={{ fontSize:12, fontWeight:700, color:"#22c55e" }}>{changelog.style_match_score || 85}%</span>
                </div>
              </div>
            )}

            <div style={{ marginTop:24, display:"flex", flexDirection:"column", gap:12 }}>
              <button onClick={handleApprove}
                style={{ width:"100%", padding:"14px 0", background:"#DFE104", color:"#000", border:"none", fontWeight:700, fontSize:12, letterSpacing:"0.12em", textTransform:"uppercase", cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center", gap:8 }}>
                <ThumbsUp size={14} /> APPROVE & DOWNLOAD
              </button>
              <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
                <button onClick={handleTweak}
                  style={{ padding:"12px 0", background:"transparent", color:"#FAFAFA", border:"2px solid #3F3F46", fontWeight:700, fontSize:10, letterSpacing:"0.12em", textTransform:"uppercase", cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center", gap:6 }}>
                  <Edit3 size={12} /> TWEAK WITH PROMPT
                </button>
                <button onClick={handleManual}
                  style={{ padding:"12px 0", background:"transparent", color:"#6B7280", border:"2px solid #3F3F46", fontWeight:700, fontSize:10, letterSpacing:"0.12em", textTransform:"uppercase", cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center", gap:6 }}>
                  <Wand2 size={12} /> MANUAL EDIT
                </button>
              </div>
            </div>
          </>
        ) : (
          <div style={{ maxWidth: 520, margin: "0 auto" }}>

            {/* ── Big title ── */}
            <div style={{ textAlign: "center", marginBottom: 40 }}>
              <p style={{ fontSize: "clamp(2rem,6vw,3.5rem)", fontWeight: 800, textTransform: "uppercase", letterSpacing: "-0.03em", color: "#FAFAFA", lineHeight: 1 }}>
                AUTEUR
              </p>
              <p style={{ fontSize: 11, color: "#DFE104", letterSpacing: "0.25em", fontWeight: 700, textTransform: "uppercase", marginTop: 6 }}>
                PROCESSING
              </p>
              <p style={{ fontSize: 12, color: "#A1A1AA", marginTop: 8, fontWeight: 500 }}>
                Cutting and rendering your reel...
              </p>
            </div>

            {/* ── Timer + ETA ── */}
            <ElapsedTimer status={status} currentStepIdx={currentStepIdx} />

            {/* ── Step pipeline ── */}
            <div style={{ margin: "32px 0" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 0 }}>
                {STEP_LABELS.map((label, i) => {
                  const isCompleted = i < currentStepIdx;
                  const isActive = i === currentStepIdx;
                  const isLast = i === STEP_LABELS.length - 1;
                  return (
                    <div key={label} style={{ display: "flex", alignItems: "center" }}>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                        {/* dot */}
                        <div style={{
                          width: 28, height: 28,
                          borderRadius: "50%",
                          display: "flex", alignItems: "center", justifyContent: "center",
                          background: isCompleted ? "#DFE104" : isActive ? "transparent" : "#18181B",
                          border: isCompleted ? "2px solid #DFE104" : isActive ? "2px solid #DFE104" : "2px solid #3F3F46",
                          boxShadow: isActive ? "0 0 16px rgba(223,225,4,0.5)" : "none",
                          position: "relative",
                          transition: "all 0.4s",
                        }}>
                          {isCompleted
                            ? <CheckCircle2 size={13} color="#000" />
                            : isActive
                              ? <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#DFE104", animation: "pulse 1.5s ease-in-out infinite" }} />
                              : <span style={{ fontSize: 8, fontWeight: 700, color: "#3F3F46" }}>{i + 1}</span>
                          }
                        </div>
                        {/* label */}
                        <span style={{
                          fontSize: 7, fontWeight: 700, letterSpacing: "0.08em",
                          textTransform: "uppercase",
                          color: isCompleted ? "#DFE104" : isActive ? "#FAFAFA" : "#3F3F46",
                          whiteSpace: "nowrap",
                        }}>
                          {label}
                        </span>
                      </div>
                      {/* connector line */}
                      {!isLast && (
                        <div style={{
                          width: 28, height: 2, marginBottom: 14,
                          background: i < currentStepIdx ? "#DFE104" : "#27272A",
                          transition: "background 0.5s",
                        }} />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* ── Progress bar ── */}
            <div style={{ margin: "0 auto 8px", height: 3, background: "#27272A", borderRadius: 2 }}>
              <div style={{
                height: "100%", background: "linear-gradient(90deg, #DFE104, #b8bc00)",
                transition: "width 800ms ease", width: `${progress}%`,
                borderRadius: 2, boxShadow: "0 0 8px rgba(223,225,4,0.4)",
              }} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 28 }}>
              <span style={{ fontSize: 9, color: "#6B7280", fontFamily: "'Space Grotesk',sans-serif", letterSpacing: "0.1em" }}>PROGRESS</span>
              <span style={{ fontSize: 9, color: "#DFE104", fontWeight: 700, fontFamily: "'Space Grotesk',sans-serif" }}>{Math.round(progress)}%</span>
            </div>

            {/* ── Message ── */}
            <div style={{
              padding: "12px 16px",
              background: "rgba(255,255,255,0.02)",
              border: "1px solid rgba(255,255,255,0.06)",
              borderRadius: 10,
              marginBottom: 16,
              display: "flex", alignItems: "center", gap: 10,
            }}>
              <Loader2 size={13} color="#DFE104" style={{ animation: "spin 1s linear infinite", flexShrink: 0 }} />
              <span style={{ fontSize: 11, color: "#A1A1AA", fontFamily: "'Space Grotesk',sans-serif" }}>{message || "Waiting in queue..."}</span>
            </div>

            {/* ── Notification banner ── */}
            <div style={{
              padding: "14px 16px",
              background: "rgba(223,225,4,0.04)",
              border: "1px solid rgba(223,225,4,0.12)",
              borderRadius: 10,
              display: "flex", alignItems: "flex-start", gap: 10,
            }}>
              <Clock size={14} color="#DFE104" style={{ flexShrink: 0, marginTop: 1 }} />
              <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: "#DFE104", fontFamily: "'Space Grotesk',sans-serif", letterSpacing: "0.05em" }}>
                  You can close this tab
                </p>
                <p style={{ fontSize: 10, color: "rgba(255,255,255,0.35)", fontFamily: "'Space Grotesk',sans-serif", marginTop: 3, lineHeight: 1.5 }}>
                  We'll have your reel ready when you come back. AI processing runs in the background — check back in a few minutes.
                </p>
              </div>
            </div>

            {error && (
              <p style={{ marginTop: 12, fontSize: 10, color: "#ef4444", textAlign: "center" }}>{error}</p>
            )}

            <style>{`
              @keyframes pulse {
                0%, 100% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.5; transform: scale(0.7); }
              }
            `}</style>
          </div>
        )}
      </div>
    </div>
  );
}

function ElapsedTimer({ status, currentStepIdx }: { status: string; currentStepIdx: number }) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    setSeconds(0);
  }, [currentStepIdx]);

  useEffect(() => {
    if (currentStepIdx >= 5) return;
    const interval = setInterval(() => setSeconds(s => s + 1), 1000);
    return () => clearInterval(interval);
  }, [currentStepIdx]);

  const format = (s: number) => {
    if (s <= 0) return "~done";
    return `~${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;
  };

  // Per-step estimated remaining seconds from step start
  const STEP_ETA = [5, 20, 30, 20, 60, 0]; // queued, transcribe, analyze, plan, render, done
  const stepTotal = STEP_ETA[currentStepIdx] ?? 30;
  const remaining = Math.max(0, stepTotal - seconds);

  const [totalElapsed, setTotalElapsed] = useState(0);
  useEffect(() => {
    const interval = setInterval(() => setTotalElapsed(s => s + 1), 1000);
    return () => clearInterval(interval);
  }, []);
  const fmtElapsed = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

  return (
    <div style={{
      display: "flex", justifyContent: "center", gap: 32,
      padding: "16px 24px",
      background: "rgba(255,255,255,0.02)",
      border: "1px solid rgba(255,255,255,0.05)",
      borderRadius: 12,
    }}>
      <div style={{ textAlign: "center" }}>
        <p style={{ fontSize: 9, color: "#6B7280", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 4 }}>Elapsed</p>
        <p style={{ fontSize: 22, color: "#FAFAFA", fontWeight: 800, fontFamily: "'Space Grotesk',sans-serif", letterSpacing: "-0.02em" }}>
          {fmtElapsed(totalElapsed)}
        </p>
      </div>
      <div style={{ width: 1, background: "rgba(255,255,255,0.07)", alignSelf: "stretch" }} />
      <div style={{ textAlign: "center" }}>
        <p style={{ fontSize: 9, color: "#6B7280", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 4 }}>This step ETA</p>
        <p style={{ fontSize: 22, color: remaining < 10 ? "#22c55e" : "#DFE104", fontWeight: 800, fontFamily: "'Space Grotesk',sans-serif", letterSpacing: "-0.02em" }}>
          {format(remaining)}
        </p>
      </div>
      <div style={{ width: 1, background: "rgba(255,255,255,0.07)", alignSelf: "stretch" }} />
      <div style={{ textAlign: "center" }}>
        <p style={{ fontSize: 9, color: "#6B7280", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 4 }}>Total ETA</p>
        <p style={{ fontSize: 22, color: "#A1A1AA", fontWeight: 800, fontFamily: "'Space Grotesk',sans-serif", letterSpacing: "-0.02em" }}>~2 min</p>
      </div>
    </div>
  );
}

function Contribution({ label, value }: { label: string; value: string }) {
  if (!value || value === "—" || value === "none") return null;
  return (
    <div style={{ display:"flex", gap:6 }}>
      <span style={{ color:"#6B7280", fontWeight:600, fontSize:10, letterSpacing:"0.05em" }}>{label}:</span>
      <span style={{ color:"#A1A1AA" }}>{value}</span>
    </div>
  );
}
