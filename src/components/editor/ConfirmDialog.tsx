import { useState } from "react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  destructive = true,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null;

  return (
    <div
      onClick={onCancel}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 500,
        background: "rgba(0,0,0,0.7)",
        backdropFilter: "blur(6px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#111113",
          border: "1px solid rgba(255,255,255,0.08)",
          maxWidth: 340,
          width: "100%",
          padding: 24,
          borderRadius: 8,
        }}
      >
        <p
          style={{ fontSize: 14, fontWeight: 700, color: "#FAFAFA", marginBottom: 8 }}
        >
          {title}
        </p>
        <p
          style={{
            fontSize: 13,
            color: "#FAFAFA",
            marginBottom: 20,
            lineHeight: "1.5",
          }}
        >
          {message}
        </p>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button
            onClick={onCancel}
            style={{
              padding: "8px 16px",
              fontSize: 12,
              fontWeight: 600,
              background: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(255,255,255,0.08)",
              color: "#FAFAFA",
              cursor: "pointer",
              borderRadius: 4,
            }}
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            style={{
              padding: "8px 16px",
              fontSize: 12,
              fontWeight: 600,
              background: destructive ? "#dc2626" : "#2563eb",
              border: "none",
              color: "#fff",
              cursor: "pointer",
              borderRadius: 4,
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
