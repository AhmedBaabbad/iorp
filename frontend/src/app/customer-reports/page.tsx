"use client";
import { useTranslations } from 'next-intl';
import { ReportCenter } from '@/features/reports/ReportsPage';
import { PermissionGate } from '@/features/auth/permission-gate';
import { CUSTOMER_REPORTS } from '@/features/reports/customer-permissions';
export default function Page() {
  const t = useTranslations('reports.customerReports');
  return <PermissionGate code="commercial:customers:read"><PermissionGate anyOf={CUSTOMER_REPORTS}><ReportCenter module="customers" title={t('title')} /></PermissionGate></PermissionGate>;
}
