"use client";
import { useEffect, useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { PageFrame } from '@/components/layout/page-frame';
import { getDefinitions, Definition } from './api';
import { ReportForm } from './ReportForm';
import s from './reports.module.css';

// One report center per module: pick a report, set its filters, preview or download it.
// Who prepared a report, when and its reference number are printed in the report itself.
export function ReportCenter({ module, title }: { module: string; title: string }) {
  const t = useTranslations('reports');
  const ar = useLocale() === 'ar';
  const [definitions, setDefinitions] = useState<Definition[]>([]);
  const [selected, setSelected] = useState('');
  const [error, setError] = useState('');

  useEffect(() => { getDefinitions(module).then(setDefinitions).catch(() => setError(t('center.loadError'))); }, [t, module]);
  const definition = definitions.find(d => d.key === selected);

  return <PageFrame title={title} subtitle={t('center.subtitle')}>
    {error && <p role="alert" className={s.error}>{error}</p>}
    <div className={s.cards}>{definitions.map(d => <button key={d.key} className={`${s.card} ${selected === d.key ? s.selected : ''}`} onClick={() => setSelected(d.key)}>
      <strong>{ar ? d.title_ar : d.title_en}</strong></button>)}</div>
    {!definitions.length && !error && <p>{t('center.empty')}</p>}
    {definition && <ReportForm key={definition.key} definition={definition} />}
  </PageFrame>;
}
