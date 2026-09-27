import { hasPermission, useAuth } from "./auth-context";

export function usePermission(code: string): boolean {
  const { permissions } = useAuth();
  return hasPermission(permissions, code);
}

export function useHasAnyPermission(codes: string[]): boolean {
  const { permissions } = useAuth();
  return codes.some((c) => hasPermission(permissions, c));
}
