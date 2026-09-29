// Shared by the server layout (pre-paint script) and the client ThemeProvider.

export const THEMES = ["light", "dark", "dim", "contrast"] as const;
export type Theme = (typeof THEMES)[number];
export type ThemePreference = Theme | "system";
export const THEME_PREFERENCES: ThemePreference[] = ["light", "dark", "dim", "contrast", "system"];
export const STORAGE_KEY = "iorp-theme";

// Native widgets (dropdown lists, date pickers) follow the theme's light or dark base.
export const COLOR_SCHEME: Record<Theme, "light" | "dark"> = { light: "light", dark: "dark", dim: "dark", contrast: "light" };

export function isPreference(value: string | null): value is ThemePreference {
  return value !== null && (THEME_PREFERENCES as string[]).includes(value);
}

// Runs before first paint so the page never flashes the wrong theme.
export const themeScript = `(function(){try{var p=localStorage.getItem(${JSON.stringify(STORAGE_KEY)});var ok=${JSON.stringify(THEME_PREFERENCES)};if(ok.indexOf(p)<0)p='system';var d=p==='system'?(matchMedia('(prefers-contrast: more)').matches?'contrast':matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'):p;var s=${JSON.stringify(COLOR_SCHEME)};var e=document.documentElement;e.dataset.theme=d;e.dataset.themePreference=p;e.style.colorScheme=s[d]}catch(x){}})()`;
