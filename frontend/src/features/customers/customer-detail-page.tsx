"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useEffect, useState } from "react";

import { CustomerFollowUpsSection } from "@/features/followups";
import { CustomerInteractionsSection } from "@/features/interactions";
import { useFormatter } from "@/hooks/useFormatter";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import type { CustomerDeletionImpact, CustomerDetail, SalesOwnerSummary } from "@/types/customers";
import { deleteCustomer, getCustomer, getCustomerDeletionImpact } from "./customer-api";
import { CustomerReportButtons } from "@/features/reports/CustomerReportButtons";
import { PermissionGuard } from "@/components/PermissionGuard";
import { CustomerDirectory } from "@/features/reference-directory/DirectoryPanel";
import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth";
import { useListName } from "@/features/masterdata";

const styles: Record<string, CSSProperties> = {
  detailGrid: {
    display: "grid",
    gap: "1px",
    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
    background: "var(--border)",
    borderRadius: "8px",
    overflow: "hidden",
  },
  detailItem: {
    background: "var(--surface)",
    padding: "18px",
  },
  detailLabel: {
    color: "var(--text-muted)",
    fontSize: "13px",
    fontWeight: 700,
    margin: "0 0 8px",
  },
  detailValue: {
    margin: 0,
    overflowWrap: "anywhere",
  },
  relatedSections: {
    display: "grid",
    gap: "24px",
  },
  overlay: {
    position: "fixed",
    inset: 0,
    background: "var(--overlay)",
    display: "grid",
    placeItems: "center",
    zIndex: 50,
    padding: "24px",
  },
  modal: {
    background: "var(--surface)",
    borderRadius: "8px",
    padding: "28px 32px",
    width: "100%",
    maxWidth: "440px",
    boxShadow: "0 20px 60px rgba(0,0,0,0.2)",
  },
  modalTitle: {
    margin: "0 0 12px",
    fontSize: "18px",
    fontWeight: 700,
    color: "var(--text)",
  },
  modalBody: {
    margin: "0 0 20px",
    color: "var(--text-muted)",
    fontSize: "14px",
    lineHeight: 1.6,
  },
  impactList: {
    margin: "10px 0 0",
    padding: "12px 16px",
    background: "var(--surface-muted)",
    borderRadius: "6px",
    listStyle: "none",
    display: "grid",
    gap: "4px",
  },
  impactItem: {
    fontSize: "13px",
    color: "var(--text-muted)",
  },
  modalActions: {
    display: "flex",
    gap: "12px",
    justifyContent: "flex-end",
  },
  deleteButton: {
    padding: "8px 18px",
    background: "var(--danger)",
    color: "var(--on-accent)",
    border: "none",
    borderRadius: "6px",
    fontWeight: 600,
    fontSize: "14px",
    cursor: "pointer",
  },
  deleteButtonDisabled: {
    padding: "8px 18px",
    background: "var(--surface-muted)",
    color: "var(--text-subtle)",
    border: "none",
    borderRadius: "6px",
    fontWeight: 600,
    fontSize: "14px",
    cursor: "not-allowed",
  },
};

function formatSalesOwner(owner: SalesOwnerSummary): string {
  const roleName = owner.roles[0]?.name;
  const base = roleName ? `${owner.full_name} — ${roleName}` : owner.full_name;
  return owner.workforce ? `${base} (${owner.workforce.employee_code})` : base;
}

export function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const t = useTranslations("commercial.customers");
  const tEnums = useTranslations();
  const messages = useTranslations("messages");
  // MD-002: list values by their names, not their keys
  const sectorName = useListName("sector");
  const cityName = useListName("city");
  const countryName = useListName("country");
  const sourceName = useListName("opportunity_source");
  const fmt = useFormatter();
  const customerId = params.id;
  const router = useRouter();
  const canDeleteCustomer = usePermission("commercial:customers:delete");
  const [customer, setCustomer] = useState<CustomerDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const [deleteImpact, setDeleteImpact] = useState<CustomerDeletionImpact | null>(null);
  const [deletePhase, setDeletePhase] = useState<"idle" | "loading" | "confirm" | "deleting">("idle");
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadCustomer() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const response = await getCustomer(customerId);

        if (isMounted) {
          setCustomer(response);
        }
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

    void loadCustomer();

    return () => {
      isMounted = false;
    };
  }, [customerId, t]);

  async function handleDeleteClick() {
    setDeleteError(null);
    setDeletePhase("loading");
    try {
      const impact = await getCustomerDeletionImpact(customerId);
      setDeleteImpact(impact);
      setDeletePhase("confirm");
    } catch {
      setDeletePhase("idle");
    }
  }

  async function handleDeleteConfirm() {
    setDeletePhase("deleting");
    try {
      await deleteCustomer(customerId);
      router.replace("/customers");
    } catch (caughtError) {
      const message = caughtError instanceof ApiClientError
        ? caughtError.message
        : "An error occurred while deleting the customer.";
      setDeleteError(message);
      setDeletePhase("confirm");
    }
  }

  function handleDeleteCancel() {
    setDeletePhase("idle");
    setDeleteImpact(null);
    setDeleteError(null);
  }

  const isConfirmPhase = deletePhase === "confirm";
  const isDeleting = deletePhase === "deleting";

  return (
    <PageFrame
      title={customer?.name ?? t("detailTitle")}
      subtitle={customer ? customer.customer_code : t("detailSubtitle")}
      action={
        <div style={{ display: "flex", gap: "10px" }}>
          <Link href="/customers" style={sharedStyles.secondaryButton}>
            {t("backToList")}
          </Link>
          {customer && canDeleteCustomer ? (
            <button
              style={deletePhase === "loading" ? styles.deleteButtonDisabled : styles.deleteButton}
              onClick={handleDeleteClick}
              disabled={deletePhase === "loading"}
            >
              {deletePhase === "loading" ? "..." : t("deleteButton")}
            </button>
          ) : null}
        </div>
      }
    >
      {customer && <><CustomerReportButtons customerId={customer.id} /><PermissionGuard code="commercial:complaints:read"><Link href={`/complaints?customer_id=${customer.id}`}>{t("complaints")}</Link></PermissionGuard></>}
      {isConfirmPhase && deleteImpact ? (
        <div style={styles.overlay} role="dialog" aria-modal="true">
          <div style={styles.modal}>
            <h2 style={styles.modalTitle}>
              {deleteImpact.is_blocked ? t("delete.blockedTitle") : t("delete.confirmTitle")}
            </h2>

            {deleteImpact.is_blocked ? (
              <div style={styles.modalBody}>
                <p style={{ margin: "0 0 8px" }}>{t("delete.blockedMessage")}</p>
                <ul style={styles.impactList}>
                  {deleteImpact.quotes > 0 ? (
                    <li style={styles.impactItem}>
                      {t("delete.quotesCount", { count: deleteImpact.quotes })}
                    </li>
                  ) : null}
                  {deleteImpact.production_demands > 0 ? (
                    <li style={styles.impactItem}>
                      {t("delete.demandsCount", { count: deleteImpact.production_demands })}
                    </li>
                  ) : null}
                  {deleteImpact.orders > 0 ? (
                    <li style={styles.impactItem}>
                      {t("delete.ordersCount", { count: deleteImpact.orders })}
                    </li>
                  ) : null}
                </ul>
              </div>
            ) : (
              <div style={styles.modalBody}>
                <p style={{ margin: "0 0 8px" }}>{t("delete.confirmMessage")}</p>
                {(deleteImpact.interactions > 0 || deleteImpact.follow_ups > 0 || deleteImpact.samples > 0) ? (
                  <ul style={styles.impactList}>
                    {deleteImpact.interactions > 0 ? (
                      <li style={styles.impactItem}>
                        {t("delete.interactionsCount", { count: deleteImpact.interactions })}
                      </li>
                    ) : null}
                    {deleteImpact.follow_ups > 0 ? (
                      <li style={styles.impactItem}>
                        {t("delete.followUpsCount", { count: deleteImpact.follow_ups })}
                      </li>
                    ) : null}
                    {deleteImpact.samples > 0 ? (
                      <li style={styles.impactItem}>
                        {t("delete.samplesCount", { count: deleteImpact.samples })}
                      </li>
                    ) : null}
                  </ul>
                ) : null}
              </div>
            )}

            {deleteError ? (
              <div style={{ ...sharedStyles.error, marginBottom: "16px" }} role="alert">
                {deleteError}
              </div>
            ) : null}

            <div style={styles.modalActions}>
              <button
                style={sharedStyles.secondaryButton as CSSProperties}
                onClick={handleDeleteCancel}
                disabled={isDeleting}
              >
                {t("delete.cancel")}
              </button>
              {!deleteImpact.is_blocked ? (
                <button
                  style={isDeleting ? styles.deleteButtonDisabled : styles.deleteButton}
                  onClick={handleDeleteConfirm}
                  disabled={isDeleting}
                >
                  {isDeleting ? t("delete.deleting") : t("delete.confirm")}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>{t("loadingDetail")}</div>
      ) : null}

      {!isLoading && isNotFound ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("notFound")}</h2>
          <p style={{ margin: "0 0 18px" }}>{t("notFoundDescription")}</p>
          <Link href="/customers" style={sharedStyles.button}>
            {t("returnToList")}
          </Link>
        </section>
      ) : null}

      {!isLoading && error ? (
        <div style={sharedStyles.error} role="alert">
          {error}
        </div>
      ) : null}

      {!isLoading && !error && !isNotFound && customer ? (
        <div style={styles.relatedSections}>
          <section style={styles.detailGrid} aria-label={t("detailsAria")}>
            <DetailItem label={t("fields.customerCode")} value={customer.customer_code} />
            <DetailItem label={t("fields.name")} value={customer.name} />
            <DetailItem label={t("fields.sector")} value={customer.sector ? sectorName(customer.sector) : customer.sector} />
            <DetailItem label={t("fields.city")} value={customer.city ? cityName(customer.city) : customer.city} />
            <DetailItem label={t("fields.country")} value={customer.country ? countryName(customer.country) : customer.country} />
            <DetailItem label={t("fields.phone")} value={customer.phone} />
            <DetailItem label={t("fields.email")} value={customer.email} />
            <DetailItem
              label={t("fields.status")}
              value={getEnumLabel("customer", "status", customer.status, tEnums)}
            />
            <DetailItem
              label={t("fields.relationshipStage")}
              value={getEnumLabel(
                "customer",
                "relationshipStage",
                customer.relationship_stage,
                tEnums,
              )}
            />
            <DetailItem
              label={t("fields.priority")}
              value={getEnumLabel("customer", "priorityLevel", customer.priority_level, tEnums)}
            />
            <DetailItem label={t("fields.opportunitySource")} value={customer.opportunity_source ? sourceName(customer.opportunity_source) : customer.opportunity_source} />
            <DetailItem label={t("fields.estimatedConsumption")} value={customer.estimated_consumption} />
            <DetailItem
              label={t("fields.salesOwner")}
              value={customer.sales_owner ? formatSalesOwner(customer.sales_owner) : t("noOwner")}
            />
            <DetailItem label={t("fields.keyInfluencerName")} value={customer.key_influencer_name} />
            <DetailItem label={t("fields.createdBy")} value={customer.created_by?.full_name ?? null} />
            <DetailItem label={t("fields.created")} value={fmt.dateTime(customer.created_at)} />
            <DetailItem label={t("fields.updated")} value={fmt.dateTime(customer.updated_at)} />
            <DetailItem label={t("fields.notes")} value={customer.notes} />
          </section>

          <CustomerDirectory id={customer.id}/><CustomerInteractionsSection customerId={customer.id} />
          <CustomerFollowUpsSection
            customerId={customer.id}
            customerSalesOwnerId={customer.sales_owner_user_id}
          />
        </div>
      ) : null}
    </PageFrame>
  );
}

function DetailItem({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div style={styles.detailItem}>
      <p style={styles.detailLabel}>{label}</p>
      <p style={styles.detailValue}>{displayValue(value)}</p>
    </div>
  );
}
