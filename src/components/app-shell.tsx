import { Link, useRouterState, useNavigate } from "@tanstack/react-router";
import { Home, CreditCard, Library, FolderOpen, User, LogIn } from "lucide-react";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { auth } from "@/lib/api";

const navItems = [
  { to: "/", label: "Home", icon: Home },
  { to: "/pricing", label: "Pricing", icon: CreditCard },
  { to: "/vault", label: "Vault", icon: Library },
  { to: "/projects", label: "Projects", icon: FolderOpen },
  { to: "/profile", label: "Profile", icon: User },
] as const;

function AuthModal({
  open,
  onClose,
  onLogin,
}: {
  open: boolean;
  onClose: () => void;
  onLogin: () => void;
}) {
  const [tab, setTab] = useState<"login" | "register">("login");
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
      const res =
        tab === "login"
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
        <form onSubmit={handleSubmit} style={{ display:"flex", flexDirection:"column", gap:16, padding:24 }}>
          {tab === "register" && (
            <div>
              <label style={{ fontSize:10, color:"#FAFAFA", letterSpacing:"0.12em", textTransform:"uppercase", display:"block", marginBottom:6, fontWeight:600 }}>NAME</label>
              <input value={name} onChange={e => setName(e.target.value)} placeholder="Your name" required
                style={{ width:"100%", padding:"12px", background:"transparent", borderBottom:"2px solid #3F3F46", color:"#FAFAFA", fontSize:13, outline:"none", fontWeight:500 }} />
            </div>
          )}
          <div>
            <label style={{ fontSize:10, color:"#FAFAFA", letterSpacing:"0.12em", textTransform:"uppercase", display:"block", marginBottom:6, fontWeight:600 }}>EMAIL</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required
              style={{ width:"100%", padding:"12px", background:"transparent", borderBottom:"2px solid #3F3F46", color:"#FAFAFA", fontSize:13, outline:"none", fontWeight:500 }} />
          </div>
          <div>
            <label style={{ fontSize:10, color:"#FAFAFA", letterSpacing:"0.12em", textTransform:"uppercase", display:"block", marginBottom:6, fontWeight:600 }}>PASSWORD</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" required minLength={6}
              style={{ width:"100%", padding:"12px", background:"transparent", borderBottom:"2px solid #3F3F46", color:"#FAFAFA", fontSize:13, outline:"none", fontWeight:500 }} />
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

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const navigate = useNavigate();
  const [authOpen, setAuthOpen] = useState(false);
  const [loggedIn, setLoggedIn] = useState(() => !!localStorage.getItem("auteur_token"));
  const token = typeof window !== "undefined" ? localStorage.getItem("auteur_token") : null;
  return (
    <div className="flex min-h-dvh w-full flex-col bg-[#09090B] overflow-x-hidden">
      <AuthModal
        open={authOpen}
        onClose={() => setAuthOpen(false)}
        onLogin={() => setLoggedIn(true)}
      />
      <main className="flex-1 px-5 pt-8 pb-36 md:px-10 lg:px-16">{children}</main>
      <nav className="fixed inset-x-0 bottom-0 z-50 px-4 pb-4">
        <div className="flex items-center justify-around rounded-none border-2 border-[#3F3F46] bg-[#09090B] px-3 py-3">
          {navItems.map(({ to, label, icon: Icon }) => {
            const active = to === "/" ? pathname === "/" : pathname.startsWith(to);
            return (
              <Link
                key={to}
                to={to}
                className={cn(
                  "flex flex-1 flex-col items-center gap-0.5 rounded-none py-2 text-[10px] font-bold uppercase tracking-widest transition-all duration-300 ease-out",
                  active ? "text-[#DFE104]" : "text-[#6B7280] hover:text-[#A1A1AA]",
                )}
              >
                <span
                  className={cn(
                    "grid h-10 w-10 place-items-center rounded-none transition-all duration-300 ease-out",
                    active
                      ? "bg-[#DFE104] text-black"
                      : "bg-[#09090B] text-[#6B7280] border-2 border-[#3F3F46]",
                  )}
                >
                  <Icon className="h-4 w-4" />
                </span>
                <span className={cn(active && "font-bold")}>{label}</span>
              </Link>
            );
          })}
          {!token && !loggedIn ? (
            <button
              onClick={() => setAuthOpen(true)}
              className="flex flex-1 flex-col items-center gap-0.5 rounded-none py-2 text-[10px] font-bold uppercase tracking-widest transition-all duration-300 ease-out text-[#6B7280] hover:text-[#A1A1AA]"
            >
              <span className="grid h-10 w-10 place-items-center rounded-none bg-[#09090B] text-[#6B7280] border-2 border-[#3F3F46]">
                <LogIn className="h-4 w-4" />
              </span>
              <span>Login</span>
            </button>
          ) : (
            <button
              onClick={async () => {
                try {
                  await auth.signout();
                } catch {}
                localStorage.removeItem("auteur_token");
                setLoggedIn(false);
              }}
              className="flex flex-1 flex-col items-center gap-0.5 rounded-none py-2 text-[10px] font-bold uppercase tracking-widest transition-all duration-300 ease-out text-[#6B7280] hover:text-[#A1A1AA]"
            >
              <span className="grid h-10 w-10 place-items-center rounded-none bg-[#09090B] text-[#6B7280] border-2 border-[#3F3F46]">
                <LogIn className="h-4 w-4" />
              </span>
              <span>Logout</span>
            </button>
          )}
        </div>
      </nav>
    </div>
  );
}
