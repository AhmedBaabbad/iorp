import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allows production verification to run beside an active development server.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  async headers() {
    if (process.env.NODE_ENV !== "development") return [];
    return [
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
