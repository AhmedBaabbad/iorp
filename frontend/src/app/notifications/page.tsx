"use client";

import { Suspense } from "react";

import { NotificationsPage } from "@/features/notifications/NotificationsPage";

/** Every signed-in user's own notifications: no permission needed. */
export default function Page() {
  return <Suspense><NotificationsPage /></Suspense>;
}
