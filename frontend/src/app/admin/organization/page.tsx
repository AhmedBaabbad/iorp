"use client";
import { AccessDeniedMessage } from "@/components/AccessDeniedMessage";
import { usePermission } from "@/features/auth";
import { OrganizationProfilePage } from "@/features/organization-profile";
export default function Page() { return usePermission("foundation:organization:read") ? <OrganizationProfilePage /> : <AccessDeniedMessage />; }
