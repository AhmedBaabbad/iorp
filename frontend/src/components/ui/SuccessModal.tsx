"use client";

import type { CSSProperties } from "react";

type SuccessModalProps = {
  message: string;
  onOk: () => void;
  okLabel?: string;
};

const styles: Record<string, CSSProperties> = {
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "var(--overlay)",
    backdropFilter: "blur(2px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },
  modal: {
    background: "var(--surface)",
    borderRadius: "14px",
    boxShadow: "0 24px 64px rgba(15, 23, 42, 0.22), 0 4px 16px rgba(15, 23, 42, 0.10)",
    padding: "36px 32px 28px",
    maxWidth: "400px",
    width: "90%",
    display: "grid",
    gap: "16px",
    textAlign: "center",
  },
  icon: {
    width: "52px",
    height: "52px",
    borderRadius: "50%",
    background: "var(--success-soft)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "26px",
    margin: "0 auto",
  },
  message: {
    fontSize: "15px",
    color: "var(--text)",
    fontWeight: 500,
    margin: 0,
    lineHeight: "1.6",
  },
  okButton: {
    background: "var(--accent)",
    border: "none",
    borderRadius: "8px",
    color: "var(--on-accent)",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: 600,
    minHeight: "40px",
    padding: "10px 32px",
    justifySelf: "center",
    minWidth: "120px",
  },
};

export function SuccessModal({ message, onOk, okLabel = "OK" }: SuccessModalProps) {
  return (
    <div style={styles.backdrop}>
      <div style={styles.modal} role="dialog" aria-modal="true">
        <div style={styles.icon}>✓</div>
        <p style={styles.message}>{message}</p>
        <button type="button" style={styles.okButton} onClick={onOk} autoFocus>
          {okLabel}
        </button>
      </div>
    </div>
  );
}
