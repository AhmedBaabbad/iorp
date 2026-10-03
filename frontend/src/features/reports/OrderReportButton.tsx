"use client";
import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { useAuth } from '@/features/auth';
import { getDefinitions, Definition } from './api';
import { ReportForm } from './ReportForm';
import s from './reports.module.css';
import { REPORT } from "@/lib/production-permissions";

// The order's full report from its detail page: same form, the order fixed.
export function OrderReportButton({ orderId }: { orderId: string }) {
  const t = useTranslations('production.reports.order');
  const { hasPermission } = useAuth();
  const [definition, setDefinition] = useState<Definition | null>(null);
  const [error, setError] = useState('');
  if (!hasPermission(REPORT.ORDER_FULL)) return null;
  const open = () => {
    setError('');
    getDefinitions('production', { order_id: orderId }).then(ds => { const d = ds.find(x => x.key === 'production.order_full'); if (d) setDefinition(d); else setError(t('unavailable')); })
      .catch(() => setError(t('loadError')));
  };
  return <>
    <button className={s.button} onClick={open}>{t('button')}</button>
    {error && <p role="alert">{error}</p>}
    {definition && <div role="dialog" aria-modal="true" aria-label={t('button')} className={s.dialog} onKeyDown={e => { if (e.key === 'Escape') setDefinition(null); }}>
      <button className={s.button} onClick={() => setDefinition(null)}>{t('close')}</button>
      <ReportForm definition={definition} fixedParams={{ order_id: orderId }} />
    </div>}
  </>;
}
