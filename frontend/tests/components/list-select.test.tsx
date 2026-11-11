import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import { ListSelect } from "@/features/masterdata/components/ListSelect";

const state = vi.hoisted(() => ({ canManage: true, items: [] as unknown[] }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: () => state.canManage }));
vi.mock("@/features/masterdata/catalog", () => ({ useListItems: () => state.items }));
afterEach(cleanup);
beforeEach(() => {
  state.canManage = true;
  state.items = [{ key: "sa", name_ar: "السعودية", name_en: "Saudi Arabia", active: true }];
});
const ui = (onChange = vi.fn()) => render(<NextIntlClientProvider locale="ar" timeZone="UTC" messages={{ masterdata: { select: {
  manageList: "إدارة القائمة", chooseItem: "اختر", loading: "تحميل", inactive: "{name}", legacy: "{value}",
} } }}><ListSelect list="country" value="" ariaLabel="الدولة" onChange={onChange} /></NextIntlClientProvider>);

it("places the accessible management icon beside the select and keeps its destination", () => {
  const onChange = vi.fn();
  ui(onChange);
  const select = screen.getByRole("combobox");
  const link = screen.getByRole("link", { name: "إدارة القائمة" });
  expect(link.parentElement).toBe(select.parentElement);
  expect(select.nextElementSibling).toBe(link);
  expect(link.className).toContain("manage");
  expect(select.parentElement?.className).toContain("row");
  expect(link.getAttribute("title")).toBe("إدارة القائمة");
  expect(link.getAttribute("href")).toBe("/master-data/lists?list=country");
  expect(link.getAttribute("target")).toBe("_blank");
  expect(link.querySelector('[aria-hidden="true"]')).toBeTruthy();
  fireEvent.change(select, { target: { value: "sa" } });
  expect(onChange).toHaveBeenCalledWith("sa", state.items[0]);
});

it("does not render the management action without permission", () => {
  state.canManage = false;
  ui();
  expect(screen.queryByRole("link")).toBeNull();
  expect(screen.getByRole("combobox")).toBeTruthy();
});

it("preserves the free text fallback without management action", () => {
  state.items = [];
  ui();
  expect(screen.getByRole("textbox")).toBeTruthy();
  expect(screen.queryByRole("link")).toBeNull();
});
