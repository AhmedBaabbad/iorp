"use client";
import { useCallback, useEffect, useRef } from "react";

const FOCUSABLE = "input:not([disabled]):not([type=hidden]):not([readonly]), select:not([disabled]), textarea:not([disabled]), [role=combobox]:not([aria-disabled=true])";

/** Lines of a document are added at the end. After the user adds one, the screen moves to it and its first field is
 *  focused, so the next line is added from the button under it without scrolling back up. Lines loaded from the server
 *  do not move the screen: only an addition announced with the returned function does.
 *  Mark each line with `data-row={group}`; `count` is the number of lines. */
export function useRevealNewRow(count: number, group: string) {
  const previous = useRef(count);
  const pending = useRef(false);
  useEffect(() => {
    const grew = count > previous.current;
    previous.current = count;
    if (!grew || !pending.current) return;
    pending.current = false;
    const rows = document.querySelectorAll<HTMLElement>(`[data-row="${group}"]`);
    const row = rows[rows.length - 1];
    if (!row) return;
    row.scrollIntoView?.({ behavior: "smooth", block: "center" });
    row.querySelector<HTMLElement>(FOCUSABLE)?.focus({ preventScroll: true });
  }, [count, group]);
  return useCallback(() => { pending.current = true; }, []);
}
