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
    ["name", t("copy.driverfields0"), "text", 200],
    ["phone", t("copy.driverfields1"), "tel", 30],
    ["email", t("copy.driverfields2"), "email", 255],
    ["identity_no", t("copy.driverfields3"), "text", 40],
    ["license_no", t("copy.driverfields4"), "text", 40],
    ["license_expiry", t("copy.driverfields5"), "date", undefined],
  ] as const;
  return <>
    {internal && <p className={s.muted} style={{ gridColumn: "1 / -1" }}>{t("copy.driverfields6")}</p>}
    {fields.map(([key, label, type, maxLength]) => <label key={key} className={s.field}>{label}
      <input type={type} value={value[key] ?? ""} maxLength={maxLength}
        readOnly={internal && ["name", "phone", "email", "identity_no"].includes(key)}
        required={!internal && (key === "name" || (key === "identity_no" && requireIdentity))}
        onChange={event => onChange(key, event.target.value || null)} />
    </label>)}
    <label className={s.field}>{t("copy.driverfields7")}
      <ListSelect list="vehicle_type" value={value.vehicle_type ?? ""} onChange={v => onChange("vehicle_type", v || null)}
        ariaLabel={t("copy.driverfields8")} />
    </label>
    <DirectorySelect path="/shipping/directory/vehicles/options" label={t("copy.driverfields9")}
      value={value.default_vehicle_id} onChange={id => onChange("default_vehicle_id", id || null)} />
    <DirectorySelect path="/shipping/directory/carriers/options" label={t("copy.driverfields10")}
      value={value.carrier_id} onChange={id => onChange("carrier_id", id || null)} />
    <label className={s.field}>{t("copy.driverfields11")}
      <textarea value={value.notes ?? ""} onChange={event => onChange("notes", event.target.value || null)} />
    </label>
  </>;
}
