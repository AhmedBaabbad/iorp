"use client";

import { Suspense } from "react";

import { AccessDeniedMessage } from "@/components/AccessDeniedMessage";
import { useHasAnyPermission } from "@/features/auth/permission-hooks";
import { AnnouncementsList } from "@/features/announcements/Announcements";
import { ANNOUNCEMENTS_PAGE } from "@/lib/notifications";

export default function Page() {
  const allowed = useHasAnyPermission(ANNOUNCEMENTS_PAGE);
  return allowed ? <Suspense><AnnouncementsList /></Suspense> : <AccessDeniedMessage />;
}
