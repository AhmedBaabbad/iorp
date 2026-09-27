"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { getShiftById } from "../api/shifts-api";
import type { ShiftData } from "../types";
import { ShiftEditForm } from "./ShiftEditForm";

export function ShiftEditPage() {
  const params = useParams<{ id: string }>();
  const shiftId = params.id;
  const messages = useTranslations("messages");
  const t = useTranslations("production.shifts");
  const [shift, setShift] = useState<ShiftData | null>(null);
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
        const data = await getShiftById(shiftId);
        if (isMounted) setShift(data);
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
  }, [shiftId, messages]);

  if (isLoading) {
    return (
      <div style={{ ...sharedStyles.state, background: "#ffffff" }}>
        {t("loadingDetail")}
      </div>
    );
  }

  if (isNotFound) {
    return (
      <section style={{ ...sharedStyles.state, background: "#ffffff" }}>
        <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("notFound")}</h2>
        <p style={{ margin: "0 0 18px" }}>{t("notFoundDescription")}</p>
        <Link href="/shifts" style={sharedStyles.button}>{t("returnToList")}</Link>
      </section>
    );
  }

  if (error) {
    return <div style={sharedStyles.error} role="alert">{error}</div>;
  }

  if (!shift) return null;

  return <ShiftEditForm shift={shift} />;
}
