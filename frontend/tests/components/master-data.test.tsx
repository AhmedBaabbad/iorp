// MD-001: master data — products with their specification templates, choosing a product on other screens, mapping
// legacy product types, and the VAT rate and default currency.
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { useState, type ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import type { ListItem, Product } from "@/features/masterdata/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ push: vi.fn() }));
const perms = vi.hoisted(() => ({ granted: new Set<string>() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: nav.push, replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: (code: string) => perms.granted.has(code),
  useHasAnyPermission: (codes: string[]) => codes.some(code => perms.granted.has(code)) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) => <main><h1>{title}</h1>{action}{children}</main> }));

import { SpecEditor } from "@/components/forms/SpecEditor";
import { refreshCatalog } from "@/features/masterdata/catalog";
import { GeneralSettings } from "@/features/masterdata/components/GeneralSettings";
import { ProductSelect } from "@/features/masterdata/components/ProductSelect";
import { ListSelect } from "@/features/masterdata/components/ListSelect";
import { ProductForm, ProductsList } from "@/features/masterdata/components/Products";
import { ReferenceLists } from "@/features/masterdata/components/ReferenceLists";
import { MD } from "@/lib/masterdata-permissions";

let en: Record<string, unknown>;
let ar: Record<string, unknown>;
beforeAll(async () => { en = await loadMessages("en") as Record<string, unknown>; ar = await loadMessages("ar") as Record<string, unknown>; });
beforeEach(() => { api.apiClient.mockReset(); nav.push.mockReset(); perms.granted = new Set(Object.values(MD)); refreshCatalog(); });
afterEach(cleanup);
const ui = (node: ReactNode, locale: "en" | "ar" = "en") =>
  render(<NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ar} timeZone="UTC">{node}</NextIntlClientProvider>);
const sent = (path: string, method: string) => api.apiClient.mock.calls.find(([p, o]) => p === path && o?.method === method)?.[1]?.body;

const strap: Product = { id: "p1", code: "PRD-0001", key: "pp_strap", name_ar: "شريط تربيط PP", name_en: "PP Strap", kind: "finished", default_unit: "roll",
  active: true, notes: null, actions: ["edit"], created_at: "", updated_at: "", properties: [
    { key: "width_mm", name_ar: "العرض", name_en: "Width", kind: "number", unit: "mm", required: true, options: null },
    { key: "color", name_ar: "اللون", name_en: "Colour", kind: "choice", unit: null, required: false,
      options: [{ value: "white", label_ar: "أبيض", label_en: "White" }, { value: "black", label_ar: "أسود", label_en: "Black" }] }] };
const old: Product = { ...strap, id: "p2", code: "PRD-0002", key: "carton_box", name_ar: "كرتون", name_en: "Carton", active: false, properties: [] };

describe("products", () => {
  it("creates a product with its key from the English name and a specification template", async () => {
    api.apiClient.mockResolvedValue({ ...strap });
    ui(<ProductForm />);
    fireEvent.change(screen.getByLabelText("Name (Arabic)"), { target: { value: "شريط تربيط PP" } });
    fireEvent.change(screen.getByLabelText("Name (English)"), { target: { value: "PP Strap" } });
    expect(screen.getByText(/Saved as: pp_strap/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Add property" }));
    const prop = screen.getByRole("group", { name: /New property/ });
    fireEvent.change(within(prop).getByLabelText("Name (Arabic)"), { target: { value: "اللون" } });
    fireEvent.change(within(prop).getByLabelText("Name (English)"), { target: { value: "Colour" } });
    fireEvent.change(within(prop).getByLabelText("Key"), { target: { value: "color" } });
    fireEvent.change(within(prop).getByLabelText("Type"), { target: { value: "choice" } });
    fireEvent.click(within(prop).getByRole("button", { name: "Add option" }));
    fireEvent.change(within(prop).getByLabelText("Arabic label"), { target: { value: "أبيض" } });
    fireEvent.change(within(prop).getByLabelText("English label"), { target: { value: "White" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save" })); });
    expect(sent("/masterdata/products", "POST")).toMatchObject({ key: "pp_strap", name_en: "PP Strap", kind: "finished",
      properties: [{ key: "color", kind: "choice", unit: null, options: [{ value: "white", label_ar: "أبيض", label_en: "White" }] }] });
    expect(nav.push).toHaveBeenCalledWith("/master-data/products/p1");
  });

  it("keeps the key of a saved product", async () => {
    api.apiClient.mockResolvedValue({ ...strap });
    ui(<ProductForm productId="p1" />);
    expect(((await screen.findByLabelText(/^Product key/)) as HTMLInputElement).readOnly).toBe(true);
    expect(screen.getByText("Every module stores this key, so it never changes.")).toBeTruthy();
  });

  it("maps a product type written before the list", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => Promise.resolve(
      o?.method === "POST" ? { value: "اشرطة تربيط ", key: "pp_strap", changed: { commercial: 2, production: 1 } }
        : path === "/masterdata/products/legacy" ? [{ value: "اشرطة تربيط ", uses: { commercial: 2, production: 1 }, total: 3, suggested_key: "" }]
          : [strap]));
    ui(<ProductsList />, "ar");
    const panel = await screen.findByRole("region", { name: "أنواع منتجات كُتبت قبل القائمة" });
    expect(within(panel).getByText("المبيعات: 2 · الإنتاج: 1")).toBeTruthy();
    fireEvent.change(within(panel).getByLabelText("ربط بـ"), { target: { value: "p1" } });
    await act(async () => { fireEvent.click(within(panel).getByRole("button", { name: "ربط" })); });
    expect(sent("/masterdata/products/legacy/map", "POST")).toEqual({ value: "اشرطة تربيط ", product_id: "p1" });  // exactly as stored
  });
});

describe("choosing a product on other screens", () => {
  function Harness({ initial = "" }: { initial?: string }) {
    const [value, setValue] = useState(initial);
    return <><ProductSelect ariaLabel="Product type" value={value} onChange={setValue} /><output>{value}</output></>;
  }

  it("offers the active products, and keeps a value written before the list", async () => {
    api.apiClient.mockResolvedValue([strap, old]);
    ui(<Harness initial="اشرطة تربيط" />, "ar");
    await screen.findByRole("option", { name: "شريط تربيط PP" });
    const select = screen.getByRole("combobox", { name: "Product type" }) as HTMLSelectElement;
    expect(Array.from(select.options).map(o => o.textContent)).toEqual(["اختر منتجًا", "شريط تربيط PP", "اشرطة تربيط (مكتوب قبل القائمة)"]);
    fireEvent.change(select, { target: { value: "pp_strap" } });
    expect(screen.getByRole("status").textContent).toBe("pp_strap");
  });

  it("stays free text until the organization defines products", async () => {
    api.apiClient.mockResolvedValue([]);
    ui(<Harness />);
    const input = await screen.findByRole("textbox", { name: "Product type" });
    fireEvent.change(input, { target: { value: "strap" } });
    expect(screen.getByRole("status").textContent).toBe("strap");
    expect(screen.getByText(/No products are defined yet/)).toBeTruthy();
  });

  it("writes the specification in the template's order with its choices", () => {
    const onChange = vi.fn();
    ui(<SpecEditor value="" template={strap.properties} onChange={onChange} />, "ar");
    fireEvent.change(screen.getByLabelText("اللون"), { target: { value: "white" } });
    fireEvent.change(screen.getByLabelText(/العرض/), { target: { value: "19" } });
    expect(onChange).toHaveBeenLastCalledWith('{"width_mm":19,"color":"white"}');
  });
});

describe("general settings", () => {
  it("sets the VAT rate and the default currency", async () => {
    api.apiClient.mockImplementation((_path: string, o?: { method?: string; body?: object }) => Promise.resolve(
      o?.method === "PATCH" ? { vat_rate: "5.00", default_currency: "USD", currencies: ["SAR", "USD"] }
        : { vat_rate: "15.00", default_currency: "SAR", currencies: ["SAR", "USD"] }));
    ui(<GeneralSettings />);
    const rate = await screen.findByLabelText(/VAT rate/) as HTMLInputElement;
    expect(rate.value).toBe("15");
    fireEvent.change(rate, { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText(/Default currency/), { target: { value: "USD" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save" })); });
    expect(sent("/masterdata/settings", "PATCH")).toEqual({ vat_rate: "5", default_currency: "USD" });
    expect(screen.getByRole("status").textContent).toBe("Saved.");
  });
});

describe("reference lists", () => {
  const item = (list: ListItem["list"], key: string, name_ar: string, name_en: string, parent_key: string | null = null, active = true): ListItem =>
    ({ id: `${list}-${key}`, list, key, name_ar, name_en, parent_key, active, sort_order: 0 });
  const all = [item("country", "sa", "السعودية", "Saudi Arabia"), item("country", "ae", "الإمارات", "UAE"),
    item("city", "riyadh", "الرياض", "Riyadh", "sa"), item("city", "dubai", "دبي", "Dubai", "ae"), item("city", "old", "قديمة", "Old", "sa", false)];

  function City({ country }: { country: string }) {
    const [value, setValue] = useState("");
    return <ListSelect list="city" ariaLabel="City" parent={country} value={value} onChange={setValue} />;
  }

  it("offers the cities of the chosen country", async () => {
    api.apiClient.mockResolvedValue(all);
    ui(<City country="sa" />, "ar");
    await screen.findByRole("option", { name: "الرياض" });
    const select = screen.getByRole("combobox", { name: "City" }) as HTMLSelectElement;
    expect(Array.from(select.options).map(o => o.textContent)).toEqual(["اختر…", "الرياض"]);  // not Dubai, not the inactive one
  });

  it("adds the usual values and maps a text written before the list", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => Promise.resolve(
      path === "/masterdata/lists/sector/standard" ? [item("sector", "packaging", "التعبئة والتغليف", "Packaging")]
        : path === "/masterdata/lists/sector/legacy/map" ? { value: "كرتون", key: "packaging", changed: { commercial: 3 } }
          : path === "/masterdata/lists/sector/legacy" ? [{ value: "كرتون", uses: { commercial: 3 }, total: 3, suggested_key: "" }]
            : path.startsWith("/masterdata/lists?list=sector") ? [item("sector", "packaging", "التعبئة والتغليف", "Packaging")] : []));
    ui(<ReferenceLists initialList="sector" />, "ar");
    await act(async () => { fireEvent.click(await screen.findByRole("button", { name: "إضافة القيم المعتادة" })); });
    expect(api.apiClient).toHaveBeenCalledWith("/masterdata/lists/sector/standard", { method: "POST" });
    expect(screen.getByText("أُضيفت 1 قيمة.")).toBeTruthy();
    const panel = await screen.findByRole("region", { name: "قيم كُتبت قبل القائمة" });
    expect(within(panel).getByText("العملاء: 3")).toBeTruthy();
    fireEvent.change(within(panel).getByLabelText("ربط بـ"), { target: { value: "sector-packaging" } });
    await act(async () => { fireEvent.click(within(panel).getByRole("button", { name: "ربط" })); });
    expect(sent("/masterdata/lists/sector/legacy/map", "POST")).toEqual({ value: "كرتون", item_id: "sector-packaging" });
  });
});
