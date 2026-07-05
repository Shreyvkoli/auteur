import { createFileRoute, Link } from "@tanstack/react-router";
import { Trash2, Plus, Play } from "lucide-react";
import { useState, useEffect } from "react";
import { AppShell } from "@/components/app-shell";
import { edit, jobs } from "@/lib/api";
import { toast } from "@/components/editor/Toast";

export const Route = createFileRoute("/projects")({ component: Projects });

interface ProjectItem {
  id: string;
  prompt?: string;
  version_type?: string;
  status?: string;
  created_at?: string;
  [key: string]: any;
}

const PAGE_SIZE = 20;

function Projects() {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  const fetchProjects = async (reset = false) => {
    try {
      const data: any = await edit.history();
      const items = Array.isArray(data) ? data as ProjectItem[] : [];
      if (reset) {
        setProjects(items.slice(0, PAGE_SIZE));
        setOffset(PAGE_SIZE);
        setHasMore(items.length > PAGE_SIZE);
      } else {
        const next = items.slice(offset, offset + PAGE_SIZE);
        setProjects(prev => [...prev, ...next]);
        setOffset(prev => prev + PAGE_SIZE);
        setHasMore(offset + PAGE_SIZE < items.length);
      }
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchProjects(true); }, []);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    if (!confirm("Delete this project?")) return;
    try {
      await jobs.cancel(id);
      setProjects(prev => prev.filter(p => p.id !== id));
    } catch { toast("Delete failed", "error"); }
  };

  return (
    <AppShell>
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:24 }}>
        <div>
          <h1 style={{ fontSize:"clamp(1.5rem,4vw,2.5rem)", fontWeight:700, letterSpacing:"-0.02em", textTransform:"uppercase", color:"#FAFAFA", fontFamily:"'Space Grotesk',sans-serif" }}>
            PROJECTS
          </h1>
          <p style={{ fontSize:11, color:"#A1A1AA", fontWeight:600, letterSpacing:"0.10em", textTransform:"uppercase", marginTop:4 }}>
            {loading ? "LOADING..." : `${projects.length} EDITS`}
          </p>
        </div>
        <Link to="/" style={{ display:"inline-flex", alignItems:"center", gap:6, background:"#DFE104", color:"#000", border:"none", fontWeight:700, fontSize:10, letterSpacing:"0.12em", textTransform:"uppercase", padding:"0 20px", height:44, cursor:"pointer", textDecoration:"none" }}>
          <Plus size={14} /> NEW
        </Link>
      </div>

      {loading ? (
        <div style={{ textAlign:"center", padding:"60px 0", fontSize:12, color:"#6B7280" }}>LOADING...</div>
      ) : projects.length === 0 ? (
        <div style={{ textAlign:"center", padding:"60px 0", border:"2px solid #3F3F46" }}>
          <p style={{ fontSize:12, color:"#A1A1AA" }}>NO PROJECTS YET</p>
          <Link to="/" style={{ display:"inline-block", marginTop:16, padding:"10px 24px", background:"#DFE104", color:"#000", fontWeight:700, fontSize:10, letterSpacing:"0.12em", textTransform:"uppercase", textDecoration:"none" }}>
            CREATE YOUR FIRST EDIT
          </Link>
        </div>
      ) : (
        <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
          {projects.map((p) => (
            <Link key={p.id} to="/editor" style={{ display:"flex", alignItems:"center", gap:16, padding:"12px 16px", border:"2px solid #3F3F46", textDecoration:"none", transition:"background 200ms" }}
              onMouseEnter={e => (e.currentTarget as HTMLElement).style.background="#DFE104"}
              onMouseLeave={e => (e.currentTarget as HTMLElement).style.background="transparent"}
              className="group"
            >
              <div style={{ width:60, height:56, background:"#27272A", display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0 }}>
                <Play size={16} style={{ color:"#6B7280", fill:"#6B7280" }} />
              </div>
              <div style={{ flex:1, minWidth:0 }}>
                <p style={{ fontSize:13, fontWeight:700, color:"#FAFAFA", textTransform:"uppercase", letterSpacing:"-0.01em", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}
                  className="group-hover:text-black"
                >{p.prompt?.slice(0, 40) || p.version_type || "UNTITLED"}</p>
                <p style={{ fontSize:10, color:"#A1A1AA", fontWeight:600, letterSpacing:"0.08em", marginTop:2 }}
                  className="group-hover:text-black/60"
                >{p.version_type || "DRAFT"} · {p.status || "UNKNOWN"}</p>
                <p style={{ fontSize:9, color:"#6B7280", marginTop:1 }}
                  className="group-hover:text-black/40"
                >{p.created_at ? new Date(p.created_at).toLocaleDateString() : ""}</p>
              </div>
              <button onClick={(e) => handleDelete(e, p.id)}
                style={{ width:36, height:36, display:"flex", alignItems:"center", justifyContent:"center", background:"transparent", border:"2px solid #3F3F46", color:"#ef4444", cursor:"pointer", flexShrink:0, transition:"background 200ms" }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background="#ef4444"; (e.currentTarget as HTMLElement).style.color="#fff"; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background="transparent"; (e.currentTarget as HTMLElement).style.color="#ef4444"; }}
              >
                <Trash2 size={13} />
              </button>
            </Link>
          ))}
          {hasMore && (
            <div style={{ textAlign:"center", marginTop:8 }}>
              <button onClick={() => fetchProjects(false)}
                style={{ padding:"10px 32px", background:"transparent", border:"2px solid #3F3F46", color:"#A1A1AA", fontWeight:700, fontSize:10, letterSpacing:"0.12em", textTransform:"uppercase", cursor:"pointer" }}>
                LOAD MORE
              </button>
            </div>
          )}
        </div>
      )}
    </AppShell>
  );
}
