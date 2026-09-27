import { NextResponse, type NextRequest } from "next/server";

import { DEFAULT_LOCALE, LOCALE_COOKIE_NAME, isLocale } from "@/i18n/config";

export function middleware(request: NextRequest) {
  const requestedLocale = request.cookies.get(LOCALE_COOKIE_NAME)?.value;
  const locale = isLocale(requestedLocale) ? requestedLocale : DEFAULT_LOCALE;
  const requestHeaders = new Headers(request.headers);

  requestHeaders.set("x-iorp-locale", locale);

  return NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
