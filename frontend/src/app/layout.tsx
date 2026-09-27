import type { ReactNode } from "react";
import { cookies } from "next/headers";
import { NextIntlClientProvider } from "next-intl";

import { AuthProvider } from "@/features/auth";
import { ThemeProvider } from "@/components/theme/theme-provider";
import { DEFAULT_LOCALE, LOCALE_COOKIE_NAME, isLocale, isRTL } from "@/i18n/config";
import { loadMessages } from "@/i18n/messages";

import "./globals.css";

export const metadata = {
  title: "IORP",
  description: "Industrial Operations & Relationship Platform",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  const requestedLocale = cookieStore.get(LOCALE_COOKIE_NAME)?.value;
  const locale = isLocale(requestedLocale) ? requestedLocale : DEFAULT_LOCALE;
  const messages = await loadMessages(locale);

  const themeScript = `(function(){try{var p=localStorage.getItem('iorp-theme')||'system';var d=p==='dark'||(p==='system'&&matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light';document.documentElement.dataset.theme=d;document.documentElement.dataset.themePreference=p;document.documentElement.style.colorScheme=d}catch(e){}})()`;

  return (
    <html lang={locale} dir={isRTL(locale) ? "rtl" : "ltr"} suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
      <body style={{ margin: 0 }}>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <ThemeProvider><AuthProvider>{children}</AuthProvider></ThemeProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
