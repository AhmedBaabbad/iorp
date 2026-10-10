"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type MouseEvent } from "react";

import { useFormatter } from "@/hooks/useFormatter";
import s from "./dashboard.module.css";
import { DEFAULT_PERIOD, PERIODS, type DashboardAttention, type DashboardCard, type DashboardSeries, type Period } from "./types";

/** The colour of the n-th figure: the card's top edge, its line on the chart and its legend dot (theme tokens). */
export const TONES = ["var(--danger)", "var(--teal)", "var(--accent)", "var(--purple)", "var(--warning)", "var(--success)"];

type Translate = (key: string, values?: Record<string, string | number>) => string;

/** The chosen period, kept in the address (?period=6m) so a refresh or a shared link shows the same view. */
export function usePeriod(): [Period, (p: Period) => void] {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const asked = params.get("period") as Period | null;
  const period = asked && PERIODS.includes(asked) ? asked : DEFAULT_PERIOD;
  return [period, (p) => router.replace(p === DEFAULT_PERIOD ? pathname : `${pathname}?period=${p}`, { scroll: false })];
}

/** The period buttons (1W · 1M · 3M · 6M · YTD · 1Y in the reference design), beside the page title. */
export function PeriodBar({ period, onPeriod }: { period: Period; onPeriod: (p: Period) => void }) {
  const t = useTranslations("dashboard.kit");
  return (
    <div className={s.periods} role="group" aria-label={t("periodLabel")}>
      {PERIODS.map((p) => (
        <button key={p} type="button" className={`${s.period} ${p === period ? s.periodActive : ""}`} aria-pressed={p === period}
          onClick={() => onPeriod(p)}>{t(`periods.${p}`)}</button>
      ))}
    </div>
  );
}

function useFigure() {
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const t = useTranslations("dashboard.kit");
  return (value: string | null | undefined, unit?: string | null) => {
    if (value === null || value === undefined) return "—";
    const n = Number(value);
    if (unit === "%") return `${fmt.decimal(n, 1)}%`;
    if (unit === "h") return t("hours", { value: fmt.decimal(n, 1) });
    const text = Number.isInteger(n) ? fmt.number(n) : fmt.decimal(n, n >= 100 ? 0 : 1);
    return unit ? `${text} ${units.has(unit) ? units(unit) : unit}` : text;
  };
}

/** The change from the previous period: a percentage, or points for a rate; green when it goes the good way. */
function Change({ card, t }: { card: DashboardCard; t: Translate }) {
  const fmt = useFormatter();
  if (card.value == null || card.previous == null) return null;
  const now = Number(card.value), before = Number(card.previous);
  const delta = card.unit === "%" ? now - before : before ? ((now - before) / Math.abs(before)) * 100 : null;
  if (delta === null) return <span className={`${s.change} ${s.flat}`}>{t("new")}</span>;
  const rounded = Math.round(delta * 10) / 10;
  const good = card.good_when === "down" ? rounded < 0 : rounded > 0;
  const tone = rounded === 0 ? s.flat : good ? s.good : s.bad;
  const arrow = rounded > 0 ? "▲" : rounded < 0 ? "▼" : "●";
  const text = card.unit === "%" ? t("points", { value: fmt.decimal(Math.abs(rounded), 1) }) : `${fmt.decimal(Math.abs(rounded), 1)}%`;
  return <span className={`${s.change} ${tone}`} title={t("vsPrevious")}>{arrow} {text}</span>;
}

/** One figure, as the cards along the top of the reference design: this period with its change, and today. */
export function StatCard({ card, title, period, tone, muted }: { card: DashboardCard; title: string; period: Period; tone?: string; muted?: boolean }) {
  const t = useTranslations("dashboard.kit");
  const figure = useFigure();
  const body = (
    <>
      <span className={s.cardEdge} style={tone ? { background: tone } : undefined} aria-hidden="true" />
      <h2 className={s.cardTitle}>{title}</h2>
      <div className={s.cardRow}>
        <div className={s.cardCol}>
          <span className={s.cardLabel}>{t(`past.${period}`)}</span>
          <span className={s.cardValue}>{figure(card.value, card.unit)}</span>
          <Change card={card} t={t} />
        </div>
        {card.today !== undefined ? (
          <div className={s.cardCol}>
            <span className={s.cardLabel}>{t("today")}</span>
            <span className={s.cardToday}>{card.today === null ? "—" : figure(card.today, card.unit)}</span>
          </div>
        ) : null}
      </div>
    </>
  );
  const className = `${s.card} ${muted ? s.cardMuted : ""}`;
  return card.href ? <Link href={card.href} className={className}>{body}</Link> : <div className={className}>{body}</div>;
}

function niceMax(max: number) {
  if (max <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(max));
  const step = [1, 2, 2.5, 5, 10].find((m) => max <= m * magnitude) ?? 10;
  return step * magnitude;
}

/** The large chart: one line per series over the period, the legend toggles a line, a CSV download of the points. */
export function TrendChart({ series, names, colors, unit, onDownload }: {
  series: DashboardSeries[]; names: Record<string, string>; colors: Record<string, string>; unit?: string | null; onDownload?: () => void;
}) {
  const t = useTranslations("dashboard.kit");
  const fmt = useFormatter();
  const locale = useLocale();
  const figure = useFigure();
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [hover, setHover] = useState<number | null>(null);
  useEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(320, entry.contentRect.width)));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const shown = series.filter((x) => !hidden.has(x.key));
  const dates = series[0]?.points.map((p) => p.date) ?? [];
  const height = 300, left = 52, right = 16, top = 12, bottom = 34;
  const max = niceMax(Math.max(0, ...shown.flatMap((x) => x.points.map((p) => Number(p.value)))));
  const x = (i: number) => left + (dates.length > 1 ? (i * (width - left - right)) / (dates.length - 1) : (width - left - right) / 2);
  const y = (v: number) => top + (1 - v / max) * (height - top - bottom);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max);
  const every = Math.max(1, Math.ceil(dates.length / Math.max(2, Math.floor((width - left) / 70))));
  const short = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", timeZone: "UTC" });
  const label = (d: string) => short.format(new Date(`${d}T12:00:00Z`));
  const empty = !dates.length || shown.every((x) => x.points.every((p) => Number(p.value) === 0));

  function move(event: MouseEvent<SVGSVGElement>) {
    if (!dates.length) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const pointer = (event.clientX - bounds.left) * width / bounds.width;
    const i = Math.round(((pointer - left) / (width - left - right)) * (dates.length - 1));
    setHover(Math.min(dates.length - 1, Math.max(0, i)));
  }

  return (
    <section className={s.panel} aria-label={t("chart")}>
      <div className={s.panelHead}>
        <div className={s.legend}>
          {series.map((x) => (
            <button key={x.key} type="button" className={`${s.legendItem} ${hidden.has(x.key) ? s.legendOff : ""}`} aria-pressed={!hidden.has(x.key)}
              onClick={() => setHidden((h) => { const n = new Set(h); if (n.has(x.key)) n.delete(x.key); else n.add(x.key); return n; })}>
              <span className={s.dot} style={{ background: hidden.has(x.key) ? "var(--border-strong)" : colors[x.key] }} />{names[x.key] ?? x.key}
            </button>
          ))}
        </div>
        {onDownload ? <button type="button" className={s.iconButton} onClick={onDownload} aria-label={t("download")} title={t("download")}>⤓</button> : null}
      </div>
      <div className={s.chart} ref={box}>
        {empty ? <div className={s.emptyChart}>{t("noData")}</div> : (
          <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} onMouseMove={move} onMouseLeave={() => setHover(null)} role="img" aria-label={t("chart")}>
            {ticks.map((v) => (
              <g key={v}>
                <line className={s.gridLine} x1={left} x2={width - right} y1={y(v)} y2={y(v)} />
                <text className={s.axisText} x={left - 8} y={y(v) + 4} textAnchor="end">{figure(String(v), unit === "%" ? "%" : null)}</text>
              </g>
            ))}
            {dates.map((d, i) => (i % every === 0 ? <text key={d} className={s.axisText} x={x(i)} y={height - 10} textAnchor="middle">{label(d)}</text> : null))}
            {shown.map((line) => (
              <polyline key={line.key} className={s.line} style={{ stroke: colors[line.key] }}
                points={line.points.map((p, i) => `${x(i)},${y(Number(p.value))}`).join(" ")} />
            ))}
            {hover !== null ? <line className={s.hoverLine} x1={x(hover)} x2={x(hover)} y1={top} y2={height - bottom} /> : null}
          </svg>
        )}
        {hover !== null && !empty ? (
          <div className={s.tooltip} style={{ [x(hover) > width / 2 ? "right" : "left"]: x(hover) > width / 2 ? width - x(hover) + 10 : x(hover) + 10 }}>
            <strong>{fmt.date(`${dates[hover]}T12:00:00Z`)}</strong>
            {shown.map((line) => (
              <span key={line.key} style={{ color: colors[line.key] }}>{names[line.key] ?? line.key}: {figure(line.points[hover]?.value, line.unit)}</span>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}

/** What waits for someone, as the table under the chart in the reference design, with a filter by kind. */
export function AttentionTable({ items, total, kinds, title }: { items: DashboardAttention[]; total: number; kinds: (kind: string) => string; title?: string }) {
  const t = useTranslations("dashboard.kit");
  const fmt = useFormatter();
  const [kind, setKind] = useState("");
  const available = useMemo(() => [...new Set(items.map((i) => i.kind))], [items]);
  const rows = kind ? items.filter((i) => i.kind === kind) : items;
  return (
    <section className={s.panel} aria-label={title ?? t("attention")}>
      <div className={s.panelHead}>
        <h2 className={s.panelTitle}>{title ?? t("attention")} {total ? <span className={s.muted}>({total})</span> : null}</h2>
        {available.length > 1 ? (
          <select className={s.select} value={kind} onChange={(e) => setKind(e.target.value)} aria-label={t("kind")}>
            <option value="">{t("allKinds")}</option>
            {available.map((k) => <option key={k} value={k}>{kinds(k)}</option>)}
          </select>
        ) : null}
      </div>
      {rows.length === 0 ? <p className={s.muted}>{t("nothingWaiting")}</p> : (
        <div className={s.tableWrap}>
          <table className={s.table}>
            <thead><tr><th>{t("columns.item")}</th><th>{t("columns.detail")}</th><th>{t("columns.date")}</th><th>{t("columns.kind")}</th></tr></thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={`${row.kind}-${row.id ?? i}`}>
                  <td>{row.href ? <Link href={row.href}><bdi>{row.label}</bdi></Link> : <bdi>{row.label}</bdi>}</td>
                  <td>{row.detail ?? "—"}</td>
                  <td>{row.date ? fmt.date(`${row.date}T12:00:00Z`) : "—"}</td>
                  <td><span className={`${s.badge} ${s[row.severity]}`}>{kinds(row.kind)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/** The chart's points as a CSV file (date, then one column per series). */
export function downloadSeries(series: DashboardSeries[], names: Record<string, string>, file: string) {
  const header = ["date", ...series.map((x) => names[x.key] ?? x.key)];
  const rows = (series[0]?.points ?? []).map((p, i) => [p.date, ...series.map((x) => x.points[i]?.value ?? "")]);
  const csv = "﻿" + [header, ...rows].map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = file;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export { s as dashboardStyles };
