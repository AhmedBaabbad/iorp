"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useLocale } from "next-intl";

import { getCurrentUser, login as loginRequest, logoutSession } from "./auth-client";
import { getStoredAccessToken, removeStoredAccessToken } from "@/lib/auth";
import { SessionGuard } from "./session-guard";
import { markActivity } from "@/lib/session-policy";
import type { AuthState, CurrentUser, LoginRequest } from "@/types/auth";
import { isLocale, LOCALE_COOKIE_NAME, type Locale } from "@/i18n/config";

type AuthContextValue = AuthState & {
  login: (payload: LoginRequest) => Promise<CurrentUser>;
  logout: () => void;
  refreshCurrentUser: () => Promise<CurrentUser | null>;
  permissions: string[];
  roles: string[];
  hasPermission: (code: string) => boolean;
  usePermission: (code: string) => boolean;
  useHasAnyPermission: (codes: string[]) => boolean;
};

export function hasPermission(permissions: string[], code: string): boolean {
  return permissions.includes(code);
}

const AuthContext = createContext<AuthContextValue | null>(null);

function resolveEffectiveLocale(user: CurrentUser, fallback: Locale): Locale {
  if (isLocale(user.effective_locale)) return user.effective_locale;
  if (isLocale(user.preferred_locale ?? undefined)) return user.preferred_locale as Locale;
  if (isLocale(user.organization?.default_locale)) return user.organization.default_locale;
  return fallback;
}

function applyEffectiveLocale(user: CurrentUser, fallback: Locale) {
  if (typeof document === "undefined") return;
  const storedLocale = document.cookie.split("; ").find((item) => item.startsWith(`${LOCALE_COOKIE_NAME}=`))?.split("=")[1];
  const locale = isLocale(storedLocale) ? storedLocale : resolveEffectiveLocale(user, fallback);
  document.documentElement.lang = locale;
  document.documentElement.dir = locale === "ar" ? "rtl" : "ltr";
  if (storedLocale !== locale) {
    document.cookie = `${LOCALE_COOKIE_NAME}=${locale}; path=/; max-age=31536000; SameSite=Lax`;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const renderedLocale = useLocale() as Locale;
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshCurrentUser = useCallback(async () => {
    const storedToken = getStoredAccessToken();

    if (!storedToken) {
      setToken(null);
      setUser(null);
      setIsLoading(false);
      return null;
    }

    try {
      setIsLoading(true);
      const currentUser = await getCurrentUser(storedToken);
      applyEffectiveLocale(currentUser, renderedLocale);
      setToken(storedToken);
      setUser(currentUser);
      return currentUser;
    } catch {
      removeStoredAccessToken();
      setToken(null);
      setUser(null);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [renderedLocale]);

  useEffect(() => {
    void refreshCurrentUser();
  }, [refreshCurrentUser]);

  const login = useCallback(async (payload: LoginRequest) => {
    const response = await loginRequest(payload);
    markActivity(); // a fresh idle window, so an old session's last activity cannot sign this one out
    const currentUser = await getCurrentUser(response.access_token);
    applyEffectiveLocale(currentUser, renderedLocale);

    setToken(response.access_token);
    setUser(currentUser);

    return currentUser;
  }, [renderedLocale]);

  const logout = useCallback(() => {
    void logoutSession().catch(() => undefined);
    removeStoredAccessToken();
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isLoading,
      isAuthenticated: Boolean(token && user),
      permissions: user?.permissions ?? [],
      roles: user?.roles ?? [],
      login,
      logout,
      refreshCurrentUser,
      hasPermission: (code: string) => hasPermission(user?.permissions ?? [], code),
      usePermission: (code: string) => hasPermission(user?.permissions ?? [], code),
      useHasAnyPermission: (codes: string[]) =>
        codes.some((c) => hasPermission(user?.permissions ?? [], c)),
    }),
    [isLoading, login, logout, refreshCurrentUser, token, user],
  );

  const clearSession = useCallback(() => { setToken(null); setUser(null); }, []);
  return (
    <AuthContext.Provider value={value}>
      {children}
      {/* Signs out on inactivity or when the session ends, without waiting for a click. */}
      {value.isAuthenticated && <SessionGuard onSignedOut={clearSession} />}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }

  return context;
}
