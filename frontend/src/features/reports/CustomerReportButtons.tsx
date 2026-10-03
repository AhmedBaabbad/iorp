"use client";
import { useEffect, useRef, useState } from 'react';
import { useTranslations } from 'next-intl';
import { useAuth } from '@/features/auth';
import { Definition, getDefinitions } from './api';
import { ReportForm } from './ReportForm';
import s from './reports.module.css';

export function CustomerReportButtons({ customerId }: { customerId: string }) {
  const t = useTranslations('reports.customerReports');
  const { hasPermission } = useAuth();
  const [definition, setDefinition] = useState<Definition>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { if (definition) dialog.current?.showModal(); }, [definition]);
  async function open(key: string) {
    setBusy(true); setError('');
    try {
      const definitions = await getDefinitions('customers', { customer_id: customerId });
      const found = definitions.find(d => d.key === `customers.${key}`);
      if (!found) throw new Error();
      setDefinition(found);
    } catch { setError(t('loadError')); }
    finally { setBusy(false); }
  }
  return <>
    {hasPermission('commercial:customers:read') && ['customer_profile', 'customer_statement'].map(key => hasPermission(`reports:customers:${key}`) &&
      <button className={s.button} disabled={busy} key={key} onClick={() => void open(key)}>{key === 'customer_profile' ? t('profile') : t('statement')}</button>)}
    {error && <span role="alert">{error}</span>}
    <dialog ref={dialog} onClose={() => setDefinition(undefined)} style={{ width: 'min(1100px, 95vw)', maxHeight: '90vh', border: 0, borderRadius: 12 }}>
      <button className={s.button} onClick={() => dialog.current?.close()}>{t('close')}</button>
      {definition && <ReportForm key={definition.key} definition={definition} fixedParams={{ customer_id: customerId }} />}
    </dialog>
  </>;
}
