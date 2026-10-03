"use client";
import {useTranslations} from 'next-intl';
import {ReportCenter} from '@/features/reports/ReportsPage';
import { PermissionGate } from "@/features/auth/permission-gate";
import { PRODUCTION_REPORTS } from "@/lib/production-permissions";
export default function Page(){const t=useTranslations('production.reports');return <PermissionGate anyOf={PRODUCTION_REPORTS}><ReportCenter module="production" title={t('center.title')}/></PermissionGate>;}
