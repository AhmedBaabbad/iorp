"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { Money, pricePlaces } from "@/components/money/Money";
import { getCustomer } from "@/features/customers";
import { useProductName } from "@/features/masterdata";
import { ReasonDialog } from "@/features/production-demands/reason-dialog";
import s from "@/features/production-demands/demands.module.css";
import { getQuoteById } from "@/features/quotes";
import { useFormatter } from "@/hooks/useFormatter";
import { ApiClientError } from "@/lib/api-client";
import {
  cancelCommercialOrder,
  confirmCommercialOrder,
  deleteCommercialOrder,
  getCommercialOrderById,
  reviseCommercialOrder,
} from "../api/commercial-orders-api";
import type { CommercialOrderData } from "../types";
import { CommercialOrderStatusBadge } from "./CommercialOrderStatusBadge";
import { SpecList, StatusHistory, salesErrorMessage } from "./sales-lifecycle";
import { Signatures } from "@/components/Signatures";

/**
 * One sales order (SALES-001): its source (an accepted quotation or the customer's reference), the lines with what was
 * sent to production and what remains, the next step (confirm, send to production, revise, cancel) and its history.
 */
export function CommercialOrderDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const t = useTranslations("commercial.commercialOrders");
  const errors = useTranslations("commercial.salesErrors");
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const currencies = useTranslations("common.currencies");
  const units = useTranslations("common.units.units");
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const fmt = useFormatter();
  const productName = useProductName();
  const [order, setOrder] = useState<CommercialOrderData | null>(null);
  const [customerName, setCustomerName] = useState("");
  const [quoteNumber, setQuoteNumber] = useState("");
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);
  const [dialog, setDialog] = useState<"revise" | "cancel" | "delete" | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const found = await getCommercialOrderById(id);
      setOrder(found);
      getCustomer(found.customer_id).then((c) => setCustomerName(c.name)).catch(() => undefined);
      if (found.quote_id) getQuoteById(found.quote_id).then((q) => setQuoteNumber(q.quote_number)).catch(() => undefined);
    } catch (e) {
      if (e instanceof ApiClientError && e.status === 404) setMissing(true);
      else setError(salesErrorMessage(e, errors, messages));
    } finally { setLoading(false); }
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, [load]);

  async function run(key: string, action: () => Promise<CommercialOrderData | void>) {
    setBusy(key); setError("");
    try {
      const result = await action();
      if (result) setOrder(result);
      setDialog(null);
    } catch (e) { setError(salesErrorMessage(e, errors, messages)); } finally { setBusy(null); }
  }

  const back = <Link href="/commercial-orders" className={s.button}>{t("backToList")}</Link>;
  if (loading) return <PageFrame title={t("detailTitle")} action={back}><p className={s.muted}>{messages("loading.default")}</p></PageFrame>;
  if (missing || !order) {
    return <PageFrame title={t("detailTitle")} action={back}><p role="alert" className={s.error}>{error || t("notFound")}</p></PageFrame>;
  }

  const actions = order.allowed_actions ?? [];
  const sent = order.transferred_quantities ?? {};
  const currency = order.currency ?? "";
  const priced = order.items.some((i) => i.agreed_unit_price != null);
  const total = order.items.reduce((sum, i) => sum + Number(i.line_total ?? 0), 0);
  const showSent = order.status !== "draft";

  return (
    <PageFrame title={order.order_number} subtitle={customerName || t("detailSubtitle")} action={back}>
      {error && <p role="alert" className={s.error}>{error}</p>}
      <section className={s.panel}>
        <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 12 }}>
          <span className={s.actions}>
            <CommercialOrderStatusBadge status={order.status} />
            <span className={s.badge}>{t("revisionBadge", { number: order.revision ?? 1 })}</span>
            {order.status === "confirmed" && <span className={s.badge}>{t(`fulfilment.${order.fulfilment ?? "none"}`)}</span>}
          </span>
          <span className={s.actions}>
            {actions.includes("edit") && <Link href={`/commercial-orders/${order.id}/edit`} className={s.button}>{common("actions.edit")}</Link>}
            {actions.includes("confirm") && (
              <button type="button" className={`${s.button} ${s.primary}`} disabled={busy !== null}
                onClick={() => void run("confirm", () => confirmCommercialOrder(order.id))}>
                {busy === "confirm" ? messages("loading.saving") : t("lifecycle.actions.confirm")}
              </button>
            )}
            {order.confirm_blocked_reason === "preparer" && <div>
              <button type="button" className={`${s.button} ${s.primary}`} disabled title={errors("ORDER_CONFIRMER_IS_PREPARER")}>
                {t("lifecycle.actions.confirm")}
              </button>
              <small style={{ display: "block", maxWidth: 360, color: "var(--text-muted)" }}>{errors("ORDER_CONFIRMER_IS_PREPARER")}</small>
            </div>}
            {actions.includes("transfer") && (
              <Link href={`/production/demands/new?sales_order=${order.id}&customer=${order.customer_id}`} className={`${s.button} ${s.primary}`}>
                {t("lifecycle.actions.transfer")}
              </Link>
            )}
            {actions.includes("revise") && (
              <button type="button" className={s.button} disabled={busy !== null} onClick={() => setDialog("revise")}>{t("lifecycle.actions.revise")}</button>
            )}
            {actions.includes("cancel") && (
              <button type="button" className={`${s.button} ${s.danger}`} disabled={busy !== null} onClick={() => setDialog("cancel")}>
                {t("lifecycle.actions.cancel")}
              </button>
            )}
            {actions.includes("delete") && (
              <button type="button" className={s.button} disabled={busy !== null} onClick={() => setDialog("delete")}>{common("actions.delete")}</button>
            )}
          </span>
        </div>
        <p className={s.muted} style={{ marginTop: 0 }}>{t(`lifecycle.hints.${order.status}`)}</p>
        <dl className={s.grid} style={{ margin: 0 }}>
          <Item label={t("fields.customer")}><Link href={`/customers/${order.customer_id}`}>{customerName || "—"}</Link></Item>
          <Item label={t("fields.source")}>
            {order.quote_id
              ? <>{t("sources.quote")}: <Link href={`/quotes/${order.quote_id}`}><bdi>{quoteNumber || "…"}</bdi></Link></>
              : t("sources.direct")}
          </Item>
          <Item label={t("fields.customerReference")}><bdi>{order.customer_reference || "—"}</bdi></Item>
          <Item label={t("fields.orderDate")}>{fmt.date(order.order_date)}</Item>
          <Item label={t("fields.requestedDelivery")}>{order.requested_delivery_date ? fmt.date(order.requested_delivery_date) : "—"}</Item>
          <Item label={t("fields.currency")}>{currency ? currencies(currency) : "—"}</Item>
          <Item label={t("fields.confirmedAt")}>{order.confirmed_at ? fmt.dateTime(order.confirmed_at) : "—"}</Item>
        </dl>
      </section>

      <section className={s.panel} aria-label={t("items.sectionTitle")}>
        <h2 style={{ marginTop: 0 }}>{t("items.sectionTitle")}</h2>
        <div className={s.tableWrap}>
          <table className={s.table}>
            <thead>
              <tr>
                <th>#</th><th>{t("items.fields.productType")}</th><th>{t("items.fields.quantity")}</th>
                {showSent && <><th>{t("items.fields.sent")}</th><th>{t("items.fields.remaining")}</th></>}
                <th>{t("items.fields.unitPrice")}</th><th>{t("items.fields.lineTotal")}</th>
              </tr>
            </thead>
            <tbody>
              {[...order.items].sort((a, b) => a.line_no - b.line_no).map((item) => {
                const taken = Number(sent[item.id ?? ""] ?? 0);
                const left = Math.max(0, Number(item.quantity) - taken);
                return (
                  <tr key={item.id ?? item.line_no}>
                    <td>{item.line_no}</td>
                    <td>{productName(item.product_type)}<SpecList productKey={item.product_type} spec={item.requested_spec_json} /></td>
                    <td><bdi>{fmt.quantity(item.quantity, unit(item.unit))}</bdi></td>
                    {showSent && <>
                      <td><bdi>{fmt.quantity(String(taken), unit(item.unit))}</bdi></td>
                      <td className={left > 0 ? undefined : s.muted}><bdi>{fmt.quantity(String(left), unit(item.unit))}</bdi></td>
                    </>}
                    <td>{item.agreed_unit_price != null && currency ? <Money amount={item.agreed_unit_price} currency={currency} places={pricePlaces(item.agreed_unit_price)} /> : "—"}</td>
                    <td>{item.line_total != null && currency ? <Money amount={item.line_total} currency={currency} /> : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {priced && currency && <p style={{ marginBottom: 0 }}><strong>{t("fields.total")}:</strong> <Money amount={total} currency={currency} /></p>}
      </section>

      {order.notes && <section className={s.panel}><p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{order.notes}</p></section>}
      <StatusHistory entries={order.history ?? []} />

      {dialog === "revise" && (
        <ReasonDialog title={t("lifecycle.reviseTitle")} description={t("lifecycle.reviseText")} confirmLabel={t("lifecycle.actions.revise")}
          busy={busy !== null} onClose={() => setDialog(null)} onConfirm={(reason) => void run("revise", () => reviseCommercialOrder(order.id, reason))} />
      )}
      {dialog === "cancel" && (
        <ReasonDialog title={t("lifecycle.cancelTitle")} description={t("lifecycle.cancelText")} confirmLabel={t("lifecycle.actions.cancel")} danger
          busy={busy !== null} onClose={() => setDialog(null)} onConfirm={(reason) => void run("cancel", () => cancelCommercialOrder(order.id, reason))} />
      )}
      {dialog === "delete" && (
        <div className={s.overlay}>
          <div role="dialog" aria-modal="true" aria-label={t("delete.confirmTitle")} className={`${s.panel} ${s.dialog}`}>
            <h2 style={{ margin: 0 }}>{t("delete.confirmTitle")}</h2>
            <p className={s.muted}>{t("delete.confirmMessage")} {t("delete.itemsCount", { count: order.items.length })}</p>
            <div className={s.actions}>
              <button type="button" className={s.button} disabled={busy !== null} onClick={() => setDialog(null)}>{t("delete.cancel")}</button>
              <button type="button" className={`${s.button} ${s.danger}`} disabled={busy !== null}
                onClick={() => void run("delete", async () => { await deleteCommercialOrder(order.id); router.replace("/commercial-orders"); })}>
                {busy === "delete" ? t("delete.deleting") : t("delete.confirm")}
              </button>
            </div>
          </div>
        </div>
      )}
          <Signatures resourceType="sales_order" id={order.id} version={order.status} />
</PageFrame>
  );
}

function Item({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt className={s.muted}>{label}</dt><dd style={{ margin: "4px 0 0" }}>{children}</dd></div>;
}
