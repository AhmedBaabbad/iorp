import type { ReactNode } from "react";
import { cookies } from "next/headers";
import { NextIntlClientProvider } from "next-intl";
import { IBM_Plex_Sans_Arabic } from "next/font/google";

import { AuthProvider } from "@/features/auth";
import { ThemeProvider } from "@/components/theme/theme-provider";
import { Notifications } from "@/components/notify/Notifications";
import { DEFAULT_LOCALE, LOCALE_COOKIE_NAME, isLocale, isRTL } from "@/i18n/config";
import { loadMessages } from "@/i18n/messages";

import "./globals.css";
import { themeScript } from "@/components/theme/theme-config";

// DASH-002: one clear typeface for Arabic and English, served with the app.
const plex = IBM_Plex_Sans_Arabic({ subsets: ["arabic", "latin"], weight: ["400", "500", "600", "700"], display: "swap" });

export const metadata = {
  title: "IORP",
  description: "Industrial Operations & Relationship Platform",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  const requestedLocale = cookieStore.get(LOCALE_COOKIE_NAME)?.value;
  const locale = isLocale(requestedLocale) ? requestedLocale : DEFAULT_LOCALE;
  const messages = await loadMessages(locale);


  return (
    <html lang={locale} dir={isRTL(locale) ? "rtl" : "ltr"} className={plex.className} suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
      {/* Browser extensions (reading tools, translators) add attributes to <body> before React loads; they are not ours. */}
      <body style={{ margin: 0 }} suppressHydrationWarning>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <ThemeProvider><AuthProvider>{children}<Notifications /></AuthProvider></ThemeProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
