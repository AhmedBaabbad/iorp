"use client";

import { useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { THEME_PREFERENCES, type ThemePreference } from "./theme-config";
import { useTheme } from "./theme-provider";
import styles from "./theme-toggle.module.css";

const svg = (children: ReactNode) => <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>;
const ICONS: Record<ThemePreference, ReactNode> = {
  light: svg(<><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>),
  dark: svg(<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />),
  dim: svg(<><path d="M20 14.5A8 8 0 1 1 9.5 4a6 6 0 0 0 10.5 10.5z" /><path d="M3 21h18" /></>),
  contrast: svg(<><circle cx="12" cy="12" r="9" /><path d="M12 3v18a9 9 0 0 0 0-18z" fill="currentColor" /></>),
  system: svg(<><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" /></>),
};

export function ThemeToggle() {
  const t = useTranslations("navigation.theme");
  const { preference, setPreference } = useTheme();

  return (
    <div className={styles.root} role="group" aria-label={t("label")}>
      <span className={`iorp-nav-label ${styles.label}`}>{t("label")} · <strong>{t(preference)}</strong></span>
      <div className={styles.options}>
        {THEME_PREFERENCES.map((choice) => (
          <button
            type="button"
            key={choice}
            className={preference === choice ? styles.active : styles.option}
            onClick={() => setPreference(choice)}
            aria-pressed={preference === choice}
            aria-label={t(choice)}
            title={`${t(choice)} — ${t(`hint.${choice}`)}`}
          >
            {ICONS[choice]}
          </button>
        ))}
      </div>
    </div>
  );
}
