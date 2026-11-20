"use client";
import { NextIntlClientProvider } from "next-intl";
import type { ComponentProps } from "react";
import { missingTranslation } from "./missing-message";

/** Also protects legacy translation calls whose namespaces now reference shared enums. */
export function TranslationProvider(props: Pick<ComponentProps<typeof NextIntlClientProvider>, "locale" | "messages" | "children">) {
  return <NextIntlClientProvider {...props} onError={() => undefined}
    getMessageFallback={({ namespace }) => missingTranslation(namespace || "messages")} />;
}
