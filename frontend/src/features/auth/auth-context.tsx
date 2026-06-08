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

import { getCurrentUser, login as loginRequest } from "./auth-client";
import { getStoredAccessToken, removeStoredAccessToken } from "@/lib/auth";
import type { AuthState, CurrentUser, LoginRequest } from "@/types/auth";

type AuthContextValue = AuthState & {
  login: (payload: LoginRequest) => Promise<CurrentUser>;
  logout: () => void;
  refreshCurrentUser: () => Promise<CurrentUser | null>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
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
  }, []);

  useEffect(() => {
    void refreshCurrentUser();
  }, [refreshCurrentUser]);

  const login = useCallback(async (payload: LoginRequest) => {
    const response = await loginRequest(payload);
    const currentUser = await getCurrentUser(response.access_token);

    setToken(response.access_token);
    setUser(currentUser);

    return currentUser;
  }, []);

  const logout = useCallback(() => {
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
      login,
      logout,
      refreshCurrentUser,
    }),
    [isLoading, login, logout, refreshCurrentUser, token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }

  return context;
}
