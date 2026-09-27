"use client";

import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { ApiClientError } from "@/lib/api-client";
import { sharedStyles } from "@/styles/shared-styles";
import { getCommercialOrderById } from "../api/commercial-orders-api";
import type { CommercialOrderData } from "../types";
import { CommercialOrderEditForm } from "./CommercialOrderEditForm";

export function CommercialOrderEditPage() {
  const messages = useTranslations("messages");
  const t = useTranslations("commercial.commercialOrders");
  const params = useParams<{ id: string }>();
  const orderId = params.id;
  const [order, setOrder] = useState<CommercialOrderData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);

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
      } catch (caughtError) {
        if (!isMounted) return;
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
  }, [orderId, messages]);

  if (isLoading) {
    return (
      <PageFrame title={t("editTitle")} subtitle="">
        <div style={{ ...sharedStyles.state, background: "#ffffff" }}>
          {messages("loading.default")}
        </div>
      </PageFrame>
    );
  }

  if (isNotFound) {
    return (
      <PageFrame title={t("editTitle")} subtitle="">
        <section style={{ ...sharedStyles.state, background: "#ffffff" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("notFound")}</h2>
          <p style={{ margin: 0 }}>{t("notFoundDescription")}</p>
        </section>
      </PageFrame>
    );
  }

  if (error) {
    return (
      <PageFrame title={t("editTitle")} subtitle="">
        <div style={sharedStyles.error} role="alert">
          {error}
        </div>
      </PageFrame>
    );
  }

  if (!order) return null;

  return <CommercialOrderEditForm order={order} />;
}
