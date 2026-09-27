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

import { getStoredPlatformToken, removeStoredPlatformToken } from "@/lib/platform-auth";
import type { PlatformAccount, PlatformAuthState, PlatformLoginRequest } from "@/types/platform";
import { getPlatformAccount, platformLogin, platformLogout } from "./platform-api";

type PlatformAuthContextValue = PlatformAuthState & {
  login: (payload: PlatformLoginRequest) => Promise<PlatformAccount>;
  logout: () => void;
  refreshAccount: () => Promise<PlatformAccount | null>;
};

const PlatformAuthContext = createContext<PlatformAuthContextValue | null>(null);

export function PlatformAuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [account, setAccount] = useState<PlatformAccount | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshAccount = useCallback(async () => {
    const storedToken = getStoredPlatformToken();

    if (!storedToken) {
      setToken(null);
      setAccount(null);
      setIsLoading(false);
      return null;
    }

    try {
      setIsLoading(true);
      const currentAccount = await getPlatformAccount(storedToken);
      setToken(storedToken);
      setAccount(currentAccount);
      return currentAccount;
    } catch {
      removeStoredPlatformToken();
      setToken(null);
      setAccount(null);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshAccount();
  }, [refreshAccount]);

  const login = useCallback(async (payload: PlatformLoginRequest) => {
    const response = await platformLogin(payload);
    const currentAccount = await getPlatformAccount(response.access_token);

    setToken(response.access_token);
    setAccount(currentAccount);

    return currentAccount;
  }, []);

  const logout = useCallback(() => {
    void platformLogout().catch(() => undefined);
    removeStoredPlatformToken();
    setToken(null);
    setAccount(null);
  }, []);

  const value = useMemo<PlatformAuthContextValue>(
    () => ({
      account,
      token,
      isLoading,
      isAuthenticated: Boolean(token && account),
      login,
      logout,
      refreshAccount,
    }),
    [account, isLoading, login, logout, refreshAccount, token],
  );

  return <PlatformAuthContext.Provider value={value}>{children}</PlatformAuthContext.Provider>;
}

export function usePlatformAuth() {
  const context = useContext(PlatformAuthContext);

  if (!context) {
    throw new Error("usePlatformAuth must be used within PlatformAuthProvider.");
  }

  return context;
}

export function useOptionalPlatformAuth() {
  return useContext(PlatformAuthContext);
}
