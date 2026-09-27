"use client";

import type { CSSProperties } from "react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { SectionShell } from "@/components/layout/section-shell";
import { useFormatter } from "@/hooks/useFormatter";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { getItemsByOrder } from "../api/production-order-items-api";
import type { ProductionOrderItemListItem } from "../types";
import { ProductionOrderItemForm } from "./ProductionOrderItemForm";
import { formatStatus, isReadOnlyStatus } from "./production-order-items-utils";

type ProductionOrderItemsListProps = {
  productionOrderId: string;
  productionOrderStatus: string;
};

const styles: Record<string, CSSProperties> = {
  itemMetaRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
    alignItems: "center",
  },
  specs: {
    display: "flex",
    flexWrap: "wrap",
    gap: "6px",
    marginTop: "10px",
  },
  specChip: {
    ...sharedStyles.badge,
    background: "#eef2ff",
    color: "#3730a3",
    textTransform: "none",
  },
};

export function ProductionOrderItemsList({
  productionOrderId,
  productionOrderStatus,
}: ProductionOrderItemsListProps) {
  const t = useTranslations("production.productionOrders.items");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [items, setItems] = useState<ProductionOrderItemListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(true);
  const isReadOnly = isReadOnlyStatus(productionOrderStatus);

  const loadItems = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await getItemsByOrder(productionOrderId);
      if (isMountedRef.current) {
        setItems(response);
      }
    } catch (caughtError) {
      if (isMountedRef.current) {
        setError(getApiErrorMessage(caughtError, messages));
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [productionOrderId, t]);

  useEffect(() => {
    isMountedRef.current = true;
    void loadItems();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadItems]);

  return (
    <SectionShell
      titleId="production-order-items-title"
      title={t("sectionTitle")}
      subtitle={t("sectionSubtitle")}
    >
      {isReadOnly ? (
        <div style={sharedStyles.state}>
          {t("statusGuardMessage", { status: formatStatus(productionOrderStatus) })}
        </div>
      ) : (
        <ProductionOrderItemForm
          productionOrderId={productionOrderId}
          productionOrderStatus={productionOrderStatus}
          onCreated={loadItems}
        />
      )}

      {isLoading ? <div style={sharedStyles.state}>{t("loading")}</div> : null}

      {!isLoading && error ? (
        <div style={{ display: "grid", gap: "12px" }}>
          <div style={sharedStyles.error} role="alert">
            {error}
          </div>
          <button
            style={{ ...sharedStyles.secondaryButton, width: "fit-content" }}
            type="button"
            onClick={() => void loadItems()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && items.length === 0 ? (
        <div style={sharedStyles.state}>{t("emptyAdded")}</div>
      ) : null}

      {!isLoading && !error && items.length > 0 ? (
        <div style={sharedStyles.list}>
          {items.map((item) => (
            <article key={item.id} style={sharedStyles.item}>
              <div style={sharedStyles.itemHeader}>
                <div>
                  <h3 style={sharedStyles.itemTitle}>{t("lineTitle", { lineNo: item.line_no })}</h3>
                  <div style={styles.itemMetaRow}>
                    <span style={sharedStyles.meta}>
                      {fmt.quantity(item.planned_quantity, item.unit)}
                    </span>
                  </div>
                </div>
              </div>

              {item.target_spec_json && Object.keys(item.target_spec_json).length > 0 ? (
                <div style={styles.specs} aria-label={t("lineSpecsAria", { lineNo: item.line_no })}>
                  {Object.entries(item.target_spec_json).map(([key, value]) => (
                    <span key={key} style={styles.specChip}>
                      {key}: {formatSpecValue(value)}
                    </span>
                  ))}
                </div>
              ) : null}

              <p style={sharedStyles.text}>{displayValue(truncateText(item.notes, 160))}</p>
            </article>
          ))}
        </div>
      ) : null}
    </SectionShell>
  );
}

function truncateText(value: string | null | undefined, maxLength: number) {
  if (!value || value.length <= maxLength) {
    return value ?? null;
  }

  return `${value.slice(0, maxLength - 1)}...`;
}

function formatSpecValue(value: unknown) {
  if (value === null || value === undefined) {
    return "-";
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}
