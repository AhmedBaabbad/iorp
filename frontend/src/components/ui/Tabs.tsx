"use client";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { useLocale } from "next-intl";
import css from "./records.module.css";

export type TabItem = { id: string; label: string; content: ReactNode };
export function Tabs({ items, label, defaultTab, queryKey = "tab" }: {
  items: TabItem[]; label: string; defaultTab?: string; queryKey?: string;
}) {
  const locale = useLocale();
  const id = useId();
  const [selected, setSelected] = useState(defaultTab ?? items[0]?.id);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const ids = items.map(item => item.id).join("|");
  useEffect(() => {
    const sync = () => {
      const value = new URL(window.location.href).searchParams.get(queryKey);
      setSelected(value && ids.split("|").includes(value) ? value : defaultTab ?? ids.split("|")[0]);
    };
    sync(); window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, [queryKey, ids, defaultTab]);
  function choose(value: string) {
    setSelected(value);
    const url = new URL(window.location.href);
    url.searchParams.set(queryKey, value);
    window.history.replaceState(null, "", url);
  }
  return <div className={css.tabs} dir={locale === "ar" ? "rtl" : "ltr"}>
    <div role="tablist" aria-label={label} className={css.tablist}>
      {items.map((item, index) => <button key={item.id} type="button" role="tab"
        ref={node => { buttons.current[index] = node; }} id={`${id}-${item.id}-tab`}
        aria-controls={`${id}-${item.id}-panel`} aria-selected={selected === item.id}
        tabIndex={selected === item.id ? 0 : -1} onClick={() => choose(item.id)}
        onKeyDown={event => {
          let next = index;
          if (event.key === "Home") next = 0;
          else if (event.key === "End") next = items.length - 1;
          else if (event.key === "ArrowRight") next += locale === "ar" ? -1 : 1;
          else if (event.key === "ArrowLeft") next += locale === "ar" ? 1 : -1;
          else return;
          event.preventDefault(); next = (next + items.length) % items.length;
          choose(items[next].id); buttons.current[next]?.focus();
        }}>{item.label}</button>)}
    </div>
    {items.map(item => <div key={item.id} role="tabpanel" id={`${id}-${item.id}-panel`}
      aria-labelledby={`${id}-${item.id}-tab`} hidden={selected !== item.id} tabIndex={0}>{item.content}</div>)}
  </div>;
}
