"use client";

import type { CSSProperties } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { updateMyProfile } from "@/features/auth/auth-client";
import { useAuth } from "@/features/auth/auth-context";
import { LOCALE_COOKIE_NAME, LOCALES, type Locale } from "@/i18n/config";

type LanguageSwitcherProps = {
  label: string;
};

const styles: Record<string, CSSProperties> = {
  wrapper: {
    alignItems: "center",
    display: "flex",
    gap: "8px",
    justifyContent: "flex-end",
    marginBottom: "18px",
  },
  label: {
    color: "#52606d",
    fontSize: "13px",
    fontWeight: 700,
  },
  button: {
    background: "transparent",
    border: "1px solid #c8d0dc",
    borderRadius: "6px",
    color: "#1f2933",
    cursor: "pointer",
    font: "inherit",
    fontSize: "13px",
    fontWeight: 700,
    padding: "6px 10px",
  },
  activeButton: {
    background: "#1f2933",
    borderColor: "#1f2933",
    color: "#ffffff",
  },
};

export function LanguageSwitcher({ label }: LanguageSwitcherProps) {
  const currentLocale = useLocale() as Locale;
  const t = useTranslations("common");
  const { user } = useAuth();
  const [isChanging, setIsChanging] = useState(false);

  async function setLocale(locale: Locale) {
    if (locale === currentLocale || isChanging) return;
    setIsChanging(true);
    try {
      if (user) {
        try {
          await updateMyProfile({ preferred_locale: locale });
        } catch {
          // Keep the explicit UI language choice usable while an older API is still running.
        }
      }
      document.cookie = `${LOCALE_COOKIE_NAME}=${locale}; path=/; max-age=31536000; SameSite=Lax`;
      document.documentElement.lang = locale;
      document.documentElement.dir = locale === "ar" ? "rtl" : "ltr";
      window.location.reload();
    } finally {
      setIsChanging(false);
    }
  }

  return (
    <div style={styles.wrapper} aria-label={label}>
      <span style={styles.label}>{label}</span>
      {LOCALES.map((locale) => (
        <button
          key={locale}
          type="button"
          style={{
            ...styles.button,
            ...(locale === currentLocale ? styles.activeButton : {}),
          }}
          onClick={() => setLocale(locale)}
          disabled={isChanging}
        >
          {t(`languages.${locale}`)}
        </button>
      ))}
    </div>
  );
}
