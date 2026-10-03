"use client";
import { useTranslations } from "next-intl";
import type { DemandStatus } from "./api";
import { ALL_STATUSES, isAll, isDefault, toggle } from "./status-visibility";
import s from "./demands.module.css";

/** A dropdown of status checkboxes: hide any status, or show them all again. */
export function StatusVisibilityPicker({ value, defaults, onChange }: { value: DemandStatus[]; defaults: DemandStatus[]; onChange: (next: DemandStatus[]) => void }) {
  const t = useTranslations("production.demands");
  return (
    <div className={s.field}>
      <span id="demand-status-visibility">{t("statusVisibility.label")}</span>
      <details className={s.picker}>
        <summary aria-labelledby="demand-status-visibility">{isAll(value) ? t("all") : t("statusVisibility.summary", { shown: value.length, total: ALL_STATUSES.length })}</summary>
        <div className={s.pickerMenu} role="group" aria-labelledby="demand-status-visibility">
          {ALL_STATUSES.map(status => {
            const checked = value.includes(status);
            return (
              <label key={status} className={s.pickerOption}>
                <input type="checkbox" checked={checked} disabled={checked && value.length === 1} onChange={() => onChange(toggle(value, status))} />
                {t(`statuses.${status}`)}
              </label>
            );
          })}
          <div className={s.actions}>
            <button type="button" className={s.button} disabled={isAll(value)} onClick={() => onChange([...ALL_STATUSES])}>{t("statusVisibility.showAll")}</button>
            <button type="button" className={s.button} disabled={isDefault(value, defaults)} onClick={() => onChange([...defaults])}>{t("statusVisibility.reset")}</button>
          </div>
        </div>
      </details>
    </div>
  );
}
