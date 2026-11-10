"use client";
import { useLocale } from "next-intl";
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
  const ar = useLocale() === "ar";
  const fields = [
    ["name", ar ? "الاسم" : "Name", "text", 200],
    ["phone", ar ? "الجوال" : "Phone", "tel", 30],
    ["email", ar ? "البريد الإلكتروني" : "Email", "email", 255],
    ["identity_no", ar ? "رقم الهوية/الإقامة" : "National ID / Iqama", "text", 40],
    ["license_no", ar ? "رقم الرخصة" : "License number", "text", 40],
    ["license_expiry", ar ? "انتهاء الرخصة" : "License expiry", "date", undefined],
  ] as const;
  return <>
    {internal && <p className={s.muted} style={{ gridColumn: "1 / -1" }}>{ar
      ? "الاسم والجوال والبريد والهوية من سجل الموظف، وتُعدَّل من الموارد البشرية."
      : "Name, phone, email and identity come from the employee record. Edit them in Human resources."}</p>}
    {fields.map(([key, label, type, maxLength]) => <label key={key} className={s.field}>{label}
      <input type={type} value={value[key] ?? ""} maxLength={maxLength}
        readOnly={internal && ["name", "phone", "email", "identity_no"].includes(key)}
        required={!internal && (key === "name" || (key === "identity_no" && requireIdentity))}
        onChange={event => onChange(key, event.target.value || null)} />
    </label>)}
    <label className={s.field}>{ar ? "نوع المركبة" : "Vehicle type"}
      <ListSelect list="vehicle_type" value={value.vehicle_type ?? ""} onChange={v => onChange("vehicle_type", v || null)}
        ariaLabel={ar ? "نوع المركبة" : "Vehicle type"} />
    </label>
    <DirectorySelect path="/shipping/directory/vehicles/options" label={ar ? "المركبة المعتادة" : "Default vehicle"}
      value={value.default_vehicle_id} onChange={id => onChange("default_vehicle_id", id || null)} />
    <DirectorySelect path="/shipping/directory/carriers/options" label={ar ? "شركة النقل" : "Carrier"}
      value={value.carrier_id} onChange={id => onChange("carrier_id", id || null)} />
    <label className={s.field}>{ar ? "ملاحظات" : "Notes"}
      <textarea value={value.notes ?? ""} onChange={event => onChange("notes", event.target.value || null)} />
    </label>
  </>;
}
