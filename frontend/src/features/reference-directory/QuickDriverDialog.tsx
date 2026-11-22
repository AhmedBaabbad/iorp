"use client";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { RecordDialog } from "@/components/ui/RecordDialog";
import { apiClient } from "@/lib/api-client";
import { DriverFields, type DriverDraft } from "./DriverFields";
import type { Option } from "./RecordSelect";
import s from "@/features/production-demands/demands.module.css";

export function QuickDriverDialog({ onClose, onSelect }: { onClose: () => void; onSelect: (driver: Option) => void }) {
  const t=useTranslations("directory");
  const [value, setValue] = useState<DriverDraft>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [existing, setExisting] = useState<string | null>(null);
  async function save() {
    if (busy) return false;
    setBusy(true); setError(""); setExisting(null);
    try {
      const row = await apiClient<Option>("/shipping/directory/drivers/quick", {
        method: "POST", notify: false, body: { ...value, affiliation: "external" },
      });
      onSelect(row);
    } catch (caught) {
      const details = (caught as { status?: number; details?: { detail?: { code?: string; existing_driver_id?: string } } });
      if (details.status === 409 && details.details?.detail?.code === "DRIVER_IDENTITY_EXISTS") {
        setExisting(details.details.detail.existing_driver_id ?? null);
        setError(t("driverExists"));
      } else setError(t("driver.addFailed"));
      return false;
    } finally { setBusy(false); }
  }
  async function chooseExisting() {
    if (!existing || busy) return;
    setBusy(true);
    try {
      const rows = await apiClient<Option[]>(`/shipping/directory/drivers/options?selected_id=${encodeURIComponent(existing)}`);
      const driver = rows.find(row => row.id === existing);
      if (driver) onSelect(driver);
      else setError(t("driverUnavailable"));
    } catch { setError(t("driver.loadFailed")); }
    finally { setBusy(false); }
  }
  return <RecordDialog title={t("newDriver")} onClose={onClose} onSave={save} error={error} saveLabel={t("saveSelect")}>
    <fieldset disabled={busy} className={s.grid} style={{ border: 0, padding: 0, margin: 0 }}>
      <DriverFields value={value} onChange={(key, next) => setValue(old => ({ ...old, [key]: next }))} />
    </fieldset>
    {existing && <button type="button" className={s.button} disabled={busy} onClick={() => void chooseExisting()}>{t("selectExisting")}</button>}
  </RecordDialog>;
}
