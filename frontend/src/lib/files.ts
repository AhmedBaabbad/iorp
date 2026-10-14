"use client";
/**
 * The one upload policy (PROJECT-FILES-003), read from the server (GET /system/file-policy) so the screens never carry
 * their own numbers. The server checks every upload again; this only answers the user before the file is sent.
 */
import { useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";

export type UploadKind = "logo" | "attachment";
export type KindPolicy = { types: string[]; max_bytes: Record<string, number> };
export type FilePolicy = Record<UploadKind, KindPolicy>;
export type FileProblem = { code: "TOO_LARGE"; limit: number } | { code: "UNSUPPORTED_TYPE" } | { code: "EMPTY" };

let cached: Promise<FilePolicy> | null = null;

export function loadFilePolicy(): Promise<FilePolicy> {
  // Never breaks a screen: a missing or wrong answer only leaves the server to check the file.
  cached ??= Promise.resolve().then(() => apiClient<FilePolicy>("/system/file-policy", { token: null, skipRefresh: true })).then((policy) => {
    if (!policy?.logo?.types || !policy?.attachment?.types) throw new Error("FILE_POLICY_INVALID");
    return policy;
  }).catch((error) => {
    cached = null;  // only a valid policy is kept; the next screen asks again
    throw error;
  });
  return cached;
}

export function useFilePolicy(kind: UploadKind): KindPolicy | null {
  const [policy, setPolicy] = useState<FilePolicy | null>(null);
  useEffect(() => {
    let live = true;
    loadFilePolicy().then((p) => { if (live) setPolicy(p); }).catch(() => {});
    return () => { live = false; };
  }, []);
  return policy?.[kind] ?? null;
}

/** Why a chosen file would be refused, or null. Without the policy yet, the server decides. */
export function fileProblem(file: File, policy: KindPolicy | null): FileProblem | null {
  if (!file.size) return { code: "EMPTY" };
  if (!policy) return null;
  if (!policy.types.includes(file.type)) return { code: "UNSUPPORTED_TYPE" };
  const limit = policy.max_bytes[file.type];
  return limit && file.size > limit ? { code: "TOO_LARGE", limit } : null;
}

/** A size in KB or MB; `unit` names them in the screen's language (common.files.units). */
export function formatBytes(bytes: number, unit: (key: "kb" | "mb") => string): string {
  const [value, key] = bytes >= 1024 * 1024 ? [bytes / (1024 * 1024), "mb" as const] : [bytes / 1024, "kb" as const];
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value)} ${unit(key)}`;
}

const NAMES: Record<string, string> = { "image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WebP", "application/pdf": "PDF" };

/** The types grouped by their limit: [["PNG, JPEG, WebP", 5 MB], ["PDF", 2 MB]]. */
export function limitGroups(policy: KindPolicy): [string, number][] {
  const groups = new Map<number, string[]>();
  for (const type of policy.types) groups.set(policy.max_bytes[type], [...(groups.get(policy.max_bytes[type]) ?? []), NAMES[type] ?? type]);
  return [...groups.entries()].map(([limit, names]) => [names.join(", "), limit]);
}

export const acceptOf = (policy: KindPolicy | null, kind: UploadKind) =>
  (policy?.types ?? (kind === "logo" ? ["image/png", "image/jpeg", "image/webp"] : ["image/png", "image/jpeg", "image/webp", "application/pdf"])).join(",");
