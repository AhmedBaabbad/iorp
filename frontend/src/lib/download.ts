import { API_BASE_URL } from "@/lib/api-client";
import { getStoredAccessToken } from "@/lib/auth";

/** A file the server builds on request (an Excel export), saved by the browser; nothing is kept on the server. */
export class DownloadError extends Error {
  constructor(public status: number, public code: string | null) {
    super("download_failed");
  }
}

function filenameOf(header: string | null, fallback: string) {
  const encoded = header?.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (encoded) return decodeURIComponent(encoded);
  return header?.match(/filename="([^"]+)"/i)?.[1] ?? fallback;
}

export async function downloadFile(path: string, fallbackName: string) {
  const response = await fetch(`${API_BASE_URL.replace(/\/$/, "")}/api/v1${path}`, {
    headers: { Authorization: `Bearer ${getStoredAccessToken() ?? ""}` },
    credentials: "include",
  });
  if (!response.ok) {
    let code: string | null = null;
    try { code = (await response.json())?.detail?.code ?? null; } catch { /* not JSON */ }
    throw new DownloadError(response.status, code);
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filenameOf(response.headers.get("content-disposition"), fallbackName);
  link.click();
  URL.revokeObjectURL(url);
}
