"use client";
import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { usePermission } from '@/features/auth/permission-hooks';
import { getDefinitions, Definition } from './api';
import { ReportForm } from './ReportForm';
import s from './reports.module.css';

// One record's report from its own page (e.g. a quality check): the report center's form with the record fixed.
// The server still decides which sections the user may include.
export function RecordReportButton({ module, reportKey, field, id, permission, label }: {
  module: string; reportKey: string; field: string; id: string; permission: string; label: string;
}) {
  const t = useTranslations('reports.record');
  const allowed = usePermission(permission);
  const [definition, setDefinition] = useState<Definition | null>(null);
  const [error, setError] = useState('');
  if (!allowed) return null;
  const open = () => {
    setError('');
    getDefinitions(module, { [field]: id }).then(ds => { const d = ds.find(x => x.key === reportKey); if (d) setDefinition(d); else setError(t('unavailable')); })
      .catch(() => setError(t('loadError')));
  };
  return <>
    <button type="button" className={s.button} onClick={open}>{label}</button>
    {error && <p role="alert">{error}</p>}
    {definition && <div role="dialog" aria-modal="true" aria-label={label} className={s.dialog} onKeyDown={e => { if (e.key === 'Escape') setDefinition(null); }}>
      <button type="button" className={s.button} onClick={() => setDefinition(null)}>{t('close')}</button>
      <ReportForm definition={definition} fixedParams={{ [field]: id }} />
    </div>}
  </>;
}
