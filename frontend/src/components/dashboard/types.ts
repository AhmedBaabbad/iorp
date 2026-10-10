// The dashboard every module answers with (backend app/core/dashboard.py, DASH-001).
export type Period = "1w" | "1m" | "3m" | "6m" | "ytd" | "1y";
export const PERIODS: Period[] = ["1w", "1m", "3m", "6m", "ytd", "1y"];
export const DEFAULT_PERIOD: Period = "3m";

export type DashboardCard = {
  key: string;
  value: string | null;
  previous?: string | null;
  today?: string | null;
  unit?: string | null; // a unit code (kg), "%" or "h"
  good_when?: "up" | "down";
  href?: string | null;
  style?: "tile" | "gauge" | "count";
  target?: string | null;
  spark?: string[] | null;
};
export type DashboardPoint = { date: string; value: string };
export type DashboardSeries = { key: string; unit?: string | null; points: DashboardPoint[] };
export type DashboardAttention = {
  kind: string; id?: string | null; label: string; detail?: string | null; date?: string | null; href?: string | null;
  severity: "danger" | "warning" | "info";
};
export type Dashboard = {
  module: string; period: Period; start: string; end: string;
  cards: DashboardCard[]; series: DashboardSeries[]; attention: DashboardAttention[]; attention_total: number;
  breakdowns?: { key: string; style: "donut" | "bars" | "funnel"; unit?: string | null; items: { key: string; value: string; label?: string | null }[] }[];
  rankings?: { key: string; unit?: string | null; items: { label: string; value: string; detail?: string | null; href?: string | null }[] }[];
};
