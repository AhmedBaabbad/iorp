"use client";

import { AccessDeniedMessage } from "@/components/AccessDeniedMessage";
import { usePermission } from "@/features/auth/permission-hooks";
import { AnnouncementForm } from "@/features/announcements/Announcements";
import { ANNOUNCEMENTS_SEND } from "@/lib/notifications";

export default function Page() {
  const allowed = usePermission(ANNOUNCEMENTS_SEND);
  return allowed ? <AnnouncementForm /> : <AccessDeniedMessage />;
}
