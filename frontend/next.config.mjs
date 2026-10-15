import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allows production verification to run beside an active development server.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // SEC-001: the browser talks to the API through this site's own address (same origin), as production does behind its
  // reverse proxy: the session-renewal cookie is first-party (SameSite works, nothing cross-site), and no CORS is needed.
  async rewrites() {
    const backend = (process.env.BACKEND_URL || "http://127.0.0.1:8080").replace(/\/$/, "");
    return [{ source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` }];
  },
  async headers() {
    const resetHeaders = ["/reset-password", "/platform/reset-password", "/forgot-password", "/platform/forgot-password"].map(source => ({
      source,
      headers: [
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "Cache-Control", value: "no-store" },
        { key: "X-Robots-Tag", value: "noindex, nofollow" },
      ],
    }));
    const securityHeaders = [{ source: "/:path*", headers: [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      // Not inside another site's frame (clickjacking); the app's own report previews stay same-origin.
      { key: "X-Frame-Options", value: "SAMEORIGIN" },
    ] }];
    if (process.env.NODE_ENV !== "development") return [...securityHeaders, ...resetHeaders];
    return [
      ...securityHeaders,
      ...resetHeaders,
      {
        source: "/_next/static/(.*)",
        headers: [
          { key: "Cache-Control", value: "no-store, must-revalidate" },
        ],
      },
    ];
  },
};

export default withNextIntl(nextConfig);
