"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { COLOR_SCHEME, STORAGE_KEY, isPreference, type Theme, type ThemePreference } from "./theme-config";

export type { Theme, ThemePreference } from "./theme-config";

type ThemeContextValue = {
  preference: ThemePreference;
  resolvedTheme: Theme;
  setPreference: (preference: ThemePreference) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function resolveTheme(preference: ThemePreference): Theme {
  if (preference !== "system") return preference;
  // Auto honors the device: increased-contrast first, then dark or light.
  if (window.matchMedia("(prefers-contrast: more)").matches) return "contrast";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(preference: ThemePreference) {
  const resolved = resolveTheme(preference);
  document.documentElement.dataset.theme = resolved;
  document.documentElement.dataset.themePreference = preference;
  document.documentElement.style.colorScheme = COLOR_SCHEME[resolved];
  return resolved;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>("system");
  const [resolvedTheme, setResolvedTheme] = useState<Theme>("light");

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    const initial: ThemePreference = isPreference(saved) ? saved : "system";
    setPreferenceState(initial);
    setResolvedTheme(applyTheme(initial));
  }, []);

  useEffect(() => {
    if (preference !== "system") return;
    const queries = ["(prefers-color-scheme: dark)", "(prefers-contrast: more)"].map((q) => window.matchMedia(q));
    const handleChange = () => setResolvedTheme(applyTheme("system"));
    queries.forEach((q) => q.addEventListener("change", handleChange));
    return () => queries.forEach((q) => q.removeEventListener("change", handleChange));
  }, [preference]);

  function setPreference(next: ThemePreference) {
    window.localStorage.setItem(STORAGE_KEY, next);
    setPreferenceState(next);
    setResolvedTheme(applyTheme(next));
  }

  const value = useMemo(() => ({ preference, resolvedTheme, setPreference }), [preference, resolvedTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within ThemeProvider");
  return context;
}
