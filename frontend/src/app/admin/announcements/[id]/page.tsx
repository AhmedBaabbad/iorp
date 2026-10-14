"use client";

import { use } from "react";

import { AccessDeniedMessage } from "@/components/AccessDeniedMessage";
import { useHasAnyPermission } from "@/features/auth/permission-hooks";
import { AnnouncementDetail } from "@/features/announcements/Announcements";
import { ANNOUNCEMENTS_PAGE } from "@/lib/notifications";

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const allowed = useHasAnyPermission(ANNOUNCEMENTS_PAGE);
  return allowed ? <AnnouncementDetail id={id} /> : <AccessDeniedMessage />;
}
