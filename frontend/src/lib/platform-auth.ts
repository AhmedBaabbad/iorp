const PLATFORM_ACCESS_TOKEN_KEY = "iorp.platform_access_token";

function canUseBrowserStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function getStoredPlatformToken() {
  if (!canUseBrowserStorage()) {
    return null;
  }

  return window.localStorage.getItem(PLATFORM_ACCESS_TOKEN_KEY);
}

export function storePlatformToken(token: string) {
  if (!canUseBrowserStorage()) {
    return;
  }

  window.localStorage.setItem(PLATFORM_ACCESS_TOKEN_KEY, token);
}

export function removeStoredPlatformToken() {
  if (!canUseBrowserStorage()) {
    return;
  }

  window.localStorage.removeItem(PLATFORM_ACCESS_TOKEN_KEY);
}
