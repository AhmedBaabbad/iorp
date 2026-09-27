"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { getWorkCenterById } from "../api/work-centers-api";
import type { WorkCenterData } from "../types";
import { WorkCenterEditForm } from "./WorkCenterEditForm";

export function WorkCenterEditPage() {
  const params = useParams<{ id: string }>();
  const workCenterId = params.id;
  const messages = useTranslations("messages");
  const t = useTranslations("production.workCenters");
  const [workCenter, setWorkCenter] = useState<WorkCenterData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const data = await getWorkCenterById(workCenterId);
        if (isMounted) setWorkCenter(data);
      } catch (caughtError) {
        if (!isMounted) return;
        if (caughtError instanceof ApiClientError && caughtError.status === 404) {
          setIsNotFound(true);
          return;
        }
        setError(getApiErrorMessage(caughtError, messages));
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    void load();
    return () => { isMounted = false; };
  }, [workCenterId]);

  if (isLoading) {
    return (
      <div style={{ ...sharedStyles.state, background: "#ffffff" }}>
        {messages("loading.default")}
      </div>
    );
  }

  if (isNotFound) {
    return (
      <section style={{ ...sharedStyles.state, background: "#ffffff" }}>
        <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("notFound")}</h2>
        <p style={{ margin: "0 0 18px" }}>{t("notFoundDescription")}</p>
        <Link href="/work-centers" style={sharedStyles.button}>{t("returnToList")}</Link>
      </section>
    );
  }

  if (error) {
    return <div style={sharedStyles.error} role="alert">{error}</div>;
  }

  if (!workCenter) return null;

  return <WorkCenterEditForm workCenter={workCenter} />;
}
