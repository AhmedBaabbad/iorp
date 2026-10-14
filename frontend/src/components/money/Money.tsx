"use client";

import { useTranslations } from "next-intl";

import { useFormatter } from "@/hooks/useFormatter";

// The Saudi riyal sign (SAMA, 2025), drawn so it shows without a font that has it. Path: saudi-riyal-font, OFL-1.1.
const RIYAL = "M750,1119C730,1163,716,1211,711,1262L1136,1172C1156,1127,1169,1079,1174,1028L750,1119ZM1136,901C1156,857,1169,809,1174,758L843,828L843,693L1136,631C1156,587,1169,538,1174,488L843,558L843,72C793,100,748,138,711,183L711,586L579,614L579,6C528,34,483,72,447,117L447,642L151,705C131,750,117,798,112,849L447,777L447,948L88,1024C68,1068,55,1117,50,1167L425,1088C456,1081,482,1063,499,1038L568,936C575,926,579,913,579,899L579,749L711,721L711,992L1136,901Z";

export function RiyalSign({ size = "0.95em" }: { size?: string }) {
  const t = useTranslations("common.currencies");
  return <svg viewBox="0 0 1256 1270" width={size} height={size} role="img" aria-label={t("SAR")} style={{ display: "inline-block", verticalAlign: "-0.12em" }}>
    <path fill="currentColor" d={RIYAL} />
  </svg>;
}

export function CurrencySign({ currency }: { currency: string }) {
  if (currency === "SAR") return <RiyalSign />;
  return <span aria-hidden={currency === "USD"}>{currency === "USD" ? "$" : currency}</span>;
}

// An amount with its currency sign: the riyal sign, or $ for dollars.
/** Places a unit price needs: two, or four for a price after a percentage discount (11.4855). */
export const pricePlaces = (value: string | number | null | undefined) => {
  const n = Number(value ?? 0);
  return Math.abs(n * 100 - Math.round(n * 100)) > 1e-9 ? 4 : 2;
};

export function Money({ amount, currency, places = 2 }: { amount: string | number | null | undefined; currency: string; places?: number }) {
  const fmt = useFormatter();
  return <bdi dir="ltr" style={{ whiteSpace: "nowrap" }}><CurrencySign currency={currency} /> {fmt.decimal(amount, places)}</bdi>;
}
