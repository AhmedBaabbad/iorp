"use client";
import { useTranslations } from "next-intl";
import { ListSelect } from "@/features/masterdata";
import { DirectorySelect } from "./RecordSelect";
import s from "@/features/production-demands/demands.module.css";

export type DriverDraft = {
  name?: string | null; phone?: string | null; email?: string | null; identity_no?: string | null;
  license_no?: string | null; license_expiry?: string | null; vehicle_type?: string | null;
  default_vehicle_id?: string | null; carrier_id?: string | null; notes?: string | null;
};

export function DriverFields({ value, onChange, internal = false, requireIdentity = true }: {
  value: DriverDraft; onChange: (key: keyof DriverDraft, value: string | null) => void;
  internal?: boolean; requireIdentity?: boolean;
}) {
  const t=useTranslations("directory");
  const fields = [
    ["name", t("fields.name"), "text", 200],
    ["phone", t("fields.phone"), "tel", 30],
    ["email", t("fields.email"), "email", 255],
    ["identity_no", t("fields.identity_no"), "text", 40],
    ["license_no", t("fields.license_no"), "text", 40],
    ["license_expiry", t("fields.license_expiry"), "date", undefined],
  ] as const;
  return <>
    {internal && <p className={s.muted} style={{ gridColumn: "1 / -1" }}>{t("driver.employeeSourceHint")}</p>}
    {fields.map(([key, label, type, maxLength]) => <label key={key} className={s.field}>{label}
      <input type={type} value={value[key] ?? ""} maxLength={maxLength}
        readOnly={internal && ["name", "phone", "email", "identity_no"].includes(key)}
        required={!internal && (key === "name" || (key === "identity_no" && requireIdentity))}
        onChange={event => onChange(key, event.target.value || null)} />
    </label>)}
    <label className={s.field}>{t("fields.vehicle_type")}
      <ListSelect list="vehicle_type" value={value.vehicle_type ?? ""} onChange={v => onChange("vehicle_type", v || null)}
        ariaLabel={t("fields.vehicle_type")} />
    </label>
    <DirectorySelect path="/shipping/directory/vehicles/options" label={t("fields.default_vehicle_id")}
      value={value.default_vehicle_id} onChange={id => onChange("default_vehicle_id", id || null)} />
    <DirectorySelect path="/shipping/directory/carriers/options" label={t("fields.carrier_id")}
      value={value.carrier_id} onChange={id => onChange("carrier_id", id || null)} />
    <label className={s.field}>{t("fields.notes")}
      <textarea value={value.notes ?? ""} onChange={event => onChange("notes", event.target.value || null)} />
    </label>
  </>;
}
