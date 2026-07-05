import { useCallback, useRef, useState } from "react";

interface ResizableDividerProps {
  direction: "horizontal" | "vertical";
  onResize: (delta: number) => void;
  minSize?: number;
  maxSize?: number;
}

export function ResizableDivider({ direction, onResize }: ResizableDividerProps) {
  const [dragging, setDragging] = useState(false);
  const startRef = useRef(0);

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setDragging(true);
      startRef.current = direction === "horizontal" ? e.clientX : e.clientY;

      const onMouseMove = (ev: MouseEvent) => {
        const current = direction === "horizontal" ? ev.clientX : ev.clientY;
        onResize(current - startRef.current);
        startRef.current = current;
      };

      const onMouseUp = () => {
        setDragging(false);
        document.removeEventListener("mousemove", onMouseMove);
        document.removeEventListener("mouseup", onMouseUp);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      };

      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
      document.body.style.cursor = direction === "horizontal" ? "col-resize" : "row-resize";
      document.body.style.userSelect = "none";
    },
    [direction, onResize],
  );

  const isH = direction === "horizontal";

  return (
    <div
      onMouseDown={onMouseDown}
      style={{
        width: isH ? 5 : "100%",
        height: isH ? "100%" : 5,
        cursor: isH ? "col-resize" : "row-resize",
        background: dragging ? "#2563eb" : "rgba(255,255,255,0.06)",
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transition: "background 150ms",
        position: "relative",
        zIndex: 10,
      }}
      onMouseEnter={(e) => {
        if (!dragging) e.currentTarget.style.background = "rgba(255,255,255,0.12)";
      }}
      onMouseLeave={(e) => {
        if (!dragging) e.currentTarget.style.background = "rgba(255,255,255,0.06)";
      }}
    >
      {/* grip dots */}
      <div
        style={{
          display: "flex",
          flexDirection: isH ? "column" : "row",
          gap: 3,
          opacity: dragging ? 1 : 0.4,
        }}
      >
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            style={{
              width: isH ? 3 : 3,
              height: isH ? 3 : 3,
              borderRadius: "50%",
              background: dragging ? "#60a5fa" : "rgba(255,255,255,0.5)",
            }}
          />
        ))}
      </div>
    </div>
  );
}
