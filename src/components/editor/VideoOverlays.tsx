import { useState, useEffect, useRef } from "react";

export function VideoOverlays({ videoRef, overlays, captions, currentTime }: {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  overlays: any[];
  captions: any[];
  currentTime: number;
}) {
  const [vRect, setVRect] = useState({ w: 0, h: 0, l: 0, t: 0 });
  const parentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const measure = () => {
      const v = videoRef.current;
      const p = parentRef.current;
      if (!v || !p) return;
      const vr = v.getBoundingClientRect();
      const pr = p.getBoundingClientRect();
      setVRect({ w: vr.width, h: vr.height, l: vr.left - pr.left, t: vr.top - pr.top });
    };
    measure();
    window.addEventListener("resize", measure);
    const obs = new ResizeObserver(measure);
    if (parentRef.current) obs.observe(parentRef.current);
    return () => { window.removeEventListener("resize", measure); obs.disconnect(); };
  }, [videoRef]);

  const items = [
    ...overlays.filter((o: any) => o.type === "text" && o.text),
    ...captions.filter((c: any) => c.text),
  ].filter((o: any) => currentTime >= o.start && currentTime < o.end);

  return (
    <div ref={parentRef} style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
      {items.map((o: any) => {
        const s = o.style || {};
        const x = (o.x ?? 0.5) * vRect.w + vRect.l;
        const y = (o.y ?? 0.5) * vRect.h + vRect.t;
        return (
          <div key={o.id}
            style={{
              position: "absolute",
              left: x,
              top: y,
              transform: "translate(-50%, -50%)",
              color: s.color || "#fff",
              fontSize: s.font_size_px || s.fontSize || 48,
              fontWeight: s.font_weight || s.fontWeight || 700,
              fontFamily: s.font_family || s.fontFamily || "Space Grotesk, sans-serif",
              textAlign: "center",
              textShadow: "0 2px 8px rgba(0,0,0,0.8)",
              whiteSpace: "pre-wrap",
              lineHeight: 1.2,
              maxWidth: `${vRect.w * 0.8}px`,
            }}
          >{o.text}</div>
        );
      })}
    </div>
  );
}
