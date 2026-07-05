import { useState, useMemo } from "react";
import { Scissors, Subtitles, ZoomIn, Music, CheckCircle2, XCircle, AlertTriangle, Eye, EyeOff } from "lucide-react";
import { cn } from "@/lib/utils";
import type { EditEvent, ChangelogEntry } from "@/lib/api";

interface TimelineSummaryProps {
  changelog: ChangelogEntry;
  onApplyChanges?: (events: EditEvent[]) => void;
}

const EVENT_ICONS: Record<string, any> = {
  cut: Scissors,
  caption: Subtitles,
  zoom: ZoomIn,
  meme_sound: Music,
  silence_removed: XCircle,
  filler_removed: AlertTriangle,
};

const EVENT_COLORS: Record<string, { bg: string; dot: string }> = {
  cut: { bg: "bg-red-500/10 border-red-500/20", dot: "bg-red-400" },
  caption: { bg: "bg-emerald-500/10 border-emerald-500/20", dot: "bg-emerald-400" },
  zoom: { bg: "bg-amber-500/10 border-amber-500/20", dot: "bg-amber-400" },
  meme_sound: { bg: "bg-purple-500/10 border-purple-500/20", dot: "bg-purple-400" },
  silence_removed: { bg: "bg-red-500/10 border-red-500/20", dot: "bg-red-400" },
  filler_removed: { bg: "bg-orange-500/10 border-orange-500/20", dot: "bg-orange-400" },
};

const TYPE_LABELS: Record<string, string> = {
  cut: "Cut",
  caption: "Caption",
  zoom: "Zoom",
  meme_sound: "Meme",
  silence_removed: "Silence Removed",
  filler_removed: "Filler Removed",
};

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function TimelineSummary({ changelog, onApplyChanges }: TimelineSummaryProps) {
  const [events, setEvents] = useState<EditEvent[]>(() =>
    (changelog.edit_events || []).map((e) => ({ ...e, enabled: true }))
  );
  const [selectedEvent, setSelectedEvent] = useState<EditEvent | null>(null);
  const [showOnlyEnabled, setShowOnlyEnabled] = useState(false);

  const toggleEvent = (timestamp: number, type: string) => {
    setEvents((prev) =>
      prev.map((e) =>
        e.timestamp === timestamp && e.type === type ? { ...e, enabled: !e.enabled } : e
      )
    );
  };

  const displayedEvents = showOnlyEnabled ? events.filter((e) => e.enabled) : events;

  const summary = useMemo(() => {
    const added = events.filter((e) => e.subtype === "added" && e.enabled).length;
    const removed = events.filter((e) => e.subtype === "removed" && e.enabled).length;
    const modified = events.filter((e) => e.subtype === "modified" && e.enabled).length;
    const kept = events.filter((e) => e.subtype === "cut" && e.enabled).length;
    const totalEnabled = events.filter((e) => e.enabled).length;
    const toggledOff = events.length - totalEnabled;
    return { added, removed, modified, kept, toggledOff, total: events.length };
  }, [events]);

  const duration = changelog.edited_duration || changelog.original_duration || 60;

  return (
    <div className="space-y-4">
      {/* Timeline bar */}
      <div className="relative rounded-lg border border-white/[0.06] bg-white/[0.01] p-4">
        <div className="flex items-center justify-between mb-2.5">
          <span className="text-[10px] text-white/30 uppercase tracking-wider">Timeline</span>
          <span className="text-[10px] text-white/20">
            {formatTime(0)} — {formatTime(duration)}
          </span>
        </div>
        <div className="relative h-8">
          <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-white/5" />
          {displayedEvents.map((e, i) => {
            const pct = duration > 0 ? (e.timestamp / duration) * 100 : 0;
            const colors = EVENT_COLORS[e.type] || EVENT_COLORS.cut;
            return (
              <button
                key={`${e.timestamp}-${e.type}-${i}`}
                onClick={() => setSelectedEvent(selectedEvent?.timestamp === e.timestamp && selectedEvent?.type === e.type ? null : e)}
                className={cn(
                  "absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-3.5 w-3.5 rounded-full border-2 transition-all hover:scale-150",
                  e.enabled ? colors.dot : "bg-white/10 border-white/10",
                  selectedEvent?.timestamp === e.timestamp && selectedEvent?.type === e.type ? "ring-2 ring-white/30 scale-150" : "",
                )}
                style={{ left: `${Math.max(1, Math.min(99, pct))}%` }}
                title={e.description}
              />
            );
          })}
        </div>
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-2 text-[9px] text-white/20">
            {Object.entries(EVENT_COLORS).slice(0, 4).map(([type, c]) => (
              <span key={type} className="flex items-center gap-1">
                <span className={cn("h-1.5 w-1.5 rounded-full", c.dot)} />
                {TYPE_LABELS[type]}
              </span>
            ))}
          </div>
          <button
            onClick={() => setShowOnlyEnabled(!showOnlyEnabled)}
            className={cn(
              "flex items-center gap-1 text-[9px] transition",
              showOnlyEnabled ? "text-[#60a5fa]" : "text-white/20 hover:text-white/40"
            )}
          >
            {showOnlyEnabled ? <Eye className="h-2.5 w-2.5" /> : <EyeOff className="h-2.5 w-2.5" />}
            {showOnlyEnabled ? "All" : "Active"}
          </button>
        </div>
      </div>

      {/* Selected event detail */}
      {selectedEvent && (
        <div className={cn(
          "rounded-lg border p-3",
          EVENT_COLORS[selectedEvent.type]?.bg || "border-white/[0.06] bg-white/[0.01]",
        )}>
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2">
              {(() => {
                const Icon = EVENT_ICONS[selectedEvent.type] || Scissors;
                return <Icon className="h-3 w-3 text-white/40" />;
              })()}
              <span className="text-[11px] font-medium text-white/60">
                {TYPE_LABELS[selectedEvent.type] || selectedEvent.type}
              </span>
              <span className="text-[10px] text-white/20">
                @{formatTime(selectedEvent.timestamp)}
              </span>
            </div>
            <button
              onClick={() => toggleEvent(selectedEvent.timestamp, selectedEvent.type)}
              className={cn(
                "flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-medium transition border",
                selectedEvent.enabled
                  ? "text-emerald-400 border-emerald-500/20 bg-emerald-500/10"
                  : "text-white/20 border-white/10 bg-white/[0.03]",
              )}
            >
              {selectedEvent.enabled ? (
                <><CheckCircle2 className="h-2.5 w-2.5" /> Enabled</>
              ) : (
                <><XCircle className="h-2.5 w-2.5" /> Disabled</>
              )}
            </button>
          </div>
          <p className="text-[12px] text-white/50">{selectedEvent.description}</p>
          {selectedEvent.content && (
            <p className="mt-1 text-[11px] text-white/30 italic">"{selectedEvent.content}"</p>
          )}
          {selectedEvent.scale && (
            <p className="mt-1 text-[10px] text-white/20">Scale: {selectedEvent.scale}x</p>
          )}
          {selectedEvent.count && (
            <p className="mt-1 text-[10px] text-white/20">Count: {selectedEvent.count}</p>
          )}
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-2">
        <div className="rounded-lg border border-emerald-500/10 bg-emerald-500/[0.03] p-2.5 text-center">
          <p className="text-[18px] font-bold text-emerald-400">{summary.added}</p>
          <p className="text-[9px] text-emerald-400/60 uppercase tracking-wider mt-0.5">Added</p>
        </div>
        <div className="rounded-lg border border-blue-500/10 bg-blue-500/[0.03] p-2.5 text-center">
          <p className="text-[18px] font-bold text-blue-400">{summary.kept}</p>
          <p className="text-[9px] text-blue-400/60 uppercase tracking-wider mt-0.5">Kept</p>
        </div>
        <div className="rounded-lg border border-amber-500/10 bg-amber-500/[0.03] p-2.5 text-center">
          <p className="text-[18px] font-bold text-amber-400">{summary.modified}</p>
          <p className="text-[9px] text-amber-400/60 uppercase tracking-wider mt-0.5">Modified</p>
        </div>
        <div className="rounded-lg border border-red-500/10 bg-red-500/[0.03] p-2.5 text-center">
          <p className="text-[18px] font-bold text-red-400">{summary.removed}</p>
          <p className="text-[9px] text-red-400/60 uppercase tracking-wider mt-0.5">Removed</p>
        </div>
      </div>

      {summary.toggledOff > 0 && (
        <div className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.01] p-2.5">
          <span className="text-[11px] text-white/30">
            {summary.toggledOff} edit{summary.toggledOff !== 1 ? "s" : ""} disabled
          </span>
          <button
            onClick={() => onApplyChanges?.(events)}
            className="rounded-md bg-[#2563eb]/20 px-3 py-1 text-[10px] font-medium text-[#60a5fa] transition hover:bg-[#2563eb]/30"
          >
            Apply Changes
          </button>
        </div>
      )}
    </div>
  );
}
