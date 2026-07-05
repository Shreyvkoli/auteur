import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Wand2, Settings, Bell, CreditCard, LogOut, ChevronRight, Sparkles } from "lucide-react";
import { useState, useEffect } from "react";
import { AppShell } from "@/components/app-shell";
import { auth, edit } from "@/lib/api";
import { toast } from "@/components/editor/Toast";

export const Route = createFileRoute("/profile")({ component: Profile });

function Profile() {
  const navigate = useNavigate();
  const [user, setUser] = useState<{ id: string; email: string; name: string; plan: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [editCount, setEditCount] = useState<number | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("auteur_token");
    if (!token) { setLoading(false); return; }
    auth.me().then((d) => { setUser(d); setLoading(false); }).catch(() => setLoading(false));
    edit.history().then((h: any) => { setEditCount(Array.isArray(h) ? h.length : h?.length ?? null); }).catch(() => {});
  }, []);

  const initials = user?.name?.split(" ").map(s => s[0]).join("").slice(0, 2).toUpperCase() || "?";

  const rows = [
    { to: "/train", icon: Wand2, label: "STYLE TRAINING" },
    { icon: Bell, label: "NOTIFICATIONS", action: () => toast("Notifications coming soon!", "info") },
    { icon: CreditCard, label: "PLAN & BILLING", action: () => window.open("https://auteur.ai/pricing", "_blank") },
    { icon: Settings, label: "SETTINGS", action: () => toast("Settings coming soon!", "info") },
    { icon: LogOut, label: "SIGN OUT", danger: true, action: async () => {
      try { await auth.signout(); } catch {}
      localStorage.removeItem("auteur_token");
      navigate({ to: "/" });
    }},
  ];

  return (
    <AppShell>
      <h1 style={{ fontSize:"clamp(1.5rem,4vw,2.5rem)", fontWeight:700, letterSpacing:"-0.02em", textTransform:"uppercase", color:"#FAFAFA", fontFamily:"'Space Grotesk',sans-serif" }}>
        PROFILE
      </h1>

      {loading ? (
        <p style={{ marginTop:24, fontSize:12, color:"#6B7280" }}>LOADING...</p>
      ) : !user ? (
        <div style={{ marginTop:24, textAlign:"center", padding:"40px 0", border:"2px solid #3F3F46" }}>
          <p style={{ fontSize:12, color:"#A1A1AA", fontWeight:600, letterSpacing:"0.08em", textTransform:"uppercase" }}>NOT SIGNED IN</p>
          <Link to="/" style={{ display:"inline-block", marginTop:16, padding:"10px 24px", background:"#DFE104", color:"#000", fontWeight:700, fontSize:10, letterSpacing:"0.12em", textTransform:"uppercase", textDecoration:"none" }}>
            SIGN IN
          </Link>
        </div>
      ) : (
        <>
          <div style={{ marginTop:24, border:"2px solid #3F3F46", padding:20 }}>
            <div style={{ display:"flex", alignItems:"center", gap:16 }}>
              <div style={{ width:48, height:48, display:"flex", alignItems:"center", justifyContent:"center", background:"#DFE104", color:"#000", fontWeight:700, fontSize:16 }}>
                {initials}
              </div>
              <div>
                <p style={{ fontWeight:700, fontSize:15, color:"#FAFAFA", letterSpacing:"-0.01em" }}>{user.name}</p>
                <p style={{ fontSize:11, color:"#A1A1AA", marginTop:2 }}>{user.email}</p>
                <span style={{ display:"inline-flex", alignItems:"center", gap:4, marginTop:8, background:"#DFE104", color:"#000", padding:"2px 10px", fontSize:9, fontWeight:700, letterSpacing:"0.08em" }}>
                  <Sparkles size={10} /> {user.plan || "FREE"}
                </span>
              </div>
            </div>
          </div>

          <div style={{ marginTop:16, display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:8 }}>
            {[
              { label: "EDITS", v: editCount !== null ? String(editCount) : "—" },
              { label: "STYLE", v: "READY" },
              { label: "PLAN", v: user.plan || "FREE" },
            ].map((s) => (
              <div key={s.label} style={{ border:"2px solid #3F3F46", padding:16, textAlign:"center" }}>
                <p style={{ fontSize:"clamp(1.2rem,3vw,1.8rem)", fontWeight:700, color:"#DFE104" }}>{s.v}</p>
                <p style={{ fontSize:9, color:"#A1A1AA", fontWeight:700, letterSpacing:"0.12em", textTransform:"uppercase", marginTop:4 }}>{s.label}</p>
              </div>
            ))}
          </div>

          <div style={{ marginTop:20, border:"2px solid #3F3F46" }}>
            {rows.map((r) => {
              const Icon = r.icon;
              const inner = (
                <div style={{ display:"flex", alignItems:"center", gap:12, padding:"12px 16px" }}>
                  <div style={{ width:36, height:36, display:"flex", alignItems:"center", justifyContent:"center", border:"2px solid #3F3F46", color: r.danger ? "#ef4444" : "#DFE104" }}>
                    <Icon size={14} />
                  </div>
                  <span style={{ flex:1, fontSize:11, fontWeight:700, letterSpacing:"0.05em", color: r.danger ? "#ef4444" : "#FAFAFA" }}>
                    {r.label}
                  </span>
                  <ChevronRight size={14} color="#6B7280" />
                </div>
              );
              if (r.action) {
                return (
                  <button key={r.label} onClick={r.action}
                    style={{ width:"100%", background:"transparent", border:"none", borderBottom:"1px solid #3F3F46", cursor:"pointer", padding:0, textAlign:"left" }}>
                    {inner}
                  </button>
                );
              }
              return r.to ? (
                <Link key={r.label} to={r.to as never}
                  style={{ display:"block", textDecoration:"none", borderBottom:"1px solid #3F3F46" }}>
                  {inner}
                </Link>
              ) : (
                <button key={r.label}
                  style={{ width:"100%", background:"transparent", border:"none", borderBottom:"1px solid #3F3F46", cursor:"pointer", padding:0, textAlign:"left" }}>
                  {inner}
                </button>
              );
            })}
          </div>
        </>
      )}
    </AppShell>
  );
}
