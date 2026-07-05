import { useState, useEffect, useRef } from "react";
import {
  FileVideo,
  Music,
  Image,
  Search,
  Loader2,
  Package,
  FolderOpen,
  Upload,
  Trash2,
  Play,
  Plus,
  Wand2,
  Disc3,
  Clock,
  CheckCircle2,
  AlertCircle,
  Hourglass,
} from "lucide-react";
import { vault, edit, jobs, type VaultItem } from "@/lib/api";
import { toast } from "./Toast";
import { useNavigate } from "@tanstack/react-router";

interface LeftPanelProps {
  videoUrl?: string;
  onAddVideo?: (url: string) => void;
}

type Tab = "assets" | "vault" | "projects";

interface ProjectItem {
  id: string;
  prompt?: string;
  version_type?: string;
  status?: string;
  created_at?: string;
  [key: string]: any;
}

const font = "'Space Grotesk',sans-serif";

function statusIcon(status?: string) {
  if (status === "completed") return <CheckCircle2 size={10} color="#22c55e" />;
  if (status === "failed") return <AlertCircle size={10} color="#ef4444" />;
  if (status === "running") return <Loader2 size={10} color="#DFE104" className="spin" />;
  return <Hourglass size={10} color="#A1A1AA" />;
}

function statusColor(status?: string) {
  if (status === "completed") return "#22c55e";
  if (status === "failed") return "#ef4444";
  if (status === "running") return "#DFE104";
  return "#A1A1AA";
}

// ── Assets Tab ──────────────────────────────────────────────────────────────
function AssetsTab({ videoUrl, onAddVideo }: { videoUrl?: string; onAddVideo?: (url: string) => void }) {
  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "10px 0" }}>
      {videoUrl ? (
        <>
          <SectionLabel>Source</SectionLabel>
          <div
            onClick={() => onAddVideo?.(videoUrl)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "6px 12px",
              cursor: "pointer",
              transition: "background 120ms",
              borderRadius: 6,
              margin: "0 6px",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 6,
                background: "rgba(37,99,235,0.15)",
                border: "1px solid rgba(37,99,235,0.25)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <FileVideo size={14} color="#60a5fa" />
            </div>
            <div style={{ minWidth: 0 }}>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: "#FAFAFA",
                  fontFamily: font,
                  display: "block",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                Main Video
              </span>
              <span style={{ fontSize: 9, color: "#A1A1AA", fontFamily: font, letterSpacing: "0.05em" }}>
                Click to add to timeline
              </span>
            </div>
          </div>
        </>
      ) : (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "40px 20px",
            gap: 8,
            opacity: 0.4,
          }}
        >
          <FileVideo size={24} color="#FAFAFA" />
          <p style={{ fontSize: 10, color: "#FAFAFA", fontFamily: font, textAlign: "center", letterSpacing: "0.08em" }}>
            No video loaded
          </p>
        </div>
      )}
    </div>
  );
}

// ── Vault Tab ───────────────────────────────────────────────────────────────
function VaultTab() {
  const [items, setItems] = useState<VaultItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [q, setQ] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const fetchItems = async () => {
    setLoading(true);
    try {
      const res = await vault.list(undefined, 100, 0);
      setItems(res?.items || []);
    } catch {
      setItems([]);
    }
    setLoading(false);
  };

  useEffect(() => { fetchItems(); }, []);

  const handleDelete = async (id: string) => {
    try {
      await vault.delete(id);
      setItems((prev) => prev.filter((i) => i.id !== id));
      toast("Deleted", "success");
    } catch {
      toast("Delete failed", "error");
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const itemType = f.type.startsWith("audio") ? "sound" : f.type.startsWith("image") ? "meme" : "meme";
      await vault.upload(f, itemType, f.name);
      await fetchItems();
      toast("Added to vault!", "success");
    } catch {
      toast("Upload failed", "error");
    }
    setUploading(false);
    e.target.value = "";
  };

  const filtered = items.filter((i) => i.name.toLowerCase().includes(q.toLowerCase()));
  const memes = filtered.filter((i) => i.type === "meme" || i.type === "image");
  const sounds = filtered.filter((i) => i.type === "sound" || i.type === "music" || i.type === "audio");
  const others = filtered.filter((i) => !["meme", "image", "sound", "music", "audio"].includes(i.type));

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
      {/* Search + Upload */}
      <div style={{ padding: "8px 10px", display: "flex", gap: 6, borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            flex: 1,
            padding: "0 7px",
            height: 28,
            background: "rgba(0,0,0,0.4)",
            border: "1px solid rgba(255,255,255,0.07)",
            borderRadius: 6,
          }}
        >
          <Search size={10} color="#A1A1AA" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search vault..."
            style={{
              flex: 1,
              background: "none",
              border: "none",
              outline: "none",
              color: "#FAFAFA",
              fontSize: 10,
              fontFamily: font,
            }}
          />
        </div>
        <input ref={fileRef} type="file" accept="video/*,audio/*,image/*" style={{ display: "none" }} onChange={handleUpload} />
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          title="Add to vault"
          style={{
            width: 28,
            height: 28,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: uploading ? "rgba(255,255,255,0.04)" : "rgba(223,225,4,0.12)",
            border: "1px solid " + (uploading ? "rgba(255,255,255,0.07)" : "rgba(223,225,4,0.3)"),
            borderRadius: 6,
            cursor: uploading ? "not-allowed" : "pointer",
            color: uploading ? "#A1A1AA" : "#DFE104",
            transition: "all 0.15s",
            flexShrink: 0,
          }}
          onMouseEnter={(e) => { if (!uploading) e.currentTarget.style.background = "rgba(223,225,4,0.2)"; }}
          onMouseLeave={(e) => { if (!uploading) e.currentTarget.style.background = "rgba(223,225,4,0.12)"; }}
        >
          {uploading ? <Loader2 size={11} className="spin" /> : <Plus size={11} />}
        </button>
      </div>

      {/* List */}
      <div style={{ flex: 1, overflowY: "auto", padding: "6px 0" }}>
        {loading ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
            <Loader2 size={14} color="#DFE104" className="spin" />
          </div>
        ) : items.length === 0 ? (
          <div style={{ textAlign: "center", padding: "30px 16px", opacity: 0.4 }}>
            <Package size={22} color="#FAFAFA" style={{ margin: "0 auto 8px" }} />
            <p style={{ fontSize: 10, color: "#FAFAFA", fontFamily: font, letterSpacing: "0.08em" }}>Vault is empty</p>
            <p style={{ fontSize: 9, color: "#A1A1AA", fontFamily: font, marginTop: 4 }}>Click + to upload</p>
          </div>
        ) : (
          <>
            {/* Memes / Images */}
            {memes.length > 0 && (
              <>
                <SectionLabel icon={<Wand2 size={9} />}>Memes</SectionLabel>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 5, padding: "0 8px 8px" }}>
                  {memes.map((m) => (
                    <VaultCard key={m.id} item={m} onDelete={handleDelete} />
                  ))}
                </div>
              </>
            )}

            {/* Sounds */}
            {sounds.length > 0 && (
              <>
                <SectionLabel icon={<Disc3 size={9} />}>Sounds & Music</SectionLabel>
                {sounds.map((s) => (
                  <SoundRow key={s.id} item={s} onDelete={handleDelete} />
                ))}
              </>
            )}

            {/* Others */}
            {others.length > 0 && (
              <>
                <SectionLabel icon={<Package size={9} />}>Other</SectionLabel>
                {others.map((o) => (
                  <SoundRow key={o.id} item={o} onDelete={handleDelete} />
                ))}
              </>
            )}

            {filtered.length === 0 && q && (
              <div style={{ textAlign: "center", padding: 20, opacity: 0.4 }}>
                <p style={{ fontSize: 10, color: "#FAFAFA", fontFamily: font }}>No results for "{q}"</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function VaultCard({ item, onDelete }: { item: VaultItem; onDelete: (id: string) => void }) {
  const [hovering, setHovering] = useState(false);
  return (
    <div
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      style={{
        position: "relative",
        aspectRatio: "1",
        borderRadius: 7,
        background: "rgba(255,255,255,0.04)",
        border: "1px solid " + (hovering ? "rgba(223,225,4,0.25)" : "rgba(255,255,255,0.07)"),
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
        cursor: "pointer",
        transition: "border-color 0.15s",
      }}
    >
      <Image size={16} color="#A1A1AA" />
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          padding: "3px 5px",
          background: "rgba(0,0,0,0.7)",
          fontSize: 8,
          color: "#FAFAFA",
          fontFamily: font,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {item.name}
      </div>
      {hovering && (
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(item.id); }}
          style={{
            position: "absolute",
            top: 3,
            right: 3,
            width: 20,
            height: 20,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(239,68,68,0.85)",
            border: "none",
            borderRadius: 4,
            cursor: "pointer",
            color: "#fff",
          }}
        >
          <Trash2 size={9} />
        </button>
      )}
    </div>
  );
}

function SoundRow({ item, onDelete }: { item: VaultItem; onDelete: (id: string) => void }) {
  const [hovering, setHovering] = useState(false);
  return (
    <div
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "5px 10px",
        margin: "0 6px 2px",
        borderRadius: 6,
        background: hovering ? "rgba(255,255,255,0.04)" : "transparent",
        border: "1px solid " + (hovering ? "rgba(255,255,255,0.08)" : "transparent"),
        cursor: "pointer",
        transition: "all 0.12s",
      }}
    >
      <div
        style={{
          width: 26,
          height: 26,
          borderRadius: 5,
          background: "rgba(139,92,246,0.15)",
          border: "1px solid rgba(139,92,246,0.2)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <Music size={11} color="#a78bfa" />
      </div>
      <span
        style={{
          flex: 1,
          fontSize: 10,
          fontWeight: 500,
          color: "#FAFAFA",
          fontFamily: font,
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {item.name}
      </span>
      {hovering && (
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(item.id); }}
          style={{
            width: 20,
            height: 20,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(239,68,68,0.1)",
            border: "1px solid rgba(239,68,68,0.2)",
            borderRadius: 4,
            cursor: "pointer",
            color: "#ef4444",
            flexShrink: 0,
          }}
        >
          <Trash2 size={9} />
        </button>
      )}
    </div>
  );
}

// ── Projects Tab ─────────────────────────────────────────────────────────────
function ProjectsTab() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    edit.history()
      .then((data: any) => {
        const items = Array.isArray(data) ? (data as ProjectItem[]) : [];
        setProjects(items.slice(0, 30));
      })
      .catch(() => setProjects([]))
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("Delete this project?")) return;
    try {
      await jobs.cancel(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
      toast("Project deleted", "success");
    } catch {
      toast("Delete failed", "error");
    }
  };

  const handleOpen = (p: ProjectItem) => {
    sessionStorage.setItem("auteur_current_job_id", p.id);
    navigate({ to: "/editor" });
    window.location.reload();
  };

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "6px 0" }}>
      {loading ? (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
          <Loader2 size={14} color="#DFE104" className="spin" />
        </div>
      ) : projects.length === 0 ? (
        <div style={{ textAlign: "center", padding: "30px 16px", opacity: 0.4 }}>
          <FolderOpen size={22} color="#FAFAFA" style={{ margin: "0 auto 8px" }} />
          <p style={{ fontSize: 10, color: "#FAFAFA", fontFamily: font, letterSpacing: "0.08em" }}>No projects yet</p>
          <p style={{ fontSize: 9, color: "#A1A1AA", fontFamily: font, marginTop: 4 }}>Start editing to see history</p>
        </div>
      ) : (
        projects.map((p) => <ProjectRow key={p.id} project={p} onOpen={handleOpen} onDelete={handleDelete} />)
      )}
    </div>
  );
}

function ProjectRow({
  project: p,
  onOpen,
  onDelete,
}: {
  project: ProjectItem;
  onOpen: (p: ProjectItem) => void;
  onDelete: (e: React.MouseEvent, id: string) => void;
}) {
  const [hovering, setHovering] = useState(false);
  const label = p.prompt?.slice(0, 32) || p.version_type || "Untitled";

  return (
    <div
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      onClick={() => onOpen(p)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "7px 10px",
        margin: "0 6px 3px",
        borderRadius: 7,
        background: hovering ? "rgba(223,225,4,0.06)" : "rgba(255,255,255,0.02)",
        border: "1px solid " + (hovering ? "rgba(223,225,4,0.2)" : "rgba(255,255,255,0.05)"),
        cursor: "pointer",
        transition: "all 0.15s",
      }}
    >
      {/* Thumbnail placeholder */}
      <div
        style={{
          width: 38,
          height: 34,
          borderRadius: 5,
          background: "rgba(255,255,255,0.04)",
          border: "1px solid rgba(255,255,255,0.07)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <Play size={11} color="#A1A1AA" fill="#A1A1AA" />
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p
          style={{
            fontSize: 10,
            fontWeight: 600,
            color: hovering ? "#DFE104" : "#FAFAFA",
            fontFamily: font,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            transition: "color 0.15s",
          }}
        >
          {label}
        </p>
        <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 2 }}>
          {statusIcon(p.status)}
          <span style={{ fontSize: 8, color: statusColor(p.status), fontFamily: font, textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 700 }}>
            {p.status || "unknown"}
          </span>
          {p.created_at && (
            <>
              <span style={{ fontSize: 8, color: "#3F3F46" }}>·</span>
              <Clock size={8} color="#6B7280" />
              <span style={{ fontSize: 8, color: "#6B7280", fontFamily: font }}>
                {new Date(p.created_at).toLocaleDateString()}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Delete */}
      {hovering && (
        <button
          onClick={(e) => onDelete(e, p.id)}
          style={{
            width: 22,
            height: 22,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(239,68,68,0.1)",
            border: "1px solid rgba(239,68,68,0.2)",
            borderRadius: 5,
            cursor: "pointer",
            color: "#ef4444",
            flexShrink: 0,
          }}
          title="Delete project"
        >
          <Trash2 size={9} />
        </button>
      )}
    </div>
  );
}

// ── Shared helpers ───────────────────────────────────────────────────────────
function SectionLabel({ children, icon }: { children: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 5,
        padding: "8px 12px 4px",
      }}
    >
      {icon && <span style={{ color: "#DFE104", opacity: 0.7 }}>{icon}</span>}
      <span
        style={{
          fontSize: 8,
          fontWeight: 700,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: "#6B7280",
          fontFamily: font,
        }}
      >
        {children}
      </span>
    </div>
  );
}

// ── Main LeftPanel ───────────────────────────────────────────────────────────
export function LeftPanel({ videoUrl, onAddVideo }: LeftPanelProps) {
  const [tab, setTab] = useState<Tab>("assets");

  const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "assets", label: "Assets", icon: <FileVideo size={12} /> },
    { key: "vault", label: "Vault", icon: <Package size={12} /> },
    { key: "projects", label: "Projects", icon: <FolderOpen size={12} /> },
  ];

  return (
    <div
      style={{
        width: 220,
        flexShrink: 0,
        background: "#050507",
        borderRight: "1px solid rgba(255,255,255,0.07)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Tab strip */}
      <div
        style={{
          display: "flex",
          flexShrink: 0,
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          background: "#030304",
        }}
      >
        {TABS.map(({ key, label, icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexDirection: "column",
              gap: 3,
              padding: "8px 0",
              background: "transparent",
              border: "none",
              borderBottom: tab === key ? "2px solid #DFE104" : "2px solid transparent",
              cursor: "pointer",
              color: tab === key ? "#DFE104" : "#6B7280",
              fontFamily: font,
              fontWeight: 600,
              fontSize: 8,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              transition: "all 0.15s",
            }}
            onMouseEnter={(e) => {
              if (tab !== key) e.currentTarget.style.color = "#A1A1AA";
            }}
            onMouseLeave={(e) => {
              if (tab !== key) e.currentTarget.style.color = "#6B7280";
            }}
          >
            {icon}
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "assets" && <AssetsTab videoUrl={videoUrl} onAddVideo={onAddVideo} />}
      {tab === "vault" && <VaultTab />}
      {tab === "projects" && <ProjectsTab />}
    </div>
  );
}
