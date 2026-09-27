"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { getCustomer } from "@/features/customers";
import { getQuoteById } from "@/features/quotes";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { ApiClientError } from "@/lib/api-client";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { deleteCommercialOrder, getCommercialOrderById } from "../api/commercial-orders-api";
import type { CommercialOrderData } from "../types";
import { CommercialOrderStatusBadge } from "./CommercialOrderStatusBadge";
import { OrderItemsTable } from "./OrderItemsTable";

const styles: Record<string, CSSProperties> = {
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(15, 23, 42, 0.55)",
    backdropFilter: "blur(2px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },
  modal: {
    background: "#ffffff",
    borderRadius: "14px",
    boxShadow: "0 24px 64px rgba(15, 23, 42, 0.28), 0 4px 16px rgba(15, 23, 42, 0.12)",
    padding: "32px",
    maxWidth: "460px",
    width: "90%",
    display: "grid",
    gap: "20px",
  },
  modalIcon: {
    width: "48px",
    height: "48px",
    borderRadius: "50%",
    background: "#fff1f2",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "22px",
    margin: "0 auto",
  },
  modalTitle: {
    fontSize: "18px",
    fontWeight: 700,
    color: "#0f172a",
    margin: 0,
    textAlign: "center" as const,
  },
  modalBody: {
    fontSize: "14px",
    color: "#475569",
    margin: 0,
    lineHeight: "1.7",
    textAlign: "center" as const,
  },
  modalActions: {
    display: "flex",
    gap: "12px",
    justifyContent: "center",
    flexWrap: "wrap" as const,
  },
  modalCancelButton: {
    ...sharedStyles.secondaryButton,
    minHeight: "40px",
    padding: "10px 24px",
    fontSize: "14px",
  },
  modalDeleteButton: {
    background: "#be123c",
    border: "none",
    borderRadius: "8px",
    color: "#ffffff",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: 600,
    minHeight: "40px",
    padding: "10px 24px",
  },
  headerActions: {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap" as const,
  },
  deleteButton: {
    ...sharedStyles.secondaryButton,
    borderColor: "#fecdd3",
    color: "#be123c",
  },
  detailGrid: {
    display: "grid",
    gap: "1px",
    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
    background: "#e4e7ec",
    borderRadius: "8px",
    overflow: "hidden",
  },
  detailItem: {
    background: "#ffffff",
    padding: "18px",
  },
  detailLabel: {
    color: "#52606d",
    fontSize: "13px",
    fontWeight: 700,
    margin: "0 0 8px",
  },
  detailValue: {
    margin: 0,
    overflowWrap: "anywhere",
  },
  sections: {
    display: "grid",
    gap: "24px",
  },
};

export function CommercialOrderDetail() {
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const t = useTranslations("commercial.commercialOrders");
  const fmt = useFormatter();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const orderId = params.id;
  const [order, setOrder] = useState<CommercialOrderData | null>(null);
  const [customerName, setCustomerName] = useState<string | null>(null);
  const [quoteNumber, setQuoteNumber] = useState<string | null>(null);
  const [quoteCurrency, setQuoteCurrency] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteSuccessRedirect, setDeleteSuccessRedirect] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadOrder() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const response = await getCommercialOrderById(orderId);

        if (isMounted) {
          setOrder(response);
        }

        const secondaryFetches: Promise<void>[] = [
          getCustomer(response.customer_id)
            .then((customer) => {
              if (isMounted) {
                setCustomerName(customer.name);
              }
            })
            .catch(() => undefined),
        ];

        if (response.quote_id) {
          secondaryFetches.push(
            getQuoteById(response.quote_id)
              .then((quote) => {
                if (isMounted) {
                  setQuoteNumber(quote.quote_number);
                  setQuoteCurrency(quote.currency);
                }
              })
              .catch(() => undefined),
          );
        }

        await Promise.all(secondaryFetches);
      } catch (caughtError) {
        if (!isMounted) {
          return;
        }

        if (caughtError instanceof ApiClientError && caughtError.status === 404) {
          setIsNotFound(true);
          return;
        }

        setError(getApiErrorMessage(caughtError, messages));
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadOrder();

    return () => {
      isMounted = false;
    };
  }, [orderId]);

  async function handleConfirmDelete() {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deleteCommercialOrder(orderId);
      setDeleteSuccessRedirect("/commercial-orders");
    } catch (caughtError) {
      setDeleteError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsDeleting(false);
      setShowDeleteConfirm(false);
    }
  }

  return (
    <>
      {deleteSuccessRedirect ? (
        <SuccessModal
          message={t("deleteSuccess")}
          okLabel={common("actions.ok")}
          onOk={() => router.replace(deleteSuccessRedirect)}
        />
      ) : null}

      {showDeleteConfirm ? (
        <div style={styles.backdrop} onClick={() => setShowDeleteConfirm(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalIcon}>!</div>
            <h2 style={styles.modalTitle}>{t("deleteConfirmTitle")}</h2>
            <p style={styles.modalBody}>{t("deleteConfirm")}</p>
            {deleteError ? (
              <div style={sharedStyles.error} role="alert">
                {deleteError}
              </div>
            ) : null}
            <div style={styles.modalActions}>
              <button
                type="button"
                style={styles.modalCancelButton}
                onClick={() => setShowDeleteConfirm(false)}
                disabled={isDeleting}
              >
                {common("actions.cancel")}
              </button>
              <button
                type="button"
                style={styles.modalDeleteButton}
                onClick={() => void handleConfirmDelete()}
                disabled={isDeleting}
              >
                {common("actions.delete")}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <PageFrame
        title={order?.order_number ?? t("detailTitle")}
        subtitle={t("detailSubtitle")}
        action={
          <div style={styles.headerActions}>
            {order ? (
              <Link
                href={`/commercial-orders/${orderId}/edit`}
                style={sharedStyles.secondaryButton}
              >
                {common("actions.edit")}
              </Link>
            ) : null}
            {order ? (
              <button
                type="button"
                style={styles.deleteButton}
                onClick={() => setShowDeleteConfirm(true)}
              >
                {common("actions.delete")}
              </button>
            ) : null}
            <Link href="/commercial-orders" style={sharedStyles.secondaryButton}>
              {t("backToList")}
            </Link>
          </div>
        }
      >
        {isLoading ? (
          <div style={{ ...sharedStyles.state, background: "#ffffff" }}>{messages("loading.default")}</div>
        ) : null}

        {!isLoading && isNotFound ? (
          <section style={{ ...sharedStyles.state, background: "#ffffff" }}>
            <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("notFound")}</h2>
            <p style={{ margin: "0 0 18px" }}>{t("notFoundDescription")}</p>
            <Link href="/commercial-orders" style={sharedStyles.button}>
              {t("returnToList")}
            </Link>
          </section>
        ) : null}

        {!isLoading && error ? (
          <div style={sharedStyles.error} role="alert">
            {error}
          </div>
        ) : null}

        {!isLoading && !error && !isNotFound && order ? (
          <div style={styles.sections}>
            {order.status === "converted_to_production" ? (
              <div style={{ ...sharedStyles.state, background: "#ffffff" }}>
                {t("productionConvertedNotice")}
              </div>
            ) : null}

            <section style={styles.detailGrid} aria-label={t("detailsAria")}>
              <DetailItem
                label={t("fields.orderNumber")}
                value={`${order.order_number} (${t("autoGeneratedNumber")})`}
              />
              <DetailItem
                label={t("fields.status")}
                value={<CommercialOrderStatusBadge status={order.status} />}
              />
              <DetailItem
                label={t("fields.customer")}
                value={
                  <Link href={`/customers/${order.customer_id}`} style={{ color: "#1d4ed8" }}>
                    {customerName ?? order.customer_id}
                  </Link>
                }
              />
              <DetailItem
                label={t("fields.quote")}
                value={
                  order.quote_id ? (
                    <Link href={`/quotes/${order.quote_id}`} style={{ color: "#1d4ed8" }}>
                      {quoteNumber ?? order.quote_id}
                    </Link>
                  ) : null
                }
              />
              <DetailItem label={t("fields.orderDate")} value={fmt.date(order.order_date)} />
              <DetailItem
                label={t("fields.requestedDelivery")}
                value={
                  order.requested_delivery_date
                    ? fmt.date(order.requested_delivery_date)
                    : null
                }
              />
              <DetailItem label={t("fields.notes")} value={order.notes} />
            </section>

            <OrderItemsTable items={order.items} currency={quoteCurrency} />

            <section style={{ ...sharedStyles.state, background: "#ffffff" }}>
              {order.quote_id
                ? t("totalsInheritedNotice")
                : t("noQuoteTotalsNotice")}
            </section>
          </div>
        ) : null}
      </PageFrame>
    </>
  );
}

function DetailItem({
  label,
  value,
}: {
  label: string;
  value: string | number | null | ReactNode;
}) {
  return (
    <div style={styles.detailItem}>
      <p style={styles.detailLabel}>{label}</p>
      <p style={styles.detailValue}>
        {typeof value === "string" || typeof value === "number" || value === null
          ? displayValue(value)
          : value}
      </p>
    </div>
  );
}
