"use client";

import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import s from "./dialog.module.css";

export type DialogProps = {
  title: ReactNode;
  onClose: () => void;
  busy?: boolean;
  size?: "sm" | "md" | "lg";
  footer?: ReactNode;
  onSubmit?: (e: FormEvent<HTMLFormElement>) => void;
  role?: "dialog" | "alertdialog";
  children: ReactNode;
};

// Only the top dialog owns keyboard focus. Keep the original overflow until the last closes.
const openDialogs: HTMLElement[] = [];
let previousOverflow = "";
const selector = 'button, input:not([type="hidden"]), select, textarea, a[href], [tabindex], [contenteditable="true"]';
function focusable(root: HTMLElement) {
  return Array.from(root.querySelectorAll<HTMLElement>(selector)).filter(node =>
    node.tabIndex >= 0 && !node.matches(":disabled") && !node.closest('[hidden], [inert], [aria-hidden="true"]') &&
    getComputedStyle(node).display !== "none" && getComputedStyle(node).visibility !== "hidden");
}

export function Dialog({ title, onClose, busy = false, size = "md", footer, onSubmit, role = "dialog", children }: DialogProps) {
  const t = useTranslations("common");
  const titleId = useId();
  const panel = useRef<HTMLDivElement & HTMLFormElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const latest = useRef({ busy, onClose });
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setMounted(true);
  }, []);
  useEffect(() => { latest.current = { busy, onClose }; }, [busy, onClose]);
  useEffect(() => {
    const node = panel.current;
    if (!mounted || !node) return;
    if (openDialogs.length === 0) {
      previousOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
    }
    openDialogs.push(node);
    const isTop = () => openDialogs.at(-1) === node;
    const first = () => (body.current && focusable(body.current)[0]) || focusable(node)[0] || node;
    if (!node.contains(document.activeElement)) first().focus();
    const keydown = (event: KeyboardEvent) => {
      if (!isTop()) return;
      if (event.key === "Escape") {
        event.preventDefault(); event.stopPropagation();
        if (!latest.current.busy) latest.current.onClose();
      } else if (event.key === "Tab") {
        const items = focusable(node);
        const active = document.activeElement;
        const index = items.indexOf(active as HTMLElement);
        if (!items.length) { event.preventDefault(); node.focus(); }
        else if (event.shiftKey && index <= 0) { event.preventDefault(); items.at(-1)?.focus(); }
        else if (!event.shiftKey && (index === -1 || index === items.length - 1)) { event.preventDefault(); items[0].focus(); }
      }
    };
    const focusin = (event: FocusEvent) => {
      if (isTop() && !node.contains(event.target as Node)) first().focus();
    };
    document.addEventListener("keydown", keydown, true);
    document.addEventListener("focusin", focusin);
    return () => {
      document.removeEventListener("keydown", keydown, true);
      document.removeEventListener("focusin", focusin);
      const wasTop = isTop();
      openDialogs.splice(openDialogs.indexOf(node), 1);
      if (!openDialogs.length) document.body.style.overflow = previousOverflow;
      const top = openDialogs.at(-1);
      if (wasTop && opener.current?.isConnected && (!top || top.contains(opener.current))) opener.current.focus();
      else if (wasTop && top) (focusable(top)[0] || top).focus();
    };
  }, [mounted]);

  if (!mounted) return null;
  const content = <>
    <header className={s.header}>
      <h2 id={titleId}>{title}</h2>
      <button type="button" className={s.close} aria-label={t("actions.close")} disabled={busy} onClick={onClose}>✕</button>
    </header>
    <div ref={body} className={s.body}>{children}</div>
    {footer != null && <footer className={s.footer}>{footer}</footer>}
  </>;
  const props = { ref: panel, role, "aria-modal": true as const, "aria-labelledby": titleId, "aria-busy": busy,
    tabIndex: -1, className: `${s.panel} ${s[size]}` };
  return createPortal(<div className={s.overlay}>
    {onSubmit ? <form {...props} onSubmit={event => { event.stopPropagation(); onSubmit(event); }}>{content}</form> : <div {...props}>{content}</div>}
  </div>, document.body);
}
