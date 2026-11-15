"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { customersByIds } from "@/features/customers/customer-api";
import type { CustomerOption } from "@/types/customers";

/** Nonblocking: the document still prints the other name when its language is missing. */
export function CustomerNameLanguageHint({ customerId, language }: {
  customerId: string; language: "ar" | "en" | null;
}) {
  const t = useTranslations("commercial.quotes");
  const [customer, setCustomer] = useState<CustomerOption | null>(null);
  useEffect(() => {
    let live = true;
    if (customerId) customersByIds([customerId]).then(rows => {
      if (live) setCustomer(rows[0] ?? null);
    }).catch(() => { if (live) setCustomer(null); });
    return () => { live = false; };
  }, [customerId]);
  if (!language || customer?.id !== customerId || !customer ||
      (language === "ar" ? customer.name_ar?.trim() : customer.name_en?.trim())) return null;
  return <p style={{ color: "var(--text-muted)", fontSize: "13px", margin: 0 }}>
    {t(language === "ar" ? "missingArabicCustomerName" : "missingEnglishCustomerName")}{" "}
    <Link href={`/customers/${customerId}`}>{t("customerCard")}</Link>
  </p>;
}
