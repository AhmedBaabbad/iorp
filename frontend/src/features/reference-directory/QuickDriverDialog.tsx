"use client";
import { useState } from "react";
import { useLocale } from "next-intl";
import { Dialog } from "@/components/ui/Dialog";
import { apiClient } from "@/lib/api-client";
import { DriverFields, type DriverDraft } from "./DriverFields";
import type { Option } from "./RecordSelect";
import s from "@/features/production-demands/demands.module.css";

export function QuickDriverDialog({ onClose, onSelect }: { onClose: () => void; onSelect: (driver: Option) => void }) {
  const ar = useLocale() === "ar";
  const [value, setValue] = useState<DriverDraft>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [existing, setExisting] = useState<string | null>(null);
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return;
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
        setError(ar ? "هذا السائق مسجل مسبقًا" : "This driver is already registered");
      } else setError(ar ? "تعذر إضافة السائق. تحقق من الحقول وحاول مجددًا." : "Could not add the driver. Check the fields and try again.");
    } finally { setBusy(false); }
  }
  async function chooseExisting() {
    if (!existing || busy) return;
    setBusy(true);
    try {
      const rows = await apiClient<Option[]>(`/shipping/directory/drivers/options?selected_id=${encodeURIComponent(existing)}`);
      const driver = rows.find(row => row.id === existing);
      if (driver) onSelect(driver);
      else setError(ar ? "السائق غير متاح للاختيار" : "Driver unavailable for selection");
    } catch { setError(ar ? "تعذر تحميل السائق" : "Could not load the driver"); }
    finally { setBusy(false); }
  }
  return <Dialog title={ar ? "سائق جديد" : "New driver"} onClose={onClose} busy={busy} onSubmit={save}
    footer={<><button type="button" className={s.button} disabled={busy} onClick={onClose}>{ar ? "إلغاء" : "Cancel"}</button>
      <button className={`${s.button} ${s.primary}`} type="submit" disabled={busy}>{ar ? "حفظ واختيار" : "Save and select"}</button></>}>
    <fieldset disabled={busy} className={s.grid} style={{ border: 0, padding: 0, margin: 0 }}>
      <DriverFields value={value} onChange={(key, next) => setValue(old => ({ ...old, [key]: next }))} />
    </fieldset>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {existing && <button type="button" className={s.button} disabled={busy} onClick={() => void chooseExisting()}>{ar ? "اختياره" : "Select it"}</button>}
  </Dialog>;
}
