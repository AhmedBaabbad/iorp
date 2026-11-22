"use client";
import { useTranslations } from "next-intl";
import { PageFrame } from "@/components/layout/page-frame";
import { PermissionGate } from "@/features/auth/permission-gate";
import { DirectoryPanel } from "@/features/reference-directory/DirectoryPanel";
import { Tabs } from "@/components/ui/Tabs";
export default function Page(){
  const t=useTranslations("directory");
  return <PermissionGate code="shipping:directory:read"><PageFrame title={t("title")} subtitle={t("subtitle")}>
    <Tabs label={t("title")} defaultTab="drivers" items={(["drivers","vehicles","carriers"] as const).map(kind=>({
      id:kind,label:t(`fields.${kind}`),content:<DirectoryPanel kind={kind} path={`/shipping/directory/${kind}`} writePermission="shipping:directory:write"/>,
    }))}/>
  </PageFrame></PermissionGate>;
}
