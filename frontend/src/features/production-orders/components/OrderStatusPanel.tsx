"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ReasonDialog } from "@/features/production-demands/reason-dialog";
import { lifecycleErrorCode } from "@/features/production-demands/planning-lifecycle";
import { useFormatter } from "@/hooks/useFormatter";
import { transitionProductionOrder } from "../api/production-orders-api";
import type { OrderLifecycle, ProductionOrderData } from "../types";
import { ProductionOrderStatusBadge } from "./ProductionOrderStatusBadge";
import s from "@/features/production-demands/demands.module.css";

type LifecycleAction = OrderLifecycle["actions"][number];

// Status badge plus the actions the server allows for this user now. The rules live in the backend.
export function OrderStatusPanel({ order, onChanged }: { order: ProductionOrderData; onChanged?: () => void }) {
  const t = useTranslations("production.productionOrders.lifecycle");
  const fmt = useFormatter();
  const [pending, setPending] = useState<LifecycleAction | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lifecycle = order.lifecycle;

  async function run(action: LifecycleAction, reason?: string) {
    setBusy(true); setError("");
    try {
      await transitionProductionOrder(order.id, action.action, { reason, expectedVersion: lifecycle?.status_version });
      setPending(null);
      onChanged?.();
    } catch (e) {
      setError(lifecycleErrorCode(e));
      setPending(null);
    } finally { setBusy(false); }
  }
  const press = (action: LifecycleAction) => (action.requires_reason || action.confirm ? setPending(action) : void run(action));

  return (
    <section className={s.panel} aria-label={t("title")}>
      <div className={s.toolbar} style={{ marginBottom: 12, justifyContent: "space-between" }}>
        <div className={s.actions}>
          <strong>{t("title")}</strong>
          <ProductionOrderStatusBadge status={order.status} />
          {lifecycle?.start_overdue && <span className={`${s.badge} ${s.urgent}`}>{t("startOverdue")}</span>}
          {lifecycle?.finish_overdue && <span className={`${s.badge} ${s.urgent}`}>{t("finishOverdue")}</span>}
        </div>
        <div className={s.actions}>
          {lifecycle?.actions.map((a) => (
            <button key={a.action} type="button" disabled={busy} onClick={() => press(a)}
              className={`${s.button} ${a.action === "cancel" ? s.danger : a.confirm || a.action === "return_to_draft" ? "" : s.primary}`}>
              {t(`actions.${a.action}`)}
            </button>
          ))}
        </div>
      </div>
      <dl className={s.grid} style={{ margin: 0 }}>
        <div><dt className={s.muted}>{t("actualStart")}</dt><dd style={{ margin: "4px 0" }}>{lifecycle?.actual_start_at ? fmt.dateTime(lifecycle.actual_start_at) : "—"}</dd></div>
        <div><dt className={s.muted}>{t("actualEnd")}</dt><dd style={{ margin: "4px 0" }}>{lifecycle?.actual_end_at ? fmt.dateTime(lifecycle.actual_end_at) : "—"}</dd></div>
      </dl>
      {lifecycle?.terminal && <p className={s.muted} style={{ marginBottom: 0 }}>{t("terminalHint")}</p>}
      {error && <p role="alert" className={s.error}>{t(`errors.${t.has(`errors.${error}`) ? error : "request_failed"}`)}</p>}
      {pending && (
        <ReasonDialog
          title={t(`confirm.${pending.action}.title`, { order: order.production_order_number })}
          description={t(`confirm.${pending.action}.text`)}
          confirmLabel={t(`actions.${pending.action}`)}
          reasonRequired={pending.requires_reason}
          danger={pending.action === "cancel"}
          busy={busy}
          onClose={() => setPending(null)}
          onConfirm={(reason) => void run(pending, reason)}
        />
      )}
    </section>
  );
}
