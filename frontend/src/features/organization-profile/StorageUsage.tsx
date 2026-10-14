"use client";
/** What the organization's files occupy against its quota (PROJECT-FILES-003): a warning from 80 %, uploads refused at 100 %. */
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { apiClient } from "@/lib/api-client";
import { formatBytes } from "@/lib/files";

type Storage = { used_bytes: number; quota_bytes: number; percent: number };

export function StorageUsage() {
  const t = useTranslations("common.files");
  const [storage, setStorage] = useState<Storage | null>(null);
  useEffect(() => {
    let live = true;
    apiClient<Storage>("/organization/storage").then((s) => { if (live) setStorage(s); }).catch(() => {});
    return () => { live = false; };
  }, []);
  if (!storage) return null;
  const tone = storage.percent >= 100 ? "var(--danger)" : storage.percent >= 80 ? "var(--warning)" : "var(--text-muted)";
  return <div style={{ display: "grid", gap: 6, marginBottom: 12 }}>
    <strong>{t("storage")}</strong>
    <div role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(100, storage.percent)} aria-label={t("storage")}
      style={{ height: 8, borderRadius: 4, background: "var(--surface-muted)", overflow: "hidden" }}>
      <div style={{ width: `${Math.min(100, storage.percent)}%`, height: "100%", background: tone }} />
    </div>
    <span style={{ color: tone, fontSize: 13 }}>{t("storageUsage", { used: formatBytes(storage.used_bytes, (key) => t(`units.${key}`)), quota: formatBytes(storage.quota_bytes, (key) => t(`units.${key}`)), percent: storage.percent })}</span>
    {storage.percent >= 100 ? <span role="alert" style={{ color: tone, fontSize: 13 }}>{t("storageFull")}</span>
      : storage.percent >= 80 ? <span role="status" style={{ color: tone, fontSize: 13 }}>{t("storageNearlyFull")}</span> : null}
  </div>;
}
