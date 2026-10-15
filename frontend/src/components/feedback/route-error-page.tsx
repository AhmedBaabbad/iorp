"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import styles from "./route-error-page.module.css";

export function RouteErrorPage({ reset }: { reset?: () => void }) {
  const t = useTranslations("common.errorPage");
  const locale = useLocale();
  const pathname = usePathname();
  const dashboard = pathname === "/platform" || pathname?.startsWith("/platform/")
    ? "/platform" : "/dashboard";

  return (
    <main className={styles.page} dir={locale === "ar" ? "rtl" : "ltr"}>
      <section className={styles.card} aria-labelledby="route-error-title">
        <span className={styles.brand}>IORP</span>
        <div className={styles.code} aria-hidden="true">{reset ? "!" : "404"}</div>
        <h1 id="route-error-title">{t(reset ? "errorTitle" : "notFoundTitle")}</h1>
        <p>{t(reset ? "errorDescription" : "notFoundDescription")}</p>
        <div className={styles.actions}>
          {reset && <button type="button" className={styles.primary} onClick={reset}>{t("retry")}</button>}
          <Link href={dashboard} className={reset ? styles.secondary : styles.primary}>{t("home")}</Link>
        </div>
      </section>
    </main>
  );
}
