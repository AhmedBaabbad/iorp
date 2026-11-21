import { describe, expect, it } from "vitest";
import { formatNumber, formatQuantity } from "@/lib/formatters";

describe.each(["ar", "en"] as const)("quantity formatting (%s)", locale => {
  it.each([
    [2.5, "2.5"],
    [100, "100"],
    [1234.5678, "1,234.568"],
    [0.125, "0.125"],
    [null, "—"],
  ])("formats %s as %s", (value, expected) => {
    expect(formatQuantity(value, null, locale)).toBe(expected);
  });

  it("preserves string decimals and localized units without trailing zeros", () => {
    expect(formatQuantity("2.500", "kg", locale)).toBe(locale === "ar" ? "2.5 كجم" : "2.5 kg");
    expect(formatQuantity("100.000", "kg", locale)).toBe(locale === "ar" ? "100 كجم" : "100 kg");
  });

  it("leaves integer number formatting unchanged", () => {
    expect(formatNumber(2.5, locale)).toBe("3");
  });
});
