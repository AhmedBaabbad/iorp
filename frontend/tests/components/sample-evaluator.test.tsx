import { cleanup, render, screen } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import { afterEach, expect, it, vi } from 'vitest';
import { loadMessages } from '@/i18n/messages';
import { SampleEvaluationsList } from '@/features/sample-evaluations/components/SampleEvaluationsList';

vi.mock('@/hooks/useFormatter', () => ({ useFormatter: () => ({ date: () => '06/10/2026' }) }));
// RBAC-002: the list asks which evaluation actions the user may take.
vi.mock('@/features/auth/permission-hooks', () => ({ usePermission: () => false, useHasAnyPermission: () => false }));
vi.mock('@/features/sample-evaluations/api/sample-evaluations-api', () => ({ listSampleEvaluations: async () => [{
  id: 'e1', sample_id: 's1', evaluation_date: '2026-10-06', result_status: 'needs_modification', next_action: 'revise_sample',
  comments: 'Please revise', evaluated_by_user_id: '00aca8aa-1234', evaluated_by_name: 'أحمد محمد',
}] }));
afterEach(cleanup);
it('shows the evaluator name instead of a shortened UUID', async () => {
  const messages = await loadMessages('ar');
  render(<NextIntlClientProvider locale="ar" messages={messages} timeZone="UTC"><SampleEvaluationsList sampleId="s1" /></NextIntlClientProvider>);
  expect(await screen.findByText(/أحمد محمد/)).toBeTruthy();
  expect(screen.queryByText(/00aca8aa/)).toBeNull();
});
