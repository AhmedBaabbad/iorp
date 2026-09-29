// Client session policy: sign out after inactivity, keep an active user's token fresh.
// Pure functions so the timing rules can be tested without a browser.

const minutes = Number(process.env.NEXT_PUBLIC_IDLE_TIMEOUT_MINUTES ?? "5");
/** Inactivity (no pointer, key, touch or scroll) that ends the session. */
export const IDLE_TIMEOUT_MS = (Number.isFinite(minutes) && minutes > 0 ? minutes : 5) * 60_000;
/** How long before the idle logout the countdown warning appears. */
export const IDLE_WARNING_MS = Math.min(60_000, IDLE_TIMEOUT_MS / 2);
/** Renew the access token this long before it expires, but only for an active user. */
export const REFRESH_AHEAD_MS = 60_000;
/** Shared across tabs so activity in one tab keeps the others signed in. */
export const LAST_ACTIVITY_KEY = "iorp.last_activity";

export type SessionAction =
  | { type: "logout" }
  | { type: "warn"; secondsLeft: number }
  | { type: "refresh" }
  | { type: "ok" };

/** Expiry (ms since epoch) from a JWT's exp claim, or null when it cannot be read. */
export function tokenExpiry(token: string | null): number | null {
  if (!token) return null;
  try {
    const payload = token.split(".")[1];
    const json = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(payload.length / 4) * 4, "=")));
    return typeof json.exp === "number" ? json.exp * 1000 : null;
  } catch {
    return null;
  }
}

/** What the guard should do right now. Idle logout wins over everything else. */
export function nextSessionAction(now: number, lastActivity: number, tokenExpiresAt: number | null): SessionAction {
  const idle = now - lastActivity;
  if (idle >= IDLE_TIMEOUT_MS) return { type: "logout" };
  if (idle >= IDLE_TIMEOUT_MS - IDLE_WARNING_MS) return { type: "warn", secondsLeft: Math.ceil((IDLE_TIMEOUT_MS - idle) / 1000) };
  // An active user never sees their token lapse; an idle one is signed out above instead.
  if (tokenExpiresAt !== null && tokenExpiresAt - now <= REFRESH_AHEAD_MS) return { type: "refresh" };
  return { type: "ok" };
}

/** Record activity now (shared with other tabs). Also called on sign-in to start a fresh idle window. */
export function markActivity(at = Date.now()) {
  try { window.localStorage.setItem(LAST_ACTIVITY_KEY, String(at)); } catch { /* storage unavailable: tabs track activity in memory */ }
}

/** Last recorded activity across tabs, or null when none was recorded. */
export function readLastActivity(): number | null {
  try { return Number(window.localStorage.getItem(LAST_ACTIVITY_KEY)) || null; } catch { return null; }
}
