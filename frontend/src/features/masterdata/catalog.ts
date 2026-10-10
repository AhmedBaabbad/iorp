"use client";

import { useLocale } from "next-intl";
import { useEffect, useState } from "react";

import { getBusinessSettings, getListItems, getProducts } from "./api";
import type { BusinessSettings, ListItem, ListName, Product } from "./types";

// The organization's products and general settings, shared by every screen that names a product or prices a document.
// Kept for a minute so moving between screens does not ask again; refreshCatalog() after a change.
const TTL = 60_000;
type Entry<T> = { at: number; value: T } | null;
let products: Entry<Product[]> = null;
let settings: Entry<BusinessSettings> = null;
let pendingProducts: Promise<Product[]> | null = null;
let pendingSettings: Promise<BusinessSettings | null> | null = null;
let lists: Entry<ListItem[]> = null;
let pendingLists: Promise<ListItem[]> | null = null;

function loadLists(): Promise<ListItem[]> {
  if (lists && Date.now() - lists.at < TTL) return Promise.resolve(lists.value);
  pendingLists ??= getListItems().then(v => (Array.isArray(v) ? v : [])).catch(() => [] as ListItem[])
    .then(value => { lists = { at: Date.now(), value }; pendingLists = null; return value; });
  return pendingLists;
}

function loadProducts(): Promise<Product[]> {
  if (products && Date.now() - products.at < TTL) return Promise.resolve(products.value);
  pendingProducts ??= getProducts().then(v => (Array.isArray(v) ? v : [])).catch(() => [] as Product[])
    .then(value => { products = { at: Date.now(), value }; pendingProducts = null; return value; });
  return pendingProducts;
}

function loadSettings(): Promise<BusinessSettings | null> {
  if (settings && Date.now() - settings.at < TTL) return Promise.resolve(settings.value);
  pendingSettings ??= getBusinessSettings().then(v => (v && typeof v.vat_rate === "string" ? v : null)).catch(() => null)
    .then(value => { if (value) settings = { at: Date.now(), value }; pendingSettings = null; return value; });
  return pendingSettings;
}

export function refreshCatalog() {
  products = null; settings = null; pendingProducts = null; pendingSettings = null; lists = null; pendingLists = null;
}

/** The items of one reference list (active and not), or null while loading. */
export function useListItems(list: ListName): ListItem[] | null {
  const [value, setValue] = useState<ListItem[] | null>(lists ? lists.value.filter(i => i.list === list) : null);
  useEffect(() => { let active = true; void loadLists().then(v => { if (active) setValue(v.filter(i => i.list === list)); }); return () => { active = false; }; }, [list]);
  return value;
}

/** A stored list value as people read it: the item's name in the screen's language, else the stored text. */
export function useListName(list: ListName): (key: string | null | undefined) => string {
  const locale = useLocale();
  const all = useListItems(list);
  return (key) => {
    if (!key) return "—";
    const found = all?.find(i => i.key === key);
    return found ? (locale === "ar" ? found.name_ar : found.name_en) : key;
  };
}

/** All the organization's products (active and not), or null while loading. */
export function useProducts(): Product[] | null {
  const [value, setValue] = useState<Product[] | null>(products?.value ?? null);
  useEffect(() => { let active = true; void loadProducts().then(v => { if (active) setValue(v); }); return () => { active = false; }; }, []);
  return value;
}

/** The VAT rate and default currency (15 % and SAR until the organization sets its own, or while loading). */
export function useBusinessSettings(): { vatRate: number; currency: "SAR" | "USD"; loaded: boolean } {
  const [value, setValue] = useState<BusinessSettings | null>(settings?.value ?? null);
  useEffect(() => { let active = true; void loadSettings().then(v => { if (active) setValue(v); }); return () => { active = false; }; }, []);
  return { vatRate: value ? Number(value.vat_rate) : 15, currency: value?.default_currency ?? "SAR", loaded: value !== null };
}

/** A product type as people read it: the product's name in the screen's language, else the stored text. */
export function useProductName(): (key: string | null | undefined) => string {
  const locale = useLocale();
  const all = useProducts();
  return (key) => {
    if (!key) return "—";
    const found = all?.find(p => p.key === key);
    return found ? (locale === "ar" ? found.name_ar : found.name_en) : key;
  };
}
