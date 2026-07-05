import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Check, ArrowUpRight, ArrowLeft } from "lucide-react";

export const Route = createFileRoute("/pricing")({ component: PricingPage });

const PLANS = [
  {
    name: "FREE",
    price: "$0",
    desc: "Dip your toes in AI editing",
    features: ["3 edits/month", "720p export", "1 reference video"],
    cta: "GET STARTED",
    popular: false,
  },
  {
    name: "PRO",
    price: "$19",
    desc: "For serious creators",
    features: ["Unlimited edits", "1080p export", "5 reference videos", "Priority queue", "Style profiles"],
    cta: "START FREE TRIAL",
    popular: true,
  },
  {
    name: "ENTERPRISE",
    price: "$49",
    desc: "For teams & studios",
    features: ["Unlimited edits", "4K export", "Unlimited references", "Priority queue", "Team workspace", "API access"],
    cta: "CONTACT SALES",
    popular: false,
  },
];

function PricingPage() {
  const navigate = useNavigate();
  return (
    <div style={{ background:"#09090B", color:"#FAFAFA", fontFamily:"'Space Grotesk',sans-serif", minHeight:"100vh", display:"flex", flexDirection:"column" }}>
      <div style={{ flex:1, display:"flex", flexDirection:"column", justifyContent:"center", padding:"40px", maxWidth:900, margin:"0 auto", width:"100%" }}>
        <button onClick={() => navigate({ to: "/" })}
          style={{ display:"inline-flex", alignItems:"center", gap:6, background:"none", border:"none", color:"#A1A1AA", cursor:"pointer", fontWeight:600, fontSize:12, letterSpacing:"0.10em", textTransform:"uppercase", marginBottom:32, padding:0 }}
          onMouseEnter={e=>e.currentTarget.style.color="#DFE104"}
          onMouseLeave={e=>e.currentTarget.style.color="#A1A1AA"}
        ><ArrowLeft size={14} /> BACK HOME</button>
        <div style={{ textAlign:"center", marginBottom:48 }}>
          <p style={{ fontSize:10, color:"#DFE104", fontWeight:700, letterSpacing:"0.18em", textTransform:"uppercase", marginBottom:8 }}>PRICING</p>
          <h1 style={{ fontSize:"clamp(2.5rem,6vw,5rem)", fontWeight:700, letterSpacing:"-0.03em", textTransform:"uppercase", color:"#FAFAFA", lineHeight:1, fontFamily:"'Space Grotesk',sans-serif" }}>
            SIMPLE<br />PRICING
          </h1>
          <p style={{ fontSize:12, color:"#A1A1AA", marginTop:12 }}>No hidden fees. Upgrade anytime.</p>
        </div>
        <div style={{ display:"grid", gap:16, gridTemplateColumns:"repeat(auto-fit, minmax(240px, 1fr))" }}>
          {PLANS.map((plan) => (
            <div key={plan.name} style={{
              padding:32, position:"relative", textAlign:"center",
              background:"rgba(24,24,27,0.6)", backdropFilter:"blur(20px)", WebkitBackdropFilter:"blur(20px)",
              borderRadius:16,
              boxShadow:"0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)",
              border: plan.popular ? "1px solid rgba(223,225,4,0.3)" : "1px solid rgba(255,255,255,0.06)",
            }}>
              {plan.popular && (
                <span style={{ position:"absolute", top:-12, left:"50%", transform:"translateX(-50%)", background:"#DFE104", color:"#000", padding:"2px 16px", fontSize:9, fontWeight:700, letterSpacing:"0.10em", whiteSpace:"nowrap", borderRadius:100 }}>
                  MOST POPULAR
                </span>
              )}
              <h2 style={{ fontSize:13, fontWeight:700, letterSpacing:"0.15em", color:"#FAFAFA", marginBottom:16, textTransform:"uppercase" }}>{plan.name}</h2>
              <div style={{ display:"flex", alignItems:"baseline", justifyContent:"center", gap:4 }}>
                <span style={{ fontSize:"clamp(2.5rem,4vw,3.5rem)", fontWeight:700, color:"#DFE104", fontFamily:"'Space Grotesk',sans-serif" }}>{plan.price}</span>
                <span style={{ fontSize:11, color:"#6B7280" }}>/month</span>
              </div>
              <p style={{ fontSize:11, color:"#A1A1AA", marginTop:12 }}>{plan.desc}</p>
              <ul style={{ marginTop:24, display:"flex", flexDirection:"column", gap:12, textAlign:"left" }}>
                {plan.features.map((f) => (
                  <li key={f} style={{ display:"flex", alignItems:"center", gap:10, fontSize:12, color:"#D4D4D8" }}>
                    <Check size={14} color="#DFE104" style={{ flexShrink:0 }} /> {f}
                  </li>
                ))}
              </ul>
              <Link to="/" style={{
                display:"flex", alignItems:"center", justifyContent:"center", marginTop:28,
                padding:"14px 0", fontWeight:700, fontSize:11, letterSpacing:"0.12em", textTransform:"uppercase", textDecoration:"none", borderRadius:8,
                background: plan.popular ? "#DFE104" : "transparent",
                color: plan.popular ? "#000" : "#FAFAFA",
                border: plan.popular ? "none" : "2px solid #3F3F46",
              }}>
                {plan.cta} <ArrowUpRight size={14} style={{ marginLeft:6 }} />
              </Link>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
