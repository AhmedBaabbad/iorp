"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import {
  AttentionTable, PeriodBar, StatCard, TONES, TrendChart, dashboardStyles as s, downloadSeries, usePeriod,
} from "@/components/dashboard/DashboardKit";
import type { Dashboard } from "@/components/dashboard/types";
import { apiClient } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";

// The production section's dashboard (DASH-001): output, scrap, stops and completed orders over the period, the daily
// output against scrap, and what waits on the floor. The server sends each part only with the permission to read it.
const COLORS: Record<string, string> = { produced: TONES[0], scrap: TONES[1] };
const CARD_TONES: Record<string, string> = { produced: TONES[0], scrap_rate: TONES[1], downtime: TONES[2], completed_orders: TONES[3] };

export function getProductionDashboard(period: string) {
  return apiClient<Dashboard>(`/production/dashboard?period=${period}`);
}

export function ProductionDashboard() {
  const t = useTranslations("dashboard.production");
  const messages = useTranslations("messages");
  const [period, setPeriod] = usePeriod();
  const [board, setBoard] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setError("");
    getProductionDashboard(period).then((b) => { if (active) setBoard(b); })
      .catch((e) => { if (active) setError(getApiErrorMessage(e, messages)); });
    return () => { active = false; };
  }, [period]); // eslint-disable-line react-hooks/exhaustive-deps

  const names = Object.fromEntries((board?.series ?? []).map((x) => [x.key, t(`series.${x.key}`)]));
  return (
    <PageFrame title={t("title")} subtitle={t("subtitle")} action={<PeriodBar period={period} onPeriod={setPeriod} />}>
      <div className={s.page}>
        {error ? <p role="alert" className={s.muted}>{error}</p> : null}
        {!board && !error ? <div className={s.cards}>{[0, 1, 2, 3].map((i) => <div key={i} className={`${s.skeleton} iorp-skeleton`} />)}</div> : null}
        {board ? (
          <>
            <div className={s.cards}>
              {board.cards.map((card) => (
                <StatCard key={card.key} card={card} title={t(`cards.${card.key}`)} period={period} tone={CARD_TONES[card.key]} />
              ))}
            </div>
            {board.series.length ? (
              <TrendChart series={board.series} names={names} colors={COLORS} unit={board.series[0]?.unit}
                onDownload={() => downloadSeries(board.series, names, `production-${period}.csv`)} />
            ) : null}
            <AttentionTable items={board.attention} total={board.attention_total} kinds={(k) => t(`attention.${k}`)} />
          </>
        ) : null}
      </div>
    </PageFrame>
  );
}
