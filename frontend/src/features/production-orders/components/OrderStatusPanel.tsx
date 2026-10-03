"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { usePermission } from "@/features/auth/permission-hooks";
import { ReasonDialog } from "@/features/production-demands/reason-dialog";
import { CloseResultDialog } from "@/features/production-results";
import { lifecycleErrorCode } from "@/features/production-demands/planning-lifecycle";
import { useFormatter } from "@/hooks/useFormatter";
import { transitionProductionOrder } from "../api/production-orders-api";
import type { OrderLifecycle, ProductionOrderData } from "../types";
import { ProductionOrderStatusBadge } from "./ProductionOrderStatusBadge";
import s from "@/features/production-demands/demands.module.css";
import { P } from "@/lib/production-permissions";

type LifecycleAction = OrderLifecycle["actions"][number];

// Status badge plus the actions the server allows for this user now. The rules live in the backend.
export function OrderStatusPanel({ order, onChanged }: { order: ProductionOrderData; onChanged?: () => void }) {
  const t = useTranslations("production.productionOrders.lifecycle");
  const fmt = useFormatter();
  const [pending, setPending] = useState<LifecycleAction | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // CLOSE_BLOCKED lists what other modules still need done (quality checks open, rejections undecided).
  const [blockers, setBlockers] = useState<{ code: string; count: number }[]>([]);
  const lifecycle = order.lifecycle;
  // Closing shows the final result first when the user may read it; zero output is offered either way.
  const canReadResult = usePermission(P.RESULTS_READ);

  async function run(action: LifecycleAction, reason?: string, zeroOutput = false) {
    setBusy(true); setError(""); setBlockers([]);
    try {
      await transitionProductionOrder(order.id, action.action, { reason, expectedVersion: lifecycle?.status_version, zeroOutput });
      setPending(null);
      onChanged?.();
    } catch (e) {
      setError(lifecycleErrorCode(e));
      setBlockers((e as { details?: { detail?: { blockers?: { code: string; count: number }[] } } }).details?.detail?.blockers ?? []);
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
      {error && <div role="alert" className={s.error}>
        {t(`errors.${t.has(`errors.${error}`) ? error : "request_failed"}`)}
        {blockers.length > 0 && <ul style={{ margin: "6px 0 0" }}>{blockers.map(b => <li key={b.code}>
          {t.has(`blockers.${b.code}`) ? t(`blockers.${b.code}`, { count: String(b.count) }) : b.code}
        </li>)}</ul>}
      </div>}
      {pending?.action === "close" && (
        <CloseResultDialog orderId={order.id} orderNumber={order.production_order_number} busy={busy} error="" canReadResult={canReadResult}
          onClose={() => setPending(null)} onConfirm={({ reason, zeroOutput }) => void run(pending, reason, zeroOutput)} />
      )}
      {pending && pending.action !== "close" && (
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
