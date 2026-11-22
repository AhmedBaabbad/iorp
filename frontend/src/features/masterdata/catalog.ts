"use client";

import { useLocale, useTranslations } from "next-intl";

import { localName } from "@/lib/local-name";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { useEffect, useState } from "react";

import { getBusinessSettings, getListItems, getProducts } from "./api";
import type { BusinessSettings, ListItem, ListName, Product } from "./types";

// The organization's products and general settings, shared by every screen that names a product or prices a document.
// Kept for a minute so moving between screens does not ask again; refreshCatalog() after a change.
const TTL = 60_000;
let generation = 0;
const subscribers = new Set<() => Promise<void>>();
type Entry<T> = { at: number; value: T } | null;
let products: Entry<Product[]> = null;
let settings: Entry<BusinessSettings> = null;
let pendingProducts: Promise<Product[]> | null = null;
let pendingSettings: Promise<BusinessSettings | null> | null = null;
let lists: Entry<ListItem[]> = null;
let pendingLists: Promise<ListItem[]> | null = null;

function loadLists(): Promise<ListItem[]> {
  if (lists && Date.now() - lists.at < TTL) return Promise.resolve(lists.value);
  if (pendingLists) return pendingLists;
  const current = generation;
  const request = getListItems().then(v => (Array.isArray(v) ? v : [])).catch(() => [] as ListItem[])
    .then(value => {
      if (current === generation) { lists = { at: Date.now(), value }; if (pendingLists === request) pendingLists = null; }
      return value;
    });
  pendingLists = request; return request;
}

function loadProducts(): Promise<Product[]> {
  if (products && Date.now() - products.at < TTL) return Promise.resolve(products.value);
  if (pendingProducts) return pendingProducts;
  const current = generation;
  const request = getProducts().then(v => (Array.isArray(v) ? v : [])).catch(() => [] as Product[])
    .then(value => {
      if (current === generation) { products = { at: Date.now(), value }; if (pendingProducts === request) pendingProducts = null; }
      return value;
    });
  pendingProducts = request; return request;
}

function loadSettings(): Promise<BusinessSettings | null> {
  if (settings && Date.now() - settings.at < TTL) return Promise.resolve(settings.value);
  if (pendingSettings) return pendingSettings;
  const current = generation;
  const request = getBusinessSettings().then(v => (v && typeof v.vat_rate === "string" ? v : null)).catch(() => null)
    .then(value => {
      if (current === generation) { if (value) settings = { at: Date.now(), value }; if (pendingSettings === request) pendingSettings = null; }
      return value;
    });
  pendingSettings = request; return request;
}

export async function refreshCatalog() {
  generation++;
  products = null; settings = null; pendingProducts = null; pendingSettings = null; lists = null; pendingLists = null;
  await Promise.all([...subscribers].map(reload => reload()));
}

/** The items of one reference list (active and not), or null while loading. */
export function useListItems(list: ListName): ListItem[] | null {
  const [value, setValue] = useState<ListItem[] | null>(lists ? lists.value.filter(i => i.list === list) : null);
  useEffect(() => {
    let active = true;
    const reload = async () => { const current = generation; const v = await loadLists(); if (active && current === generation) setValue(v.filter(i => i.list === list)); };
    subscribers.add(reload); void reload();
    return () => { active = false; subscribers.delete(reload); };
  }, [list]);
  return value;
}

/** A stored list value as people read it: the item's name in the screen's language, else `fallback` (e.g. the value's
 * usual words, MD-003), else the stored text. */
export function useListName(list: ListName, fallback?: (key: string) => string | undefined): (key: string | null | undefined) => string {
  const locale = useLocale();
  const all = useListItems(list);
  return (key) => {
    if (!key) return "—";
    const found = all?.find(i => i.key === key);
    return found ? localName(found, locale) : fallback?.(key) ?? "—";
  };
}

/** All the organization's products (active and not), or null while loading. */
export function useProducts(): Product[] | null {
  const [value, setValue] = useState<Product[] | null>(products?.value ?? null);
  useEffect(() => {
    let active = true;
    const reload = async () => { const current = generation; const v = await loadProducts(); if (active && current === generation) setValue(v); };
    subscribers.add(reload); void reload();
    return () => { active = false; subscribers.delete(reload); };
  }, []);
  return value;
}

/** The VAT rate and default currency (15 % and SAR until the organization sets its own, or while loading). */
export function useBusinessSettings(): { vatRate: number; currency: "SAR" | "USD"; loaded: boolean } {
  const [value, setValue] = useState<BusinessSettings | null>(settings?.value ?? null);
  useEffect(() => {
    let active = true;
    const reload = async () => { const current = generation; const v = await loadSettings(); if (active && current === generation) setValue(v); };
    subscribers.add(reload); void reload();
    return () => { active = false; subscribers.delete(reload); };
  }, []);
  return { vatRate: value ? Number(value.vat_rate) : 15, currency: value?.default_currency ?? "SAR", loaded: value !== null };
}

/** A product type as people read it: the product's name in the screen's language, else the stored text. */
export function useProductName(): (key: string | null | undefined) => string {
  const locale = useLocale();
  const all = useProducts();
  return (key) => {
    if (!key) return "—";
    const found = all?.find(p => p.key === key);
    return found ? localName(found, locale) : "—";
  };
}

/** MD-003: the choices of a classification list — its active items, in the screen's language, and the value a record
 * already holds even when deactivated — or `fallback` keys while the organization's list is empty or loading. */
export function useListChoices(list: ListName, fallback: readonly string[], fallbackLabel: (key: string) => string,
                               current?: string | null): { key: string; label: string }[] {
  const locale = useLocale();
  const all = useListItems(list);
  const named = (i: ListItem) => localName(i, locale);
  if (!all || all.length === 0) {
    const keys = current && !fallback.includes(current) ? [...fallback, current] : [...fallback];
    return keys.map(key => ({ key, label: fallbackLabel(key) }));
  }
  const choices = all.filter(i => i.active).map(i => ({ key: i.key, label: named(i) }));
  if (current && !choices.some(c => c.key === current)) {
    const held = all.find(i => i.key === current);
    choices.push({ key: current, label: held ? named(held) : fallbackLabel(current) });
  }
  return choices;
}

/** MD-003: a classification that used to be fixed (enums.<entity>.<field>): its name from the organization's list, else
 * its usual words. */
export function useClassificationName(list: ListName, entity: string, field: string) {
  const t = useTranslations();
  return useListName(list, (key) => getEnumLabel(entity, field, key, t));
}

/** MD-003: its choices from the organization's list (the usual keys while the list is empty), with their names. */
export function useClassificationChoices(list: ListName, usual: readonly string[], entity: string, field: string, current?: string | null) {
  const t = useTranslations();
  return useListChoices(list, usual, (key) => getEnumLabel(entity, field, key, t), current);
}
