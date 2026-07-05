import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useRef, useState, useCallback } from "react";
import { ArrowUpRight, Upload, Link2, ArrowRight, X, Wand2, Edit3, Sparkles } from "lucide-react";
import { edit as editApi, auth } from "@/lib/api";
import { toast } from "@/components/editor/Toast";

/* ── Glass Card wrapper ── */
function Glass({ children, style, className, ...rest }: { children: React.ReactNode; style?: React.CSSProperties; className?: string; [key: string]: any }) {
  return (
    <div className={className} {...rest} style={{
      background: "rgba(24,24,27,0.6)",
      backdropFilter: "blur(20px)",
      WebkitBackdropFilter: "blur(20px)",
      border: "1px solid rgba(255,255,255,0.06)",
      borderRadius: 16,
      boxShadow: "0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)",
      ...style,
    }}>{children}</div>
  );
}

/* ── Animated background orbs ── */
function Orbs() {
  return (
    <div style={{ position:"fixed", inset:0, overflow:"hidden", pointerEvents:"none", zIndex:0 }}>
      <div style={{
        position:"absolute", width:"50vmax", height:"50vmax", borderRadius:"50%",
        background:"radial-gradient(circle, rgba(223,225,4,0.12) 0%, transparent 70%)",
        top:"-10%", left:"-10%", animation:"orbFloat 20s ease-in-out infinite",
      }} />
      <div style={{
        position:"absolute", width:"40vmax", height:"40vmax", borderRadius:"50%",
        background:"radial-gradient(circle, rgba(108,99,255,0.08) 0%, transparent 70%)",
        bottom:"-5%", right:"-5%", animation:"orbFloat 25s ease-in-out infinite reverse",
      }} />
      <div style={{
        position:"absolute", width:"30vmax", height:"30vmax", borderRadius:"50%",
        background:"radial-gradient(circle, rgba(223,225,4,0.06) 0%, transparent 70%)",
        top:"40%", left:"60%", animation:"orbFloat 18s ease-in-out infinite 5s",
      }} />
    </div>
  );
}

/* ── CSS Marquee ── */
function Marquee({ children, speed = 40 }: { children: React.ReactNode; speed?: number }) {
  return (
    <div style={{ overflow:"hidden", whiteSpace:"nowrap", display:"flex" }}>
      <div className="marquee-track" style={{
        display:"flex", animation:`marquee ${speed}s linear infinite`,
        willChange:"transform",
      }}>
        {children}
      </div>
      <div className="marquee-track" style={{
        display:"flex", animation:`marquee ${speed}s linear infinite`,
        willChange:"transform",
      }}>
        {children}
      </div>
    </div>
  );
}
import { uploadVideo, video as videoApi } from "@/lib/api";

export const Route = createFileRoute("/")({ component: Home });

/* ── Noise texture overlay ── */
function Noise() {
  return (
    <svg style={{ position: "fixed", inset: 0, width: "100%", height: "100%", zIndex: 9999, pointerEvents: "none", mixBlendMode: "overlay", opacity: 0.03 }}>
      <title>Noise Texture</title>
      <filter id="noise">
        <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="4" stitchTiles="stitch" />
        <feColorMatrix type="saturate" values="0" />
      </filter>
      <rect width="100%" height="100%" filter="url(#noise)" />
    </svg>
  );
}

/* ── Auth Modal ── */
function AuthModal({ open, onClose, onLogin }: { open: boolean; onClose: () => void; onLogin: () => void }) {
  const [tab, setTab] = useState<"login"|"register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = tab === "login"
        ? await auth.login(email, password)
        : await auth.register(email, password, name || email.split("@")[0]);
      localStorage.setItem("auteur_token", res.access_token);
      setLoading(false);
      onLogin();
      onClose();
    } catch (err: any) {
      setError(err.message);
      setLoading(false);
    }
  };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, zIndex: 200,
      display: "flex", alignItems: "center", justifyContent: "center",
      background: "rgba(0,0,0,0.85)", backdropFilter: "blur(10px)", padding: 16,
    }}>
      <div onClick={e => e.stopPropagation()} style={{ background: "#09090B", border: "2px solid #3F3F46", width: "100%", maxWidth: 400 }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"18px 24px", borderBottom:"2px solid #3F3F46" }}>
          <span style={{ fontSize:11, fontWeight:700, letterSpacing:"0.18em", textTransform:"uppercase", color:"#FAFAFA" }}>{tab === "login" ? "SIGN IN" : "SIGN UP"}</span>
          <button onClick={onClose} style={{ background:"none", border:"none", color:"#FAFAFA", cursor:"pointer", fontSize:13 }}>✕</button>
        </div>
        <div style={{ display:"flex", borderBottom:"2px solid #3F3F46" }}>
          {(["login","register"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              style={{
                flex: 1, padding:"12px 0", background: "transparent", border: "none",
                borderBottom: tab===t ? "2px solid #DFE104" : "2px solid transparent",
                color: tab===t ? "#DFE104" : "#FAFAFA",
                fontFamily:"'Space Grotesk',sans-serif", fontWeight:700, fontSize:11, letterSpacing:"0.15em", textTransform:"uppercase", cursor:"pointer",
              }}
            >{t === "login" ? "LOGIN" : "REGISTER"}</button>
          ))}
        </div>
        <form onSubmit={handleSubmit} style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
          {tab === "register" && (
            <div>
              <label style={{ fontSize:10, color:"#FAFAFA", letterSpacing:"0.12em", textTransform:"uppercase", display:"block", marginBottom:6, fontWeight:600 }}>NAME</label>
              <input value={name} onChange={e => setName(e.target.value)} placeholder="Your name" required
                style={{ width:"100%", padding:"12px", background:"transparent", borderBottom:"2px solid #3F3F46", color:"#FAFAFA", fontFamily:"'Space Grotesk',sans-serif", fontSize:13, outline:"none", fontWeight:500 }} />
            </div>
          )}
          <div>
            <label style={{ fontSize:10, color:"#FAFAFA", letterSpacing:"0.12em", textTransform:"uppercase", display:"block", marginBottom:6, fontWeight:600 }}>EMAIL</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required
              style={{ width:"100%", padding:"12px", background:"transparent", borderBottom:"2px solid #3F3F46", color:"#FAFAFA", fontFamily:"'Space Grotesk',sans-serif", fontSize:13, outline:"none", fontWeight:500 }} />
          </div>
          <div>
            <label style={{ fontSize:10, color:"#FAFAFA", letterSpacing:"0.12em", textTransform:"uppercase", display:"block", marginBottom:6, fontWeight:600 }}>PASSWORD</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" required minLength={6}
              style={{ width:"100%", padding:"12px", background:"transparent", borderBottom:"2px solid #3F3F46", color:"#FAFAFA", fontFamily:"'Space Grotesk',sans-serif", fontSize:13, outline:"none", fontWeight:500 }} />
          </div>
          {error && <p style={{ fontSize:11, color:"#ef4444", fontWeight:500 }}>{error}</p>}
          <button type="submit" disabled={loading}
            style={{ padding:"14px 0", background: loading ? "#3F3F46" : "#DFE104", color: loading ? "#FAFAFA" : "#000", border:"none", fontWeight:700, fontSize:12, letterSpacing:"0.12em", textTransform:"uppercase", cursor: loading ? "not-allowed" : "pointer" }}
          >{loading ? "..." : tab === "login" ? "SIGN IN" : "CREATE ACCOUNT"}</button>
        </form>
      </div>
    </div>
  );
}

/* ── Upload Modal ── */
function UploadModal({ open, onClose, onFile, onYt, onEditor }: any) {
  const ref = useRef<HTMLInputElement>(null);
  const [link, setLink] = useState("");
  const [tab, setTab] = useState<"file"|"yt">("file");
  const [drag, setDrag] = useState(false);
  if (!open) return null;
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 200,
        display: "flex", alignItems: "center", justifyContent: "center",
        background: "rgba(0,0,0,0.85)", backdropFilter: "blur(10px)", padding: 16,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{ background: "#09090B", border: "2px solid #3F3F46", width: "100%", maxWidth: 440 }}
      >
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"18px 32px", borderBottom:"2px solid #3F3F46" }}>
          <span style={{ fontSize:11, fontWeight:700, letterSpacing:"0.18em", textTransform:"uppercase", color:"#FAFAFA" }}>START EDITING</span>
          <button onClick={onClose} style={{ background:"none", border:"none", color:"#FAFAFA", cursor:"pointer", fontSize:13 }}>✕</button>
        </div>
        <div style={{ display:"flex", borderBottom:"2px solid #3F3F46" }}>
          {(["file","yt"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              style={{
                flex: 1, padding:"12px 0",
                background: "transparent", border: "none", borderBottom: tab===t ? "2px solid #DFE104" : "2px solid transparent",
                color: tab===t ? "#DFE104" : "#FAFAFA",
                fontFamily:"'Space Grotesk',sans-serif", fontWeight:700, fontSize:11, letterSpacing:"0.15em", textTransform:"uppercase", cursor:"pointer",
              }}
            >{t==="file" ? "UPLOAD FILE" : "YOUTUBE IMPORT"}</button>
          ))}
        </div>
        <div style={{ padding:32 }}>
          {tab==="file" && (
            <div
              onDragOver={e=>{e.preventDefault();setDrag(true)}}
              onDragLeave={()=>setDrag(false)}
              onDrop={e=>{e.preventDefault();setDrag(false);onFile(e.dataTransfer.files)}}
              onClick={()=>ref.current?.click()}
              style={{
                display:"flex", flexDirection:"column", alignItems:"center", gap:16, padding:"40px 0", cursor:"pointer",
                border:`2px dashed ${drag?"#DFE104":"#3F3F46"}`,
                background: drag ? "rgba(223,225,4,0.04)" : "transparent",
                transition: "background 200ms",
              }}
            >
              <input ref={ref} type="file" accept="video/*" style={{display:"none"}} onChange={e=>onFile(e.target.files)} />
              <Upload size={32} color={drag?"#DFE104":"#FAFAFA"} />
              <div style={{ textAlign:"center" }}>
                <p style={{ fontWeight:700, textTransform:"uppercase", letterSpacing:"-0.01em", fontSize:16, color:"#FAFAFA" }}>{drag?"DROP IT ↓":"DRAG & DROP"}</p>
                <p style={{ fontSize:10, color:"#FAFAFA", letterSpacing:"0.12em", textTransform:"uppercase", marginTop:6, opacity:0.5 }}>MP4 · MOV · AVI · UP TO 2GB</p>
              </div>
              <button
                onClick={e=>{e.stopPropagation();ref.current?.click()}}
                style={{ display:"inline-flex", alignItems:"center", gap:6, background:"#DFE104", color:"#000", border:"none", fontWeight:700, fontSize:11, letterSpacing:"0.12em", textTransform:"uppercase", padding:"0 24px", height:44, cursor:"pointer", transition:"transform 120ms" }}
                onMouseEnter={e=>(e.currentTarget as HTMLElement).style.transform="scale(1.05)"}
                onMouseLeave={e=>(e.currentTarget as HTMLElement).style.transform="scale(1)"}
              >BROWSE FILES</button>
            </div>
          )}
          {tab==="yt" && (
            <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
              <p style={{ fontSize:10, color:"#FAFAFA", letterSpacing:"0.15em", textTransform:"uppercase", fontWeight:600, opacity:0.7 }}>PASTE YOUTUBE URL</p>
              <div style={{ display:"flex" }}>
                <div style={{ display:"flex", flex:1, alignItems:"center", gap:8, padding:"0 12px", background:"transparent", border:"2px solid #3F3F46", borderRight:"none", height:52 }}>
                  <Link2 size={14} color="#FAFAFA" />
                  <input value={link} onChange={e=>setLink(e.target.value)} onKeyDown={e=>{if(e.key==="Enter"&&link)onYt(link)}}
                    placeholder="https://youtube.com/watch?v=..."
                    style={{ flex:1, background:"transparent", border:"none", outline:"none", color:"#FAFAFA", fontFamily:"'Space Grotesk',sans-serif", fontSize:13, fontWeight:500 }}
                  />
                </div>
                <button disabled={!link} onClick={()=>onYt(link)}
                  style={{ display:"flex", alignItems:"center", justifyContent:"center", width:52, height:52, background:link?"#DFE104":"#27272A", border:"2px solid #3F3F46", cursor:link?"pointer":"not-allowed" }}
                >
                  <ArrowRight size={18} color={link?"#000":"#FAFAFA"} />
                </button>
              </div>
            </div>
          )}
        </div>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"12px 32px", borderTop:"2px solid #3F3F46" }}>
          <span style={{ fontSize:10, color:"#27272A", letterSpacing:"0.12em", textTransform:"uppercase", fontWeight:600 }}>OR</span>
          <button onClick={onEditor} style={{ display:"inline-flex", alignItems:"center", gap:6, background:"transparent", color:"#FAFAFA", border:"2px solid #3F3F46", fontWeight:700, fontSize:10, letterSpacing:"0.12em", textTransform:"uppercase", padding:"0 16px", height:36, cursor:"pointer", transition:"background 150ms,color 150ms" }}
            onMouseEnter={e=>{ (e.currentTarget as HTMLElement).style.background="#FAFAFA"; (e.currentTarget as HTMLElement).style.color="#000"; }}
            onMouseLeave={e=>{ (e.currentTarget as HTMLElement).style.background="transparent"; (e.currentTarget as HTMLElement).style.color="#FAFAFA"; }}
          >OPEN EDITOR →</button>
        </div>
      </div>
    </div>
  );
}

/* ── Capability Row (group hover card) ── */
function CapRow({ num, title, desc }: { num:string; title:string; desc:string }) {
  const [hov, setHov] = useState(false);
  return (
    <Glass style={{
      display:"flex", alignItems:"center", gap:24, padding:"32px 32px",
      marginBottom:12, borderRadius:16, cursor:"pointer",
      border: hov ? "1px solid rgba(223,225,4,0.2)" : "1px solid rgba(255,255,255,0.06)",
      transition:"all 300ms",
      transform: hov ? "translateX(8px)" : "translateX(0)",
      boxShadow: hov ? "0 0 40px rgba(223,225,4,0.08)" : "0 8px 32px rgba(0,0,0,0.4)",
    }}
      onMouseEnter={()=>setHov(true)}
      onMouseLeave={()=>setHov(false)}
    >
      <span style={{
        fontSize:"clamp(2rem,4vw,3rem)",
        fontWeight:700, letterSpacing:"-0.04em", lineHeight:0.85,
        color: hov ? "#DFE104" : "#27272A",
        transition:"color 300ms", minWidth:"4rem", flexShrink:0, fontFamily:"'Space Grotesk',sans-serif",
      }} aria-hidden="true">{num}</span>
      <div style={{ display:"flex", flexDirection:"column", gap:6, flex:1 }}>
        <h3 style={{
          fontSize:"clamp(1.25rem,2.5vw,2rem)", fontWeight:700, letterSpacing:"-0.02em",
          textTransform:"uppercase", lineHeight:1, fontFamily:"'Space Grotesk',sans-serif",
          color: hov ? "#DFE104" : "#FAFAFA", transition:"color 300ms",
        }}>{title}</h3>
        <p style={{ fontSize:"clamp(0.8rem,1.2vw,1rem)", lineHeight:1.6, color:"#A1A1AA", maxWidth:440 }}>{desc}</p>
      </div>
      <ArrowUpRight size={20} color={hov?"#DFE104":"rgba(255,255,255,0.2)"} style={{ flexShrink:0, transition:"all 300ms", transform: hov?"rotate(12deg) scale(1.1)":"rotate(0deg) scale(1)" }} />
    </Glass>
  );
}

const CAPS = [
  { num:"01", title:"SMART CUT",    desc:"AI removes silences, filler words, and dead air automatically." },
  { num:"02", title:"AUTO CAPTION", desc:"98% accurate captions generated and synced in under 2 seconds." },
  { num:"03", title:"COLOR GRADE",  desc:"Describe a vibe. Auteur applies cinematic color to every frame." },
  { num:"04", title:"AI ZOOM",      desc:"Dynamic punch-ins at punchlines, auto-timed to the frame." },
  { num:"05", title:"STYLE TRAIN",  desc:"Feed your past videos. Auteur learns and replicates your style." },
];

/* ── Stats block ── */
const STATS = [
  { v:"2M+",  l:"CREATORS" },
  { v:"50M+", l:"VIDEOS EDITED" },
  { v:"4.9★", l:"RATING" },
  { v:"98%",  l:"ACCURACY" },
  { v:"<2S",  l:"AI SPEED" },
];

/* ── Home ── */
function Home() {
  const navigate = useNavigate();
  const [modal, setModal] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [upMsg, setUpMsg] = useState("");
  const [upPct, setUpPct] = useState(0);
  const [done, setDone] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const [loggedIn, setLoggedIn] = useState(() => {
    if (typeof window !== 'undefined') return !!localStorage.getItem("auteur_token");
    return false;
  });

  const [generating, setGenerating] = useState(false);
  const [trimFile, setTrimFile] = useState<File | null>(null);
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(0);
  const [trimDuration, setTrimDuration] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Multi-step launch modal
  const [launchModal, setLaunchModal] = useState(false);
  const [launchStep, setLaunchStep] = useState<"mode" | "ref">("mode");
  const [launchMode, setLaunchMode] = useState<"viral" | "vlog">("viral");
  const [launchRefs, setLaunchRefs] = useState<string[]>([]);
  const [refInput, setRefInput] = useState("");

  const openLaunchModal = useCallback(() => {
    setLaunchStep("mode");
    setLaunchMode("viral");
    setLaunchRefs([]);
    setRefInput("");
    setLaunchModal(true);
  }, []);

  const handleLaunchEdit = useCallback(async () => {
    const vid = sessionStorage.getItem("auteur_video_id");
    if (!vid) return;
    setLaunchModal(false);
    setGenerating(true);
    setUpMsg("Importing refs...");
    try {
      // Import all YouTube URLs first to get valid video IDs
      const refIds: string[] = [];
      for (const url of launchRefs) {
        if (!url.trim()) continue;
        try {
          setUpMsg(`Importing ref: ${url.slice(0, 40)}...`);
          const r = await videoApi.importYoutube(url);
          refIds.push(r.video_id);
        } catch {
          // Pass raw URL as fallback — backend may handle it or skip
          refIds.push(url.trim());
        }
      }
      const prompt = launchMode === "vlog"
        ? "Make an engaging vlog-style edit with natural pacing and story flow"
        : "Make a viral short-form reel with punchy cuts and high energy";
      const res = await editApi.create({
        video_id: vid,
        prompt,
        version_type: launchMode,
        ref_video_ids: refIds,
      });
      sessionStorage.setItem("auteur_job_id", res.job_id);
      setGenerating(false);
      navigate({ to: "/results" });
    } catch (e: any) {
      setGenerating(false);
      toast(e.message, "error");
    }
  }, [navigate, launchMode, launchRefs]);

  const handleOpenEditor = useCallback(() => {
    navigate({ to: "/editor" });
  }, [navigate]);

  const handleFiles = useCallback((files: FileList | null) => {
    if (!files?.length) return;
    const f = files[0];
    if (!f.type.startsWith("video/")) { toast("Please upload a video file", "error"); return; }
    setModal(false);
    setTrimFile(f);
    setTrimStart(0);
    setTrimEnd(0);
    setTrimDuration(0);
  }, []);

  const handleTrimConfirm = useCallback(async () => {
    if (!trimFile) return;
    setTrimFile(null);
    setUploading(true);
    setUpMsg("Starting...");
    try {
      const r = await uploadVideo(
        trimFile,
        (s, p) => { setUpMsg(s); setUpPct(p); },
        trimStart > 0 ? trimStart : undefined,
        trimEnd > 0 && trimEnd > trimStart ? trimEnd : undefined,
      );
      setDone(true); setUpMsg("Done!");
      sessionStorage.setItem("auteur_video_id", r.video_id);
      sessionStorage.setItem("auteur_video_duration", String(r.duration));
      sessionStorage.setItem("auteur_video_filename", trimFile.name);
    } catch (e: any) { setUploading(false); toast(e.message, "error"); }
  }, [trimFile, trimStart, trimEnd]);

  const handleUploadFull = useCallback(async () => {
    if (!trimFile) return;
    setTrimFile(null);
    setUploading(true);
    setUpMsg("Starting...");
    try {
      const r = await uploadVideo(trimFile, (s, p) => { setUpMsg(s); setUpPct(p); });
      setDone(true); setUpMsg("Done!");
      sessionStorage.setItem("auteur_video_id", r.video_id);
      sessionStorage.setItem("auteur_video_duration", String(r.duration));
      sessionStorage.setItem("auteur_video_filename", trimFile.name);
    } catch (e: any) { setUploading(false); toast(e.message, "error"); }
  }, [trimFile]);

  const handleYt = useCallback(async (url: string) => {
    setModal(false); setUploading(true); setUpMsg("Importing...");
    try {
      const r = await videoApi.importYoutube(url);
      setDone(true); setUpMsg("Done!");
      sessionStorage.setItem("auteur_video_id", r.video_id);
      sessionStorage.setItem("auteur_video_duration", String(r.duration));
      sessionStorage.setItem("auteur_video_filename", "youtube.mp4");
    } catch (e: any) { setUploading(false); toast(e.message, "error"); }
  }, [navigate]);

  if (uploading || generating) return (
    <div style={{ background:"#09090B", color:"#FAFAFA", fontFamily:"'Space Grotesk',sans-serif", minHeight:"100vh", overflow:"hidden", display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:32 }}>
      <Noise />
      {done && !generating ? (
        <>
          <p style={{ fontSize:"clamp(2.5rem,8vw,7rem)", fontWeight:700, textTransform:"uppercase", letterSpacing:"-0.03em", color:"#DFE104" }}>
            DONE ✓
          </p>
          <p style={{ fontSize:14, color:"#A1A1AA", letterSpacing:"0.05em", fontWeight:500, textAlign:"center", maxWidth:400, lineHeight:1.6 }}>
            Your video is uploaded. Ready for the next step?
          </p>
          <div style={{ display:"flex", gap:16, marginTop:16, flexWrap:"wrap", justifyContent:"center" }}>
            <button onClick={openLaunchModal}
              style={{ display:"inline-flex", alignItems:"center", gap:10, background:"#DFE104", color:"#000", border:"none", fontWeight:800, fontSize:13, letterSpacing:"0.10em", textTransform:"uppercase", padding:"0 36px", height:56, cursor:"pointer", transition:"all 200ms", borderRadius:4, boxShadow:"0 0 30px rgba(223,225,4,0.4)" }}
              onMouseEnter={e=>{ (e.currentTarget as HTMLElement).style.transform="scale(1.05)"; (e.currentTarget as HTMLElement).style.boxShadow="0 0 50px rgba(223,225,4,0.6)"; }}
              onMouseLeave={e=>{ (e.currentTarget as HTMLElement).style.transform="scale(1)"; (e.currentTarget as HTMLElement).style.boxShadow="0 0 30px rgba(223,225,4,0.4)"; }}
            >
              <Wand2 size={18} /> GENERATE AI EDIT
            </button>
            <button onClick={handleOpenEditor}
              style={{ display:"inline-flex", alignItems:"center", gap:8, background:"transparent", color:"#FAFAFA", border:"1px solid rgba(255,255,255,0.15)", fontWeight:600, fontSize:11, letterSpacing:"0.10em", textTransform:"uppercase", padding:"0 24px", height:56, cursor:"pointer", transition:"all 150ms", borderRadius:4 }}
              onMouseEnter={e=>{ (e.currentTarget as HTMLElement).style.background="rgba(255,255,255,0.08)"; }}
              onMouseLeave={e=>{ (e.currentTarget as HTMLElement).style.background="transparent"; }}
            >
              <Edit3 size={14} /> MANUAL EDIT
            </button>
          </div>

          {/* ── Launch Modal ── */}
          {launchModal && (
            <div
              onClick={() => setLaunchModal(false)}
              style={{
                position:"fixed", inset:0, zIndex:300,
                display:"flex", alignItems:"center", justifyContent:"center",
                background:"rgba(0,0,0,0.88)", backdropFilter:"blur(16px)",
                padding:24,
              }}
            >
              <div
                onClick={e => e.stopPropagation()}
                style={{
                  width:"100%", maxWidth:480,
                  background:"rgba(12,12,14,0.95)",
                  border:"1px solid rgba(223,225,4,0.2)",
                  borderRadius:20,
                  boxShadow:"0 0 60px rgba(223,225,4,0.15), 0 40px 80px rgba(0,0,0,0.8)",
                  overflow:"hidden",
                }}
              >
                {/* Step indicator */}
                <div style={{ display:"flex", borderBottom:"1px solid rgba(255,255,255,0.06)" }}>
                  {(["mode", "ref"] as const).map((s, i) => (
                    <div key={s} style={{
                      flex:1, padding:"14px 0", textAlign:"center",
                      fontSize:9, fontWeight:700, letterSpacing:"0.15em", textTransform:"uppercase",
                      fontFamily:"'Space Grotesk',sans-serif",
                      color: launchStep === s ? "#DFE104" : "rgba(255,255,255,0.25)",
                      borderBottom: launchStep === s ? "2px solid #DFE104" : "2px solid transparent",
                      transition:"all 0.2s",
                    }}>
                      {i + 1}. {s === "mode" ? "Choose Format" : "Add Reference"}
                    </div>
                  ))}
                </div>

                <div style={{ padding:32 }}>
                  {launchStep === "mode" ? (
                    <>
                      <p style={{ fontSize:10, color:"rgba(255,255,255,0.4)", fontWeight:700, letterSpacing:"0.18em", textTransform:"uppercase", marginBottom:8, fontFamily:"'Space Grotesk',sans-serif" }}>Select Format</p>
                      <h2 style={{ fontSize:"clamp(1.4rem,3vw,2rem)", fontWeight:800, color:"#FAFAFA", letterSpacing:"-0.02em", textTransform:"uppercase", lineHeight:1.1, marginBottom:24, fontFamily:"'Space Grotesk',sans-serif" }}>
                        What style of<br/>edit do you want?
                      </h2>
                      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:28 }}>
                        {([
                          { mode:"viral" as const, emoji:"⚡", label:"REEL", sub:"Short-form, punchy cuts, viral hooks" },
                          { mode:"vlog" as const, emoji:"🎬", label:"VLOG", sub:"Natural pacing, storytelling flow" },
                        ]).map(({ mode, emoji, label, sub }) => (
                          <button key={mode} onClick={() => setLaunchMode(mode)}
                            style={{
                              padding:"20px 16px", textAlign:"center",
                              background: launchMode === mode ? "rgba(223,225,4,0.1)" : "rgba(255,255,255,0.03)",
                              border: launchMode === mode ? "2px solid #DFE104" : "2px solid rgba(255,255,255,0.07)",
                              borderRadius:12, cursor:"pointer", transition:"all 0.2s",
                              boxShadow: launchMode === mode ? "0 0 20px rgba(223,225,4,0.15)" : "none",
                            }}
                          >
                            <div style={{ fontSize:28, marginBottom:8 }}>{emoji}</div>
                            <p style={{ fontSize:13, fontWeight:800, color: launchMode === mode ? "#DFE104" : "#FAFAFA", letterSpacing:"0.08em", fontFamily:"'Space Grotesk',sans-serif" }}>{label}</p>
                            <p style={{ fontSize:10, color:"rgba(255,255,255,0.4)", marginTop:4, lineHeight:1.4, fontFamily:"'Space Grotesk',sans-serif" }}>{sub}</p>
                          </button>
                        ))}
                      </div>
                      <button onClick={() => setLaunchStep("ref")}
                        style={{ width:"100%", height:52, background:"#DFE104", border:"none", borderRadius:10, fontWeight:800, fontSize:12, letterSpacing:"0.12em", textTransform:"uppercase", cursor:"pointer", color:"#000", fontFamily:"'Space Grotesk',sans-serif", transition:"all 0.2s", boxShadow:"0 4px 20px rgba(223,225,4,0.3)" }}
                        onMouseEnter={e => (e.currentTarget as HTMLElement).style.transform = "scale(1.02)"}
                        onMouseLeave={e => (e.currentTarget as HTMLElement).style.transform = "scale(1)"}
                      >
                        NEXT →
                      </button>
                    </>
                    ) : (
                    <>
                      <p style={{ fontSize:10, color:"rgba(255,255,255,0.4)", fontWeight:700, letterSpacing:"0.18em", textTransform:"uppercase", marginBottom:8, fontFamily:"'Space Grotesk',sans-serif" }}>Reference Style</p>
                      <h2 style={{ fontSize:"clamp(1.2rem,3vw,1.7rem)", fontWeight:800, color:"#FAFAFA", letterSpacing:"-0.02em", textTransform:"uppercase", lineHeight:1.1, marginBottom:8, fontFamily:"'Space Grotesk',sans-serif" }}>
                        Add YouTube refs<br/>for AI to match style
                      </h2>
                      <p style={{ fontSize:11, color:"rgba(255,255,255,0.35)", marginBottom:16, fontFamily:"'Space Grotesk',sans-serif", lineHeight:1.5 }}>
                        Paste YouTube video links. AI will analyze pacing, cuts,
                        captions & color grade — then replicate the style on your video.
                      </p>

                      {/* Chips for added refs */}
                      {launchRefs.length > 0 && (
                        <div style={{ display:"flex", flexDirection:"column", gap:6, marginBottom:12 }}>
                          {launchRefs.map((url, i) => (
                            <div key={i} style={{ display:"flex", alignItems:"center", gap:8, padding:"6px 10px", background:"rgba(223,225,4,0.08)", border:"1px solid rgba(223,225,4,0.2)", borderRadius:8 }}>
                              <Link2 size={12} color="#DFE104" />
                              <span style={{ flex:1, fontSize:11, color:"rgba(255,255,255,0.8)", fontFamily:"'Space Grotesk',sans-serif", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{url}</span>
                              <button onClick={() => setLaunchRefs(prev => prev.filter((_, j) => j !== i))} style={{ background:"none", border:"none", color:"rgba(255,255,255,0.3)", cursor:"pointer", padding:0, display:"flex" }}><X size={12} /></button>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Input row */}
                      <div style={{ display:"flex", gap:8, marginBottom:16 }}>
                        <div style={{ flex:1, display:"flex", alignItems:"center", gap:8, padding:"0 12px", background:"rgba(255,255,255,0.04)", border:"1px solid rgba(255,255,255,0.1)", borderRadius:10, height:44 }}>
                          <Link2 size={14} color="rgba(255,255,255,0.3)" />
                          <input
                            value={refInput}
                            onChange={e => setRefInput(e.target.value)}
                            onKeyDown={e => {
                              if (e.key === "Enter" && refInput.trim()) {
                                setLaunchRefs(prev => [...prev, refInput.trim()]);
                                setRefInput("");
                              }
                            }}
                            placeholder="youtube.com/watch?v=..."
                            style={{ flex:1, background:"none", border:"none", outline:"none", color:"#FAFAFA", fontFamily:"'Space Grotesk',sans-serif", fontSize:12, fontWeight:500 }}
                          />
                        </div>
                        <button onClick={() => {
                          if (refInput.trim()) {
                            setLaunchRefs(prev => [...prev, refInput.trim()]);
                            setRefInput("");
                          }
                        }} style={{ width:44, height:44, background:"rgba(223,225,4,0.15)", border:"1px solid rgba(223,225,4,0.3)", borderRadius:10, cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0 }}>
                          <span style={{ color:"#DFE104", fontSize:18, fontWeight:700, lineHeight:1 }}>+</span>
                        </button>
                      </div>

                      <div style={{ display:"flex", gap:8 }}>
                        <button onClick={() => setLaunchStep("mode")}
                          style={{ flex:1, height:48, background:"transparent", border:"1px solid rgba(255,255,255,0.1)", borderRadius:10, fontWeight:600, fontSize:11, letterSpacing:"0.08em", textTransform:"uppercase", cursor:"pointer", color:"rgba(255,255,255,0.5)", fontFamily:"'Space Grotesk',sans-serif" }}
                        >
                          ← BACK
                        </button>
                        <button onClick={handleLaunchEdit}
                          style={{ flex:2, height:48, background:"#DFE104", border:"none", borderRadius:10, fontWeight:800, fontSize:12, letterSpacing:"0.12em", textTransform:"uppercase", cursor:"pointer", color:"#000", fontFamily:"'Space Grotesk',sans-serif", boxShadow:"0 4px 20px rgba(223,225,4,0.3)" }}
                          onMouseEnter={e => (e.currentTarget as HTMLElement).style.transform = "scale(1.02)"}
                          onMouseLeave={e => (e.currentTarget as HTMLElement).style.transform = "scale(1)"}
                        >
                          {launchRefs.length > 0 ? `START WITH ${launchRefs.length} REF${launchRefs.length > 1 ? "S" : ""} ✦` : "START EDITING →"}
                        </button>
                      </div>
                      {launchRefs.length === 0 && (
                        <p style={{ fontSize:9, color:"rgba(255,255,255,0.2)", textAlign:"center", marginTop:10, fontFamily:"'Space Grotesk',sans-serif", letterSpacing:"0.06em" }}>
                          Reference is optional — AI will use its default style without it
                        </p>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      ) : (
        <>
          <p style={{ fontSize:"clamp(2.5rem,8vw,7rem)", fontWeight:700, textTransform:"uppercase", letterSpacing:"-0.03em", color:"#FAFAFA" }}>
            {generating ? "EDITING..." : "UPLOADING..."}
          </p>
          <p style={{ fontSize:11, color:"#A1A1AA", letterSpacing:"0.15em", textTransform:"uppercase", fontWeight:600 }}>{upMsg}</p>
          <div style={{ width:280 }}>
            <div style={{ height:2, background:"#27272A" }}>
              <div style={{ height:"100%", width:`${upPct}%`, background:"#DFE104", transition:"width 400ms" }} />
            </div>
            <div style={{ display:"flex", justifyContent:"space-between", marginTop:8 }}>
              <span style={{ fontSize:10, color:"#A1A1AA", letterSpacing:"0.15em", textTransform:"uppercase", fontWeight:600 }}>PROGRESS</span>
              <span style={{ fontSize:10, color:"#DFE104", fontWeight:700, letterSpacing:"0.15em" }}>{Math.round(upPct)}%</span>
            </div>
          </div>
        </>
      )}
    </div>
  );

  if (trimFile) {
    const url = URL.createObjectURL(trimFile);
    return (
      <div style={{ background:"#09090B", color:"#FAFAFA", fontFamily:"'Space Grotesk',sans-serif", minHeight:"100vh", display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:24, padding:40 }}>
        <Noise />
        <p style={{ fontSize:"clamp(1.5rem,4vw,2.5rem)", fontWeight:700, textTransform:"uppercase", letterSpacing:"-0.03em", color:"#FAFAFA" }}>
          TRIM YOUR VIDEO
        </p>
        <p style={{ fontSize:11, color:"#A1A1AA", letterSpacing:"0.15em", textTransform:"uppercase", fontWeight:600 }}>
          {trimFile.name}
        </p>
        <div style={{ width:"100%", maxWidth:560 }}>
          <video
            ref={videoRef}
            src={url}
            onLoadedMetadata={() => {
              const d = videoRef.current?.duration || 0;
              setTrimDuration(d);
              setTrimEnd(d);
            }}
            controls
            style={{ width:"100%", borderRadius:8, border:"2px solid #3F3F46" }}
          />
        </div>
        {trimDuration > 0 && (
          <div style={{ width:"100%", maxWidth:560, display:"flex", flexDirection:"column", gap:16 }}>
            <div style={{ display:"flex", justifyContent:"space-between" }}>
              <span style={{ fontSize:10, color:"#A1A1AA", letterSpacing:"0.12em", textTransform:"uppercase" }}>
                Start: {trimStart.toFixed(1)}s
              </span>
              <span style={{ fontSize:10, color:"#A1A1AA", letterSpacing:"0.12em", textTransform:"uppercase" }}>
                End: {trimEnd.toFixed(1)}s
              </span>
            </div>
            <input type="range" min={0} max={trimDuration} step={0.1} value={trimStart}
              onChange={e => { const v = parseFloat(e.target.value); setTrimStart(Math.min(v, trimEnd - 1)); if (videoRef.current) videoRef.current.currentTime = v; }}
              style={{ width:"100%", accentColor:"#DFE104" }}
            />
            <input type="range" min={0} max={trimDuration} step={0.1} value={trimEnd}
              onChange={e => { const v = parseFloat(e.target.value); setTrimEnd(Math.max(v, trimStart + 1)); if (videoRef.current) videoRef.current.currentTime = v; }}
              style={{ width:"100%", accentColor:"#DFE104" }}
            />
            <div style={{ fontSize:10, color:"#A1A1AA", textAlign:"center", letterSpacing:"0.10em", textTransform:"uppercase" }}>
              Duration: {(trimEnd - trimStart).toFixed(1)}s
            </div>
            <div style={{ display:"flex", gap:12, justifyContent:"center" }}>
              <button onClick={() => { URL.revokeObjectURL(url); setTrimFile(null); setModal(true); }}
                style={{ background:"transparent", color:"#FAFAFA", border:"2px solid #3F3F46", fontWeight:700, fontSize:11, letterSpacing:"0.12em", textTransform:"uppercase", padding:"0 24px", height:44, cursor:"pointer" }}
              >CANCEL</button>
              <button onClick={() => { URL.revokeObjectURL(url); handleUploadFull(); }}
                style={{ background:"#DFE104", color:"#000", border:"none", fontWeight:700, fontSize:11, letterSpacing:"0.12em", textTransform:"uppercase", padding:"0 32px", height:44, cursor:"pointer" }}
              >UPLOAD FULL</button>
              <button onClick={() => { URL.revokeObjectURL(url); handleTrimConfirm(); }}
                style={{ background:"#6C63FF", color:"#fff", border:"none", fontWeight:700, fontSize:11, letterSpacing:"0.12em", textTransform:"uppercase", padding:"0 32px", height:44, cursor:"pointer" }}
              >TRIM & UPLOAD</button>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <>
      <Noise />
      <Orbs />
      <UploadModal open={modal} onClose={()=>setModal(false)} onFile={handleFiles} onYt={handleYt} onEditor={()=>{setModal(false);navigate({to:"/editor"});}} />
      <AuthModal open={authOpen} onClose={()=>setAuthOpen(false)} onLogin={() => setLoggedIn(true)} />

      <div style={{ position:"relative", zIndex:1, background:"#09090B", color:"#FAFAFA", fontFamily:"'Space Grotesk',sans-serif", minHeight:"100vh", overflowX:"hidden" }}>

        {/* ── NAV ── */}
        <Glass style={{
          display:"flex", alignItems:"center", justifyContent:"space-between",
          padding:"0 40px", height:64, borderRadius:0, borderTop:"none",
          borderLeft:"none", borderRight:"none", borderBottom:"1px solid rgba(255,255,255,0.06)",
          position:"sticky", top:0, zIndex:50,
        }}>
          <span style={{ fontWeight:700, fontSize:14, letterSpacing:"0.22em", textTransform:"uppercase" }}>AUTEUR</span>
          <div style={{ display:"flex", alignItems:"center", gap:32 }}>
            {[
              { l: "FEATURES", onClick: () => document.getElementById("capabilities")?.scrollIntoView({ behavior: "smooth" }) },
              { l: "PRICING", onClick: () => navigate({ to: "/pricing" }) },
              { l: "CHANGELOG", onClick: () => window.open("https://github.com/anomalyco/auteur/releases", "_blank") },
            ].map(({ l, onClick }) => (
              <button key={l} onClick={onClick} style={{ background:"none", border:"none", color:"#FAFAFA", fontFamily:"'Space Grotesk',sans-serif", fontWeight:700, fontSize:11, letterSpacing:"0.15em", textTransform:"uppercase", cursor:"pointer", transition:"color 200ms" }}
                onMouseEnter={e=>(e.currentTarget.style.color="#DFE104")}
                onMouseLeave={e=>(e.currentTarget.style.color="#FAFAFA")}
              >{l}</button>
            ))}
            {loggedIn ? (
              <button onClick={async () => { try { await auth.signout(); } catch {} localStorage.removeItem("auteur_token"); setLoggedIn(false); }} style={{ background:"none", border:"none", color:"#FAFAFA", fontFamily:"'Space Grotesk',sans-serif", fontWeight:700, fontSize:11, letterSpacing:"0.15em", textTransform:"uppercase", cursor:"pointer" }}
                onMouseEnter={e=>(e.currentTarget.style.color="#DFE104")}
                onMouseLeave={e=>(e.currentTarget.style.color="#FAFAFA")}
              >LOGOUT</button>
            ) : (
              <button onClick={() => setAuthOpen(true)} style={{ background:"none", border:"none", color:"#FAFAFA", fontFamily:"'Space Grotesk',sans-serif", fontWeight:700, fontSize:11, letterSpacing:"0.15em", textTransform:"uppercase", cursor:"pointer" }}
                onMouseEnter={e=>(e.currentTarget.style.color="#DFE104")}
                onMouseLeave={e=>(e.currentTarget.style.color="#FAFAFA")}
              >SIGN IN</button>
            )}
          </div>
          <Glass style={{ display:"inline-flex", alignItems:"center", gap:6, padding:"0 24px", height:40, cursor:"pointer" }}>
            <button onClick={()=>setModal(true)}
              style={{ background:"none", border:"none", color:"#DFE104", fontWeight:700, fontSize:11, letterSpacing:"0.12em", textTransform:"uppercase", cursor:"pointer", padding:0 }}
            >GET STARTED <ArrowUpRight size={14} style={{ verticalAlign:"middle", marginLeft:4 }} /></button>
          </Glass>
        </Glass>

        {/* ── HERO ── */}
        <section style={{
          padding:"0 40px", position:"relative", overflow:"hidden",
          minHeight:"calc(100vh - 64px)", display:"flex", flexDirection:"column",
          justifyContent:"center",
        }}>
          <span aria-hidden="true" style={{
            position:"absolute", right:-40, top:-80,
            fontSize:"clamp(12rem,30vw,40rem)", fontWeight:700, lineHeight:0.7,
            color:"#18181B", letterSpacing:"-0.06em", userSelect:"none", pointerEvents:"none",
          }}>AI</span>

          <Glass style={{ padding:"32px 40px 24px", maxWidth:900, margin:"0 auto" }}>
            <div style={{ display:"inline-flex", alignItems:"center", gap:6, padding:"4px 16px", borderRadius:100, background:"rgba(223,225,4,0.1)", border:"1px solid rgba(223,225,4,0.2)", marginBottom:16 }}>
              <Sparkles size={12} color="#DFE104" />
              <span style={{ fontSize:10, color:"#DFE104", letterSpacing:"0.12em", textTransform:"uppercase", fontWeight:700 }}>AI-POWERED VIDEO EDITING</span>
            </div>

            <h1 style={{
              fontSize:"clamp(3rem,10vw,10rem)", fontWeight:700, lineHeight:0.88,
              letterSpacing:"-0.04em", textTransform:"uppercase",
            }}>
              <span style={{ display:"block" }}>EDIT VIDEOS</span>
              <span style={{ display:"block", color:"#DFE104" }}>LIKE A PRO</span>
              <span style={{ display:"block" }}>CREATOR.</span>
            </h1>

            <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", gap:24, paddingTop:20, marginTop:20, borderTop:"1px solid rgba(255,255,255,0.06)", flexWrap:"wrap" }}>
              <p style={{ maxWidth:400, fontSize:14, lineHeight:1.6, color:"#A1A1AA", fontWeight:500 }}>
                Drop a clip. Describe your vibe. Ship the reel.<br />
                Auteur handles cutting, captions, color &amp; sound — powered by AI.
              </p>
              <div style={{ display:"flex", alignItems:"center", gap:10, flexShrink:0, flexWrap:"wrap" }}>
                <button onClick={()=>setModal(true)}
                  style={{ display:"inline-flex", alignItems:"center", gap:8, background:"#DFE104", color:"#000", border:"none", fontWeight:700, fontSize:12, letterSpacing:"0.12em", textTransform:"uppercase", padding:"0 28px", height:48, cursor:"pointer", borderRadius:12, transition:"transform 120ms, box-shadow 200ms" }}
                  onMouseEnter={e=>{ const el=e.currentTarget; el.style.transform="scale(1.05)"; el.style.boxShadow="0 0 40px rgba(223,225,4,0.3)"; }}
                  onMouseLeave={e=>{ const el=e.currentTarget; el.style.transform="scale(1)"; el.style.boxShadow="none"; }}
                >
                  START EDITING FREE <ArrowUpRight size={18} />
                </button>
                <Glass style={{ padding:"0 20px", height:48, cursor:"pointer" }}>
                  <button onClick={()=>navigate({to:"/editor"})}
                    style={{ background:"none", border:"none", color:"#FAFAFA", fontWeight:700, fontSize:12, letterSpacing:"0.12em", textTransform:"uppercase", cursor:"pointer", padding:0, height:"100%" }}
                  >OPEN EDITOR →</button>
                </Glass>
              </div>
            </div>
          </Glass>

          {/* Stats grid */}
          <div style={{ display:"flex", gap:12, marginTop:"auto", padding:"16px 0", justifyContent:"center" }}>
            {STATS.map(({v,l}) => (
              <Glass key={l} style={{ flex:"1 1 120px", padding:"14px 12px", textAlign:"center", borderRadius:12 }}>
                <p style={{ fontWeight:700, fontSize:"clamp(1rem,2vw,1.5rem)", letterSpacing:"-0.03em", color:"#DFE104", lineHeight:1 }}>{v}</p>
                <p style={{ fontSize:9, color:"#FAFAFA", letterSpacing:"0.16em", textTransform:"uppercase", marginTop:6, fontWeight:600, opacity:0.6 }}>{l}</p>
              </Glass>
            ))}
          </div>
        </section>

        {/* ── MARQUEE 1 ── */}
        <div style={{ borderTop:"1px solid rgba(255,255,255,0.06)", borderBottom:"1px solid rgba(255,255,255,0.06)" }}>
          <Glass style={{ borderRadius:0, border:"none", borderTop:"1px solid rgba(255,255,255,0.04)", borderBottom:"1px solid rgba(255,255,255,0.04)", padding:"16px 0" }}>
            <Marquee speed={80}>
              {["SMART CUT","✦","AUTO CAPTIONS","✦","COLOR GRADE","✦","AI ZOOM","✦","SOUND MATCH","✦","EXPORT 4K","✦","STYLE TRAIN","✦","HOOK DETECT","✦"].map((w,i) => (
                <span key={i} style={{ padding:"0 32px", fontWeight:700, textTransform:"uppercase", fontSize:15, letterSpacing:"-0.01em", whiteSpace:"nowrap", color:"#DFE104", opacity: w==="✦"?0.3:1 }}>{w}</span>
              ))}
            </Marquee>
          </Glass>
        </div>

        {/* ── CAPABILITIES ── */}
        <section id="capabilities" style={{ padding:"60px 40px 0" }}>
          <div style={{ display:"flex", alignItems:"center", gap:16, marginBottom:48, maxWidth:900, margin:"0 auto 48px" }}>
            <span style={{ fontSize:11, color:"#FAFAFA", letterSpacing:"0.18em", textTransform:"uppercase", fontWeight:700, opacity:0.6 }}>WHAT AUTEUR DOES</span>
            <div style={{ flex:1, height:1, background:"rgba(255,255,255,0.06)" }} />
          </div>

          <div style={{ position:"relative", maxWidth:900, margin:"0 auto" }}>
            <span aria-hidden="true" style={{
              position:"absolute", right:0, top:-40,
              fontSize:"clamp(6rem,15vw,12rem)", fontWeight:700, lineHeight:0.8,
              color:"#18181B", letterSpacing:"-0.05em", userSelect:"none", pointerEvents:"none",
            }}>05</span>
            <h2 style={{
              fontSize:"clamp(2.5rem,8vw,7rem)", fontWeight:700, letterSpacing:"-0.03em",
              textTransform:"uppercase", lineHeight:0.88, marginBottom:48, position:"relative", zIndex:1,
            }}>CAPABILITIES</h2>
          </div>

          <div style={{ maxWidth:900, margin:"0 auto" }}>
            {CAPS.map(c => <CapRow key={c.num} {...c} />)}
          </div>
        </section>

        {/* ── MARQUEE 2 — TESTIMONIALS, SLOWER ── */}
        <div style={{ marginTop:80, borderTop:"1px solid rgba(255,255,255,0.06)", borderBottom:"1px solid rgba(255,255,255,0.06)" }}>
          <Glass style={{ borderRadius:0, border:"none", borderTop:"1px solid rgba(255,255,255,0.04)", borderBottom:"1px solid rgba(255,255,255,0.04)", padding:"16px 0" }}>
            <Marquee speed={40}>
              {['"BEST EDITOR I\'VE EVER USED" —@creator','✦','"SAVES 3 HRS/VIDEO" —@filmmaker','✦','"THE AI JUST GETS IT" —@studio','✦','"1K→100K IN 60 DAYS" —@creator','✦'].map((w,i) => (
                <span key={i} style={{ padding:"0 40px", fontWeight:600, fontSize:14, whiteSpace:"nowrap", color:"#A1A1AA", letterSpacing:"-0.01em", opacity: w==="✦"?0.3:1 }}>{w}</span>
              ))}
            </Marquee>
          </Glass>
        </div>

        {/* ── CTA ── */}
        <section style={{ padding:"100px 40px", position:"relative", overflow:"hidden" }}>
          <span aria-hidden="true" style={{
            position:"absolute", left:-20, bottom:-40,
            fontSize:"clamp(10rem,25vw,20rem)", fontWeight:700, lineHeight:0.7,
            color:"#18181B", letterSpacing:"-0.06em", userSelect:"none", pointerEvents:"none",
          }}>GO</span>

          <Glass style={{ padding:"64px 48px", maxWidth:700, margin:"0 auto", textAlign:"center" }}>
            <h2 style={{
              fontSize:"clamp(2.5rem,8vw,8rem)", fontWeight:700, lineHeight:0.88,
              letterSpacing:"-0.04em", textTransform:"uppercase",
            }}>
              <span style={{ display:"block", color:"#DFE104" }}>YOUR NEXT</span>
              <span style={{ display:"block" }}>VIDEO</span>
              <span style={{ display:"block" }}>AWAITS.</span>
            </h2>
            <p style={{ maxWidth:400, margin:"24px auto 0", fontSize:14, color:"#A1A1AA", lineHeight:1.7 }}>
              Upload raw footage. Write a prompt. Get a polished reel in minutes — not hours.
            </p>
            <button onClick={()=>setModal(true)}
              style={{ display:"inline-flex", alignItems:"center", gap:8, background:"#DFE104", color:"#000", border:"none", fontWeight:700, fontSize:13, letterSpacing:"0.12em", textTransform:"uppercase", padding:"0 40px", height:60, cursor:"pointer", borderRadius:12, marginTop:32, transition:"transform 120ms, box-shadow 200ms" }}
              onMouseEnter={e=>{ const el=e.currentTarget; el.style.transform="scale(1.05)"; el.style.boxShadow="0 0 40px rgba(223,225,4,0.3)"; }}
              onMouseLeave={e=>{ const el=e.currentTarget; el.style.transform="scale(1)"; el.style.boxShadow="none"; }}
            >
              UPLOAD &amp; START EDITING <ArrowUpRight size={20} />
            </button>
          </Glass>
        </section>

        {/* ── FOOTER ── */}
        <Glass style={{
          display:"flex", alignItems:"center", justifyContent:"space-between",
          padding:"20px 40px", borderRadius:0, borderLeft:"none", borderRight:"none", borderBottom:"none",
        }}>
          <span style={{ fontWeight:700, fontSize:14, letterSpacing:"0.22em", textTransform:"uppercase" }}>AUTEUR</span>
          <span style={{ fontSize:10, color:"rgba(255,255,255,0.3)", letterSpacing:"0.14em", textTransform:"uppercase", fontWeight:600 }}>© 2024 AUTEUR. ALL RIGHTS RESERVED.</span>
          <div style={{ display:"flex", gap:24 }}>
            {[
              { l: "PRIVACY", onClick: () => window.open("https://auteur.ai/privacy", "_blank") },
              { l: "TERMS", onClick: () => window.open("https://auteur.ai/terms", "_blank") },
              { l: "SUPPORT", onClick: () => window.open("mailto:support@auteur.ai") },
            ].map(({ l, onClick }) => (
              <button key={l} onClick={onClick} style={{ background:"none", border:"none", fontSize:10, color:"rgba(255,255,255,0.3)", letterSpacing:"0.14em", textTransform:"uppercase", cursor:"pointer", fontFamily:"'Space Grotesk',sans-serif", fontWeight:700 }}
                onMouseEnter={e=>e.currentTarget.style.color="#DFE104"}
                onMouseLeave={e=>e.currentTarget.style.color="rgba(255,255,255,0.3)"}
              >{l}</button>
            ))}
          </div>
        </Glass>

        {/* ── Global Styles ── */}
        <style>{`
          @media (prefers-reduced-motion: reduce) {
            .marquee-track, .marquee-track-rev { animation: none !important; }
          }
          @keyframes orbFloat {
            0%, 100% { transform: translate(0, 0) scale(1); }
            33% { transform: translate(30px, -50px) scale(1.1); }
            66% { transform: translate(-20px, 30px) scale(0.9); }
          }
        `}</style>
      </div>
    </>
  );
}
