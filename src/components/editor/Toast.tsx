import { useEffect, useState } from "react";

export interface ToastMessage {
  id: string;
  text: string;
  type: "success" | "error" | "info";
}

interface ToastContainerProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  return (
    <div
      style={{
        position: "fixed",
        bottom: 60,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 999,
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          onClick={() => onDismiss(t.id)}
          style={{
            padding: "8px 16px",
            borderRadius: 6,
            fontSize: 12,
            fontWeight: 600,
            background:
              t.type === "error"
                ? "#dc2626"
                : t.type === "success"
                  ? "#16a34a"
                  : "rgba(255,255,255,0.12)",
            color: "#fff",
            cursor: "pointer",
            backdropFilter: "blur(8px)",
            boxShadow: "0 4px 20px rgba(0,0,0,0.4)",
            whiteSpace: "nowrap",
            animation: "toastIn 200ms ease-out",
          }}
        >
          {t.text}
        </div>
      ))}
    </div>
  );
}

let toastId = 0;
export function useToast() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = (text: string, type: "success" | "error" | "info" = "info") => {
    const id = String(++toastId);
    setToasts((prev) => [...prev, { id, text, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3000);
  };

  const dismiss = (id: string) => setToasts((prev) => prev.filter((t) => t.id !== id));

  return { toasts, addToast, dismiss };
}

// Global toast() that works from any component without hooks
const globalToasts: ToastMessage[] = [];
let globalSetToasts: ((msgs: ToastMessage[]) => void) | null = null;

export function toast(text: string, type: "success" | "error" | "info" = "info") {
  const id = String(++toastId);
  const msg: ToastMessage = { id, text, type };
  globalToasts.push(msg);
  globalSetToasts?.([...globalToasts]);
  setTimeout(() => {
    const idx = globalToasts.findIndex((t) => t.id === id);
    if (idx !== -1) globalToasts.splice(idx, 1);
    globalSetToasts?.([...globalToasts]);
  }, 3500);
}

export function GlobalToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  globalSetToasts = setToasts;

  return (
    <>
      {children}
      <ToastContainer toasts={toasts} onDismiss={(id) => {
        const idx = globalToasts.findIndex((t) => t.id === id);
        if (idx !== -1) globalToasts.splice(idx, 1);
        setToasts([...globalToasts]);
      }} />
    </>
  );
}
