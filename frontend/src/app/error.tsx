"use client";

import { RouteErrorPage } from "@/components/feedback/route-error-page";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <RouteErrorPage reset={reset} />;
}
