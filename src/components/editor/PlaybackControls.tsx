import { Play, Pause, SkipBack, SkipForward, Volume2, VolumeX, Volume1 } from "lucide-react";
import { useState } from "react";

interface PlaybackControlsProps {
  currentTime: number;
  duration: number;
  playing: boolean;
  isMuted: boolean;
  speed: number;
  onTogglePlay: () => void;
  onSeek: (time: number) => void;
  onToggleMute: () => void;
  onStepForward: () => void;
  onStepBackward: () => void;
  onSpeedChange: (speed: number) => void;
}

const fmt = (t: number) => {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  const ms = Math.floor((t % 1) * 100);
  return `${m}:${String(s).padStart(2, "0")}.${String(ms).padStart(2, "0")}`;
};

const SPEEDS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 4.0];

export function PlaybackControls({
  currentTime,
  duration,
  playing,
  isMuted,
  speed,
  onTogglePlay,
  onSeek,
  onToggleMute,
  onStepForward,
  onStepBackward,
  onSpeedChange,
}: PlaybackControlsProps) {
  const [volume, setVolume] = useState(1);
  const bg = "#0a0a0c";
  const font = "'Space Grotesk',sans-serif";
  const dim = (_a?: number) => "#FAFAFA";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "0 16px",
        height: 44,
        background: "#050507",
        borderTop: "1px solid rgba(255,255,255,0.06)",
        flexShrink: 0,
      }}
    >
      {/* Frame step backward */}
      <button
        onClick={onStepBackward}
        title="Step back 1 frame (←)"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 26,
          height: 26,
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: dim(0.55),
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = dim(0.9))}
        onMouseLeave={(e) => (e.currentTarget.style.color = dim(0.55))}
      >
        <SkipBack size={13} />
      </button>

      {/* Play/Pause */}
      <button
        onClick={onTogglePlay}
        title="Play/Pause (Space)"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 30,
          height: 30,
          borderRadius: 0,
          background: "#DFE104",
          border: "none",
          cursor: "pointer",
          color: "#000",
          transition: "transform 120ms",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.transform = "scale(1.08)")}
        onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}
      >
        {playing ? <Pause size={12} /> : <Play size={12} style={{ marginLeft: 1 }} />}
      </button>

      {/* Frame step forward */}
      <button
        onClick={onStepForward}
        title="Step forward 1 frame (→)"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 26,
          height: 26,
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: dim(0.55),
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = dim(0.9))}
        onMouseLeave={(e) => (e.currentTarget.style.color = dim(0.55))}
      >
        <SkipForward size={13} />
      </button>

      {/* Seek bar */}
      <div
        style={{
          flex: 1,
          height: 3,
          background: "rgba(255,255,255,0.07)",
          cursor: "pointer",
          borderRadius: 0,
          position: "relative",
        }}
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const t = ((e.clientX - r.left) / r.width) * duration;
          onSeek(Math.max(0, Math.min(duration, t)));
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${(currentTime / duration) * 100}%`,
            background: "#DFE104",
            borderRadius: 0,
            transition: "none",
          }}
        />
        {/* Playhead indicator */}
        <div
          style={{
            position: "absolute",
            top: -4,
            left: `${(currentTime / duration) * 100}%`,
            width: 2,
            height: 11,
            background: "#DFE104",
            transform: "translateX(-50%)",
            boxShadow: "0 0 8px rgba(223,225,4,0.6)",
            pointerEvents: "none",
          }}
        />
      </div>

      {/* Time display */}
      <span
        style={{
          fontSize: 13,
          color: dim(0.65),
          fontFamily: "monospace",
          flexShrink: 0,
          minWidth: 90,
          textAlign: "right",
        }}
      >
        {fmt(currentTime)} / {fmt(duration)}
      </span>

      {/* Speed selector */}
      <select
        value={speed}
        onChange={(e) => onSpeedChange(parseFloat(e.target.value))}
        style={{
          background: "rgba(255,255,255,0.04)",
          border: "1px solid rgba(255,255,255,0.08)",
          color: "#FAFAFA",
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.1em",
          padding: "2px 6px",
          cursor: "pointer",
          fontFamily: "'Space Grotesk', sans-serif",
          borderRadius: 0,
          outline: "none",
        }}
      >
        {SPEEDS.map((s) => (
          <option key={s} value={s} style={{ background: "#111" }}>
            {s}x
          </option>
        ))}
      </select>

      {/* Volume */}
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <button
          onClick={onToggleMute}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            padding: 4,
            color: isMuted ? "#DFE104" : "#FAFAFA",
            transition: "color 150ms",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "#DFE104")}
          onMouseLeave={(e) => (e.currentTarget.style.color = isMuted ? "#DFE104" : "#FAFAFA")}
        >
          {isMuted || volume === 0 ? <VolumeX size={14} /> : volume < 0.5 ? <Volume1 size={14} /> : <Volume2 size={14} />}
        </button>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={isMuted ? 0 : volume}
          onChange={(e) => {
            const v = parseFloat(e.target.value);
            setVolume(v);
            const video = document.querySelector("video");
            if (video) video.volume = v;
          }}
          style={{
            width: 60,
            height: 2,
            accentColor: "#DFE104",
            cursor: "pointer",
          }}
        />
      </div>
    </div>
  );
}
