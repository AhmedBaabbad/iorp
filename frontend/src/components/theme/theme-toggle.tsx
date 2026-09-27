"use client";

import { useTranslations } from "next-intl";
import { useTheme, type ThemePreference } from "./theme-provider";
import styles from "./theme-toggle.module.css";

const choices: ThemePreference[] = ["light", "dark", "system"];

export function ThemeToggle() {
  const t = useTranslations("navigation.theme");
  const { preference, setPreference } = useTheme();

  return (
    <div className={styles.root} role="group" aria-label={t("label")}>
      <span className={`iorp-nav-label ${styles.label}`}>{t("label")}</span>
      <div className={styles.options}>
        {choices.map((choice) => (
          <button
            type="button"
            key={choice}
            className={preference === choice ? styles.active : styles.option}
            onClick={() => setPreference(choice)}
            aria-pressed={preference === choice}
            title={t(choice)}
          >
            <span aria-hidden="true">{choice === "light" ? "☀" : choice === "dark" ? "☾" : "◐"}</span>
            <span className="iorp-nav-label">{t(choice)}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
