"use client";
import { AccessDeniedMessage } from "@/components/AccessDeniedMessage";
import { usePermission } from "@/features/auth";
import { OrganizationProfilePage } from "@/features/organization-profile";
export default function Page() { const profile=usePermission("foundation:organization:read");const branding=usePermission("organization:branding:read");return profile||branding ? <OrganizationProfilePage /> : <AccessDeniedMessage />; }
