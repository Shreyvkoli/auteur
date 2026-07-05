import { createFileRoute } from "@tanstack/react-router";
import { Search, Plus, Trash2, Play, Music, Disc3, Wand2, Upload, Loader2 } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { AppShell } from "@/components/app-shell";
import { vault, type VaultItem } from "@/lib/api";
import { toast } from "@/components/editor/Toast";

export const Route = createFileRoute("/vault")({ component: Vault });

function Vault() {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<VaultItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);
  const LIMIT = 50;

  const fetchItems = async (reset = false) => {
    setLoading(true);
    try {
      const newOffset = reset ? 0 : offset;
      const res = await vault.list(undefined, LIMIT, newOffset);
      const newItems = res?.items || [];
      setItems(reset ? newItems : [...items, ...newItems]);
      setTotal(res?.total || 0);
      setOffset(newOffset + LIMIT);
    } catch { if (reset) setItems([]); }
    setLoading(false);
  };

  useEffect(() => { fetchItems(true); }, []);

  const handleDelete = async (id: string) => {
    try { await vault.delete(id); setItems((prev) => prev.filter((i) => i.id !== id)); }
    catch (e: any) { toast(e.message, "error"); }
  };

  const memes = items.filter((i) => i.type === "meme").filter((i) => i.name.toLowerCase().includes(q.toLowerCase()));
  const sounds = items.filter((i) => i.type === "sound").filter((i) => i.name.toLowerCase().includes(q.toLowerCase()));
  const musicItems = items.filter((i) => i.type === "music" || i.type === "audio").filter((i) => i.name.toLowerCase().includes(q.toLowerCase()));
  const others = items.filter((i) => !["meme", "sound", "music", "audio"].includes(i.type)).filter((i) => i.name.toLowerCase().includes(q.toLowerCase()));

  return (
    <AppShell>
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between" }}>
        <div>
          <h1 style={{ fontSize:"clamp(1.5rem,4vw,2.5rem)", fontWeight:700, letterSpacing:"-0.02em", textTransform:"uppercase", color:"#FAFAFA", fontFamily:"'Space Grotesk',sans-serif" }}>
            MY VAULT
          </h1>
          <p style={{ fontSize:11, color:"#A1A1AA", fontWeight:600, letterSpacing:"0.10em", textTransform:"uppercase", marginTop:4 }}>
            {loading ? "LOADING..." : `${items.length} ITEMS`}
          </p>
        </div>
        <input ref={fileRef} type="file" accept="video/*,audio/*,image/*" style={{ display:"none" }}
          onChange={async (e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            setUploading(true);
            try {
              const itemType = f.type.startsWith("audio") ? "sound" : f.type.startsWith("image") ? "meme" : "meme";
              await vault.upload(f, itemType, f.name);
              fetchItems();
            } catch { toast("Upload failed", "error"); }
            setUploading(false);
          }}
        />
        <button onClick={() => fileRef.current?.click()} disabled={uploading}
          style={{ display:"inline-flex", alignItems:"center", gap:6, padding:"0 20px", height:44, border:"none", background: uploading ? "#27272A" : "#DFE104", color: uploading ? "#6B7280" : "#000", fontWeight:700, fontSize:10, letterSpacing:"0.12em", textTransform:"uppercase", cursor: uploading ? "not-allowed" : "pointer" }}>
          {uploading ? <Loader2 size={14} /> : <Upload size={14} />}
          {uploading ? "UPLOADING..." : "ADD TO VAULT"}
        </button>
      </div>

      <div style={{ marginTop:20, border:"2px solid #3F3F46", display:"flex", alignItems:"center", gap:8, padding:"0 12px" }}>
        <Search size={14} color="#6B7280" />
        <input value={q} onChange={e => setQ(e.target.value)} placeholder="SEARCH VAULT..."
          style={{ flex:1, padding:"12px 0", background:"transparent", border:"none", outline:"none", color:"#FAFAFA", fontSize:11, fontWeight:600, letterSpacing:"0.05em" }} />
      </div>

      <Section title="MEMES" icon={<Wand2 size={12} />}>
        {loading ? (
          <p style={{ fontSize:11, color:"#6B7280", padding:"16px 0" }}>LOADING...</p>
        ) : memes.length === 0 ? (
          <p style={{ fontSize:11, color:"#6B7280", padding:"16px 0", letterSpacing:"0.05em" }}>NO MEMES YET</p>
        ) : (
          <div style={{ display:"grid", gridTemplateColumns:"repeat(3, 1fr)", gap:8 }}>
            {memes.map((m) => (
              <div key={m.id}
                style={{ position:"relative", aspectRatio:"1", border:"2px solid #3F3F46", display:"flex", alignItems:"center", justifyContent:"center", overflow:"hidden" }}>
                <Play size={20} style={{ color:"#6B7280", fill:"#6B7280" }} />
                <div style={{ position:"absolute", bottom:0, left:0, right:0, padding:"6px 8px", background:"#09090B", borderTop:"2px solid #3F3F46", fontSize:10, fontWeight:600, color:"#A1A1AA", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                  {m.name}
                </div>
                <button onClick={() => handleDelete(m.id)}
                  style={{ position:"absolute", top:4, right:4, width:28, height:28, display:"flex", alignItems:"center", justifyContent:"center", background:"#27272A", border:"2px solid #3F3F46", color:"#6B7280", cursor:"pointer", opacity:0, transition:"opacity 200ms" }}
                  onMouseEnter={e => (e.currentTarget as HTMLElement).style.opacity="1"}
                  onMouseLeave={e => (e.currentTarget as HTMLElement).style.opacity="0"}
                  className="group-hover:opacity-100"
                >
                  <Trash2 size={10} />
                </button>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="SOUNDS" icon={<Disc3 size={12} />}>
        {loading ? (
          <p style={{ fontSize:11, color:"#6B7280", padding:"16px 0" }}>LOADING...</p>
        ) : sounds.length === 0 ? (
          <p style={{ fontSize:11, color:"#6B7280", padding:"16px 0", letterSpacing:"0.05em" }}>NO SOUNDS YET</p>
        ) : (
          <div style={{ border:"2px solid #3F3F46" }}>
            {sounds.map((s) => (
              <div key={s.id} style={{ display:"flex", alignItems:"center", gap:12, padding:"10px 12px", borderBottom:"1px solid #3F3F46" }}>
                <button style={{ width:32, height:32, display:"flex", alignItems:"center", justifyContent:"center", border:"2px solid #3F3F46", background:"transparent", color:"#DFE104", cursor:"pointer" }}>
                  <Play size={12} fill="#DFE104" />
                </button>
                <span style={{ flex:1, fontSize:12, fontWeight:600, color:"#FAFAFA" }}>{s.name}</span>
                <button onClick={() => handleDelete(s.id)}
                  style={{ width:28, height:28, display:"flex", alignItems:"center", justifyContent:"center", border:"2px solid #3F3F46", background:"transparent", color:"#6B7280", cursor:"pointer", transition:"color 200ms,background 200ms" }}
                  onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background="#ef4444"; (e.currentTarget as HTMLElement).style.color="#fff"; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background="transparent"; (e.currentTarget as HTMLElement).style.color="#6B7280"; }}>
                  <Trash2 size={10} />
                </button>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="MUSIC" icon={<Music size={12} />}>
        {loading ? (
          <p style={{ fontSize:11, color:"#6B7280", padding:"16px 0" }}>LOADING...</p>
        ) : musicItems.length === 0 ? (
          <p style={{ fontSize:11, color:"#6B7280", padding:"16px 0", letterSpacing:"0.05em" }}>NO MUSIC YET</p>
        ) : (
          <div style={{ border:"2px solid #3F3F46" }}>
            {musicItems.map((m) => (
              <div key={m.id} style={{ display:"flex", alignItems:"center", gap:12, padding:"10px 12px", borderBottom:"1px solid #3F3F46" }}>
                <button style={{ width:32, height:32, display:"flex", alignItems:"center", justifyContent:"center", border:"2px solid #3F3F46", background:"transparent", color:"#DFE104", cursor:"pointer" }}>
                  <Play size={12} fill="#DFE104" />
                </button>
                <span style={{ flex:1, fontSize:12, fontWeight:600, color:"#FAFAFA" }}>{m.name}</span>
                <button onClick={() => handleDelete(m.id)}
                  style={{ width:28, height:28, display:"flex", alignItems:"center", justifyContent:"center", border:"2px solid #3F3F46", background:"transparent", color:"#6B7280", cursor:"pointer", transition:"color 200ms,background 200ms" }}
                  onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background="#ef4444"; (e.currentTarget as HTMLElement).style.color="#fff"; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background="transparent"; (e.currentTarget as HTMLElement).style.color="#6B7280"; }}>
                  <Trash2 size={10} />
                </button>
              </div>
            ))}
          </div>
        )}
      </Section>

      {others.length > 0 && (
        <Section title="OTHER ASSETS" icon={<Wand2 size={12} />}>
          <div style={{ display:"flex", flexWrap:"wrap", gap:8 }}>
            {others.map((o) => (
              <div key={o.id} style={{ display:"flex", alignItems:"center", gap:8, padding:"8px 12px", border:"2px solid #3F3F46" }}>
                <span style={{ width:6, height:6, background:"#DFE104" }} />
                <span style={{ fontSize:11, fontWeight:600, color:"#FAFAFA" }}>{o.name}</span>
                <button onClick={() => handleDelete(o.id)} style={{ background:"none", border:"none", color:"#6B7280", cursor:"pointer", padding:2 }}>
                  <Trash2 size={10} />
                </button>
              </div>
            ))}
          </div>
        </Section>
      )}

      {items.length < total && (
        <button onClick={() => fetchItems(false)} disabled={loading}
          style={{ display:"block", margin:"20px auto 0", padding:"10px 32px", background:"transparent", border:"2px solid #3F3F46", color:"#A1A1AA", fontWeight:700, fontSize:10, letterSpacing:"0.12em", textTransform:"uppercase", cursor:loading?"not-allowed":"pointer" }}>
          {loading ? "LOADING..." : `LOAD MORE (${items.length}/${total})`}
        </button>
      )}
    </AppShell>
  );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={{ marginTop:24 }}>
      <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:12 }}>
        <span style={{ color:"#DFE104" }}>{icon}</span>
        <span style={{ fontSize:10, fontWeight:700, letterSpacing:"0.15em", color:"#A1A1AA" }}>{title}</span>
      </div>
      {children}
    </div>
  );
}
