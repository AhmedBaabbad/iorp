"use client";
import { useLocale } from "next-intl";
import { PageFrame } from "@/components/layout/page-frame";
import { PermissionGate } from "@/features/auth/permission-gate";
import { DirectoryPanel } from "@/features/reference-directory/DirectoryPanel";
export default function Page(){const ar=useLocale()==="ar";return <PermissionGate code="shipping:directory:read"><PageFrame title={ar?"دليل النقل":"Transport directory"} subtitle={ar?"سائقون ومركبات وشركات نقل تُسجّل مرة وتُختار عند الاستخدام":"Save drivers, vehicles and carriers once and select them when needed"}>{(["drivers","vehicles","carriers"] as const).map(kind=><DirectoryPanel key={kind} kind={kind} path={`/shipping/directory/${kind}`} writePermission="shipping:directory:write"/>)}</PageFrame></PermissionGate>;}
