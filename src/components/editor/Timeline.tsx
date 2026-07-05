import { useRef, useCallback, useState, useEffect } from "react";
import { ZoomIn, ZoomOut, Scissors, Trash2, Copy, Volume2, Ruler, Magnet } from "lucide-react";
import type { EditState } from "@/lib/api";
import { BASE } from "@/lib/api";

const TRACKS = [
  { key: "video", label: "Video", color: "#2563eb", h: 40 },
  { key: "text", label: "Text", color: "#10b981", h: 28 },
  { key: "overlays", label: "Overlays", color: "#ec4899", h: 28 },
  { key: "captions", label: "Captions", color: "#f59e0b", h: 24 },
  { key: "audio", label: "Audio", color: "#8b5cf6", h: 30 },
  { key: "effects", label: "Effects", color: "#ef4444", h: 22 },
];

const RULER_HEIGHT = 24;
const LABEL_WIDTH = 56;
const HANDLE_W = 6;
const SNAP_THRESHOLD = 8;

interface TimelineProps {
  state: EditState;
  currentTime: number;
  duration: number;
  selectedClipId: string | null;
  onSelectClip: (id: string | null) => void;
  onSeek: (time: number) => void;
  onAction?: (actions: any[]) => Promise<void>;
}

export function Timeline({
  state,
  currentTime,
  duration,
  selectedClipId,
  onSelectClip,
  onSeek,
  onAction,
}: TimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [thumbnails, setThumbnails] = useState<string[]>([]);
  const [thumbInterval, setThumbInterval] = useState(2);

  /* Fetch thumbnails for video */
  useEffect(() => {
    const vid = state?.video_id;
    if (!vid) return;
    let cancelled = false;
    fetch(`${BASE}/video/${vid}/thumbnails`)
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled && data.thumbnails) {
          setThumbnails(data.thumbnails);
          setThumbInterval(data.interval || 2);
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [state?.video_id]);
  const [draggingPlayhead, setDraggingPlayhead] = useState(false);
  const [rippleEnabled, setRippleEnabled] = useState(false);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    clipId: string;
    trackKey: string;
    item: any;
  } | null>(null);
  const [dragAudioVol, setDragAudioVol] = useState<{
    trackId: string;
    startY: number;
    origVol: number;
  } | null>(null);

  const [dragTrim, setDragTrim] = useState<{
    clipId: string;
    edge: "left" | "right";
    startX: number;
    origStart: number;
    origEnd: number;
    sourceStart: number;
    sourceEnd: number;
  } | null>(null);
  const [dragReorder, setDragReorder] = useState<{
    clipId: string;
    index: number;
    startX: number;
    origStart: number;
    trackKey: string;
  } | null>(null);
  const [dragOffset, setDragOffset] = useState(0);

  const totalWidth = Math.max(800, duration * 40 * zoom);
  const timeToX = (t: number) => (t / duration) * totalWidth;
  const xToTime = (x: number) => Math.max(0, Math.min(duration, (x / totalWidth) * duration));

  const snapTime = (t: number, skipId?: string): number => {
    if (!rippleEnabled) return t;
    const snapPoints: number[] = [0, duration];
    const allIds = new Set<string>();
    state?.timeline?.forEach((s) => {
      if (s.id !== skipId) {
        snapPoints.push(s.timeline_start, s.timeline_end);
      }
    });
    state?.captions?.forEach((c) => {
      if (c.id !== skipId) {
        snapPoints.push(c.start, c.end);
      }
    });
    state?.overlays?.forEach((o) => {
      if (o.id !== skipId) {
        snapPoints.push(o.start, o.end);
      }
    });
    state?.audio_tracks?.forEach((a) => {
      if (a.id !== skipId) {
        snapPoints.push(a.start, a.start + a.duration);
      }
    });
    for (const pt of snapPoints) {
      if (Math.abs(t - pt) * (totalWidth / duration) < SNAP_THRESHOLD) return pt;
    }
    return t;
  };

  /* Context menu close */
  useEffect(() => {
    if (!contextMenu) return;
    const close = () => setContextMenu(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [contextMenu]);

  /* Ctrl+Wheel zoom */
  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    setZoom((z) => Math.max(0.25, Math.min(4, z - e.deltaY * 0.003)));
  }, []);

  /* Audio volume drag */
  const handleAudioVolDown = useCallback((e: React.MouseEvent, trackId: string, vol: number) => {
    e.stopPropagation();
    setDragAudioVol({ trackId, startY: e.clientY, origVol: vol });
  }, []);

  useEffect(() => {
    if (!dragAudioVol) return;
    const handleMove = (e: MouseEvent) => {
      const dy = (dragAudioVol.startY - e.clientY) * 0.005;
      const newVol = Math.max(0, Math.min(1, dragAudioVol.origVol + dy));
      onAction?.([{ action: "audio_edit", track_id: dragAudioVol.trackId, volume: newVol }]);
    };
    const handleUp = () => setDragAudioVol(null);
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [dragAudioVol, onAction]);

  /* Ruler interactions */
  const handleRulerMouseDown = useCallback(
    (e: React.MouseEvent) => {
      setDraggingPlayhead(true);
      const rect = (e.currentTarget.parentElement as HTMLElement).getBoundingClientRect();
      const x = e.clientX - rect.left - LABEL_WIDTH;
      onSeek(xToTime(x));
    },
    [duration, totalWidth, onSeek],
  );

  useEffect(() => {
    if (!draggingPlayhead) return;
    const handleMove = (e: MouseEvent) => {
      const container = containerRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left - LABEL_WIDTH + container.scrollLeft;
      onSeek(xToTime(x));
    };
    const handleUp = () => setDraggingPlayhead(false);
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [draggingPlayhead, duration, totalWidth, onSeek]);

  /* Trim drag */
  const handleTrimStart = useCallback((e: React.MouseEvent, item: any, edge: "left" | "right") => {
    e.stopPropagation();
    setDragTrim({
      clipId: item.id,
      edge,
      startX: e.clientX,
      origStart: item.start,
      origEnd: item.end,
      sourceStart: item.sourceStart,
      sourceEnd: item.sourceEnd,
    });
  }, []);

  useEffect(() => {
    if (!dragTrim) return;
    const handleMove = (e: MouseEvent) => {
      const dx = xToTime(e.clientX - dragTrim.startX) - xToTime(0);
      const newStart = Math.max(0, dragTrim.sourceStart + (dragTrim.edge === "left" ? dx : 0));
      const newEnd = dragTrim.sourceEnd + (dragTrim.edge === "right" ? dx : 0);
      if (newStart < newEnd)
        onAction?.([{ action: "trim", clip_id: dragTrim.clipId, start: newStart, end: newEnd }]);
    };
    const handleUp = (e: MouseEvent) => {
      const dx = xToTime(e.clientX - dragTrim.startX) - xToTime(0);
      const newStart = Math.max(0, dragTrim.sourceStart + (dragTrim.edge === "left" ? dx : 0));
      const newEnd = dragTrim.sourceEnd + (dragTrim.edge === "right" ? dx : 0);
      if (newEnd - newStart > 0.5 && newStart >= 0 && newEnd <= 1e6) {
        onAction?.([{ action: "trim", clip_id: dragTrim.clipId, start: newStart, end: newEnd }]);
      }
      setDragTrim(null);
    };
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [dragTrim, onAction, xToTime, timeToX]);

  /* Reorder drag */
  const handleReorderStart = useCallback((e: React.MouseEvent, item: any, index: number, trackKey: string) => {
    setDragOffset(0);
    setDragReorder({ clipId: item.id, index, startX: e.clientX, origStart: item.start, trackKey });
  }, []);

  useEffect(() => {
    if (!dragReorder) return;
    const handleMove = (e: MouseEvent) => {
      setDragOffset(e.clientX - dragReorder.startX);
    };
    const handleUp = (e: MouseEvent) => {
      const dx = e.clientX - dragReorder.startX;
      const dt = xToTime(timeToX(0) + dx) - xToTime(0);
      if (Math.abs(dt) > 0.1) {
        const snapped = snapTime(Math.max(0, dragReorder.origStart + dt), dragReorder.clipId);
        let action: any;
        if (dragReorder.trackKey === "video") {
          action = { action: "move_clip", clip_id: dragReorder.clipId, new_start: snapped };
        } else if (dragReorder.trackKey === "audio") {
          action = { action: "audio_edit", track_id: dragReorder.clipId, start: snapped };
        } else if (dragReorder.trackKey === "captions") {
          const cap = state?.captions?.find((c) => c.id === dragReorder.clipId);
          if (cap) {
            const dur = cap.end - cap.start;
            action = { action: "update_caption", caption_id: dragReorder.clipId, start: snapped, end: snapped + dur };
          }
        } else if (dragReorder.trackKey === "text") {
          const inCaptions = state?.captions?.find((c) => c.id === dragReorder.clipId);
          if (inCaptions) {
            const dur = inCaptions.end - inCaptions.start;
            action = { action: "update_caption", caption_id: dragReorder.clipId, start: snapped, end: snapped + dur };
          } else {
            const ov = state?.overlays?.find((o) => o.id === dragReorder.clipId);
            if (ov) {
              const dur = ov.end - ov.start;
              action = { action: "update_text_overlay", overlay_id: dragReorder.clipId, start: snapped, end: snapped + dur };
            }
          }
        }
        if (action) onAction?.([action]);
      }
      setDragReorder(null);
      setDragOffset(0);
    };
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [dragReorder, state, onAction, duration, zoom, rippleEnabled]);

  const rulerTicks = [];
  const step = zoom >= 2 ? 1 : zoom >= 1 ? 2 : 5;
  for (let t = 0; t <= duration; t += step) {
    rulerTicks.push(t);
  }

  const segments = state?.timeline || [];
  const textOverlays = [
    ...(state?.overlays || []).filter((o) => o.type === "text"),
    ...(state?.captions || []).map((c) => ({ ...c, type: "text" })),
  ];
  const imageOverlays = (state?.overlays || []).filter((o) => o.type !== "text");
  const captions = state?.captions || [];
  const audioTracks = state?.audio_tracks || [];
  const effects = state?.effects?.transitions || [];
  const blurFx = state?.effects?.blur_effects || [];
  const shakeFx = state?.effects?.shake_effects || [];

  const getTrackItems = (trackKey: string) => {
    switch (trackKey) {
      case "video":
        return segments.map((s) => ({
          id: s.id,
          clipId: s.clip_id,
          start: s.timeline_start,
          end: s.timeline_end,
          sourceStart: s.source_start,
          sourceEnd: s.source_end,
          label: `${s.speed !== 1 ? `${s.speed}x ` : ""}${s.reversed ? "REV " : ""}${s.source_start.toFixed(1)}-${s.source_end.toFixed(1)}`,
          color: "#2563eb",
          speed: s.speed,
          type: "video",
        }));
      case "text":
        return textOverlays.map((o) => ({
          id: o.id,
          clipId: o.id,
          start: o.start,
          end: o.end,
          label: o.text?.slice(0, 20) || "Text",
          color: "#10b981",
          type: "text",
        }));
      case "overlays":
        return imageOverlays.map((o) => ({
          id: o.id,
          clipId: o.id,
          start: o.start,
          end: o.end,
          label: o.name || o.type,
          color: "#ec4899",
          type: "overlay",
        }));
      case "captions":
        return captions.map((c) => ({
          id: c.id,
          clipId: c.id,
          start: c.start,
          end: c.end,
          label: c.text?.slice(0, 20) || "Caption",
          color: "#f59e0b",
          type: "caption",
        }));
      case "audio":
        return audioTracks.map((t) => {
          const bars = Array.from(
            { length: Math.max(8, Math.floor((t.duration || 10) / 2)) },
            (_, i) => ({
              h: Math.max(3, Math.sin(i * 1.5 + (t.volume || 0.5) * 3) * 0.5 + 0.5) * 16,
              key: i,
            }),
          );
          return {
            id: t.id,
            clipId: t.id,
            start: t.start,
            end: t.start + t.duration,
            label: `${t.name || t.type} vol:${Math.round(t.volume * 100)}%`,
            color: "#8b5cf6",
            bars,
            volume: t.volume,
            fade_in: t.fade_in || 0,
            fade_out: t.fade_out || 0,
            type: "audio",
          };
        });
      case "effects": {
        const items: any[] = [];
        effects.forEach((e) => {
          if (e.between)
            items.push({
              id: e.id,
              clipId: e.id,
              start: 0,
              end: 0,
              label: e.transition,
              color: "#ef4444",
              type: "effect",
            });
        });
        blurFx.forEach((b) =>
          items.push({
            id: b.id,
            clipId: b.id,
            start: b.start,
            end: b.end,
            label: `Blur ${b.blur_type}`,
            color: "#ef4444",
            type: "effect",
          }),
        );
        shakeFx.forEach((s) =>
          items.push({
            id: s.id,
            clipId: s.id,
            start: s.start,
            end: s.end,
            label: "Shake",
            color: "#ef4444",
            type: "effect",
          }),
        );
        return items;
      }
      default:
        return [];
    }
  };

  const font = "'Space Grotesk',sans-serif";
  const dim = (_a?: number) => "#FAFAFA";

  return (
    <div
      ref={containerRef}
      style={{
        height: "100%",
        background: "#0d0d0f",
        borderTop: "1px solid rgba(255,255,255,0.05)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Toolbar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 12px",
          height: 32,
          borderBottom: "1px solid rgba(255,255,255,0.04)",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          {TRACKS.map(({ label, color }) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <div
                style={{ width: 8, height: 8, background: color, opacity: 0.9, borderRadius: 1 }}
              />
              <span style={{ fontSize: 12, color: dim(0.6), fontFamily: font }}>{label}</span>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <button
            onClick={() => {
              if (!state || !onAction) return;
              const seg = state.timeline?.find(
                (s) => currentTime >= s.timeline_start && currentTime < s.timeline_end
              );
              if (seg) {
                const at = seg.source_start + (currentTime - seg.timeline_start) * (seg.speed || 1);
                onAction([{ action: "split", clip_id: seg.clip_id, at }]);
              }
            }}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "4px 8px",
              color: "#fbbf24",
              fontSize: 12,
              fontWeight: 700,
              fontFamily: "monospace",
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
            title="Split at playhead (S)"
          >
            <Scissors size={13} /> Split
          </button>

          <div style={{ width: 1, height: 16, background: "rgba(255,255,255,0.06)", margin: "0 4px" }} />

          <button
            onClick={() => setRippleEnabled((r) => !r)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: 4,
              color: rippleEnabled ? "#60a5fa" : dim(0.4),
              display: "flex",
              alignItems: "center",
              gap: 3,
              fontSize: 11,
              fontFamily: "monospace",
            }}
            title="Toggle snapping"
          >
            <Magnet size={12} /> Snap
          </button>

          <div style={{ width: 1, height: 16, background: "rgba(255,255,255,0.06)", margin: "0 4px" }} />

          <ZoomOut size={12} style={{ color: dim(0.4) }} />
          <input
            type="range"
            min="25"
            max="400"
            value={Math.round(zoom * 100)}
            onChange={(e) => setZoom(parseInt(e.target.value) / 100)}
            style={{
              width: 80,
              height: 4,
              accentColor: "#60a5fa",
              cursor: "pointer",
            }}
          />
          <ZoomIn size={12} style={{ color: dim(0.4) }} />
          <span
            style={{
              fontSize: 11,
              fontFamily: "monospace",
              color: dim(0.55),
              width: 36,
              textAlign: "center",
            }}
          >
            {Math.round(zoom * 100)}%
          </span>
        </div>
      </div>

      {/* Tracks area */}
      <div
        ref={scrollRef}
        style={{ position: "relative", overflowX: "auto", overflowY: "hidden", flex: 1 }}
        onWheel={handleWheel}
      >
        <div
          style={{
            display: "flex",
            height: RULER_HEIGHT,
            alignItems: "flex-end",
            paddingLeft: LABEL_WIDTH,
            borderBottom: "1px solid rgba(255,255,255,0.04)",
            cursor: "pointer",
            userSelect: "none",
            position: "relative",
          }}
          onMouseDown={handleRulerMouseDown}
        >
          <div style={{ width: totalWidth, position: "relative", height: "100%" }}>
            {rulerTicks.map((t) => (
              <div key={t} style={{ position: "absolute", left: timeToX(t), bottom: 0 }}>
                <span
                  style={{
                    position: "absolute",
                    bottom: 4,
                    left: -8,
                    fontSize: 12,
                    fontFamily: "monospace",
                    color: dim(0.5),
                    whiteSpace: "nowrap",
                  }}
                >
                  {t}s
                </span>
                <div
                  style={{
                    position: "absolute",
                    bottom: 0,
                    left: 0,
                    width: 1,
                    height: 6,
                    background: "rgba(255,255,255,0.08)",
                  }}
                />
              </div>
            ))}
          </div>
        </div>

        <div style={{ position: "relative", minWidth: totalWidth + LABEL_WIDTH }}>
          {TRACKS.map(({ key, label, color, h }) => (
            <div
              key={key}
              style={{
                display: "flex",
                alignItems: "center",
                height: h + 12,
                borderBottom: "1px solid rgba(255,255,255,0.03)",
              }}
            >
              <div style={{ width: LABEL_WIDTH, flexShrink: 0, paddingLeft: 12 }}>
                <span style={{ fontSize: 11, color: dim(0.5), fontFamily: font }}>{label}</span>
              </div>
              <div style={{ position: "relative", flex: 1, height: h + 12 }}>
                {getTrackItems(key).map((item: any, idx: number) => {
                  const left = timeToX(item.start);
                  const width = Math.max(timeToX(item.end) - left, 4);
                  const isSelected = selectedClipId === item.id;
                  const isVideo = key === "video";
                  const isAudio = key === "audio";
                  const isDragging =
                    dragReorder?.clipId === item.id || dragTrim?.clipId === item.id;
                  const effectiveLeft = dragReorder?.clipId === item.id ? left + dragOffset : left;
                  return (
                    <div key={item.id}>
                      {/* Clip bar */}
                      <div
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectClip(isSelected ? null : item.id);
                        }}
                        onMouseDown={(e) => handleReorderStart(e, item, idx, key)}
                        onContextMenu={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setContextMenu({ x: e.clientX, y: e.clientY, clipId: item.id, trackKey: key, item });
                        }}
                        style={{
                          position: "absolute",
                          top: 4,
                          bottom: 4,
                          left: effectiveLeft,
                          width,
                          background: `${color}${isSelected ? "35" : "25"}`,
                          borderLeft: `2px solid ${color}`,
                          borderTop: `1px solid ${color}44`,
                          borderBottom: `1px solid ${color}44`,
                          borderRadius: "0 3px 3px 0",
                          cursor: "grab",
                          opacity: isDragging ? 0.5 : 1,
                          boxShadow: isSelected
                            ? `inset 0 0 0 1.5px ${color}aa, 0 0 8px ${color}33`
                            : "none",
                          overflow: "hidden",
                          transition: "filter 120ms, box-shadow 120ms",
                          zIndex: isSelected ? 5 : 1,
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(1.4)")}
                        onMouseLeave={(e) => (e.currentTarget.style.filter = "brightness(1)")}
                      >
                        {item.bars ? (
                          <div
                            style={{
                              display: "flex",
                              alignItems: "flex-end",
                              gap: 1,
                              height: "100%",
                              padding: "2px 4px",
                              position: "relative",
                            }}
                          >
                            {item.bars.map((b: any) => (
                              <div
                                key={b.key}
                                style={{
                                  width: 2,
                                  height: `${Math.min(100, b.h)}px`,
                                  background: `${color}88`,
                                  borderRadius: "1px 1px 0 0",
                                }}
                              />
                            ))}
                            {/* Volume overlay on hover */}
                            <div
                              onMouseDown={(e) => handleAudioVolDown(e, item.id, item.volume)}
                              style={{
                                position: "absolute",
                                right: 4,
                                top: 2,
                                padding: "1px 4px",
                                background: "rgba(0,0,0,0.5)",
                                borderRadius: 3,
                                cursor: "ns-resize",
                                fontSize: 10,
                                color: dim(0.7),
                                display: "flex",
                                alignItems: "center",
                                gap: 3,
                                opacity: 0.8,
                              }}
                              title="Drag up/down to adjust volume"
                            >
                              <Volume2 size={9} />
                              {Math.round(item.volume * 100)}%
                            </div>
                            {/* Fade in handle */}
                            {item.fade_in > 0 && (
                              <div
                                style={{
                                  position: "absolute",
                                  left: 0,
                                  top: 0,
                                  bottom: 0,
                                  width: timeToX(item.fade_in) - timeToX(0),
                                  background: `linear-gradient(to right, ${color}55, transparent)`,
                                  pointerEvents: "none",
                                }}
                              />
                            )}
                            {/* Fade out handle */}
                            {item.fade_out > 0 && (
                              <div
                                style={{
                                  position: "absolute",
                                  right: 0,
                                  top: 0,
                                  bottom: 0,
                                  width: timeToX(item.fade_out) - timeToX(0),
                                  background: `linear-gradient(to left, ${color}55, transparent)`,
                                  pointerEvents: "none",
                                }}
                              />
                            )}
                          </div>
                        ) : isVideo && thumbnails.length > 0 && item.sourceStart != null ? (
                          <div style={{ position: "relative", height: "100%", overflow: "hidden" }}>
                            {(() => {
                              const iv = thumbInterval || 2;
                              const sp = item.speed || 1;
                              const imgs: any[] = [];
                              for (let i = 0; i < thumbnails.length; i++) {
                                const srcT = i * iv;
                                if (srcT < item.sourceStart) continue;
                                if (srcT > item.sourceEnd) break;
                                const tlPos = item.start + (srcT - item.sourceStart) / sp;
                                const rel = timeToX(tlPos) - timeToX(item.start);
                                if (rel > width) break;
                                imgs.push(
                                  <img
                                    key={i}
                                    src={thumbnails[i]}
                                    alt=""
                                    style={{
                                      position: "absolute",
                                      left: rel,
                                      top: 0,
                                      height: "100%",
                                      width: "auto",
                                      objectFit: "cover",
                                      opacity: 0.85,
                                      pointerEvents: "none",
                                    }}
                                  />
                                );
                              }
                              return imgs;
                            })()}
                            <span
                              style={{
                                position: "absolute",
                                left: 4,
                                bottom: 2,
                                zIndex: 2,
                                fontSize: 11,
                                padding: "1px 4px",
                                color: "#fff",
                                fontWeight: 700,
                                whiteSpace: "nowrap",
                                textShadow: "0 1px 4px rgba(0,0,0,0.9)",
                                background: "rgba(0,0,0,0.4)",
                                borderRadius: 2,
                              }}
                            >
                              {item.label}
                            </span>
                          </div>
                        ) : (
                          <span
                            style={{
                              fontSize: 11,
                              padding: "0 6px",
                              color: `${color}dd`,
                              fontWeight: 600,
                              whiteSpace: "nowrap",
                              lineHeight: `${h}px`,
                            }}
                          >
                            {item.label}
                          </span>
                        )}
                      </div>
                      {/* Trim handles (video track only) */}
                      {isVideo && width > 20 && (
                        <>
                          <div
                            onMouseDown={(e) => handleTrimStart(e, item, "left")}
                            style={{
                              position: "absolute",
                              top: 4,
                              bottom: 4,
                              left: left - HANDLE_W / 2,
                              width: HANDLE_W,
                              cursor: "ew-resize",
                              zIndex: 10,
                            }}
                          />
                          <div
                            onMouseDown={(e) => handleTrimStart(e, item, "right")}
                            style={{
                              position: "absolute",
                              top: 4,
                              bottom: 4,
                              left: left + width - HANDLE_W / 2,
                              width: HANDLE_W,
                              cursor: "ew-resize",
                              zIndex: 10,
                            }}
                          />
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          {/* Playhead */}
          <div
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              left: LABEL_WIDTH + timeToX(currentTime),
              width: 1.5,
              background: "#ef4444",
              pointerEvents: "none",
              boxShadow: "0 0 8px rgba(239,68,68,0.6)",
              zIndex: 20,
            }}
          >
            <div
              style={{
                position: "absolute",
                top: -2,
                left: "50%",
                transform: "translateX(-50%) rotate(45deg)",
                width: 7,
                height: 7,
                background: "#ef4444",
              }}
            />
          </div>
        </div>
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <div
          style={{
            position: "fixed",
            left: contextMenu.x,
            top: contextMenu.y,
            zIndex: 999,
            background: "#1a1a1e",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 6,
            padding: "4px 0",
            minWidth: 160,
            boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
          }}
        >
          {[
            { label: "Delete", icon: Trash2, color: "#ef4444", action: "delete" },
            { label: "Duplicate", icon: Copy, color: "#60a5fa", action: "duplicate" },
            ...(contextMenu.trackKey === "video"
              ? [{ label: "Split here", icon: Scissors, color: "#fbbf24", action: "split" as const }]
              : []),
          ].map(({ label, icon: Icon, color, action }) => (
            <button
              key={action}
              onClick={() => {
                if (action === "delete") {
                  onAction?.([{ action: "delete", clip_id: contextMenu.clipId }]);
                  onSelectClip(null);
                } else if (action === "duplicate") {
                  onAction?.([{ action: "duplicate", clip_id: contextMenu.item.clipId || contextMenu.clipId, count: 1 }]);
                } else if (action === "split") {
                  const seg = state?.timeline?.find((s) => s.id === contextMenu.clipId);
                  if (seg) {
                    const at = seg.source_start + (currentTime - seg.timeline_start) * (seg.speed || 1);
                    onAction?.([{ action: "split", clip_id: seg.clip_id, at }]);
                  }
                }
                setContextMenu(null);
              }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                width: "100%",
                padding: "6px 12px",
                background: "none",
                border: "none",
                cursor: "pointer",
                color: color,
                fontSize: 13,
                fontFamily: font,
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
            >
              <Icon size={13} />
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Status bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 12px",
          height: 20,
          borderTop: "1px solid rgba(255,255,255,0.03)",
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 11, fontFamily: "monospace", color: dim(0.5) }}>
          {segments.length} clips · {captions.length} captions · {audioTracks.length} audio ·{" "}
          {textOverlays.length + imageOverlays.length} overlays
          {rippleEnabled && <span style={{ color: "#60a5fa", marginLeft: 8 }}>· Snap ON</span>}
        </span>
        <span style={{ fontSize: 11, color: dim(0.4), display: "flex", alignItems: "center", gap: 6 }}>
          <Ruler size={10} /> {Math.round(zoom * 100)}%
          <span style={{ color: dim(0.3) }}>·</span>
          {state?.metadata?.aspect_ratio || "9:16"} · {state?.metadata?.width}×{state?.metadata?.height}
        </span>
      </div>
    </div>
  );
}
