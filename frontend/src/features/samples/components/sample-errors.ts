import { ApiClientError } from '@/lib/api-client';
import { getApiErrorMessage } from '@/lib/api-error-handler';

const codes = new Set(['SAMPLE_PRODUCT_NOT_FOUND','SAMPLE_PRODUCT_INACTIVE','SAMPLE_PROPERTY_UNKNOWN',
  'SAMPLE_PROPERTY_REQUIRED','SAMPLE_PROPERTY_NUMBER','SAMPLE_PROPERTY_TEXT','SAMPLE_PROPERTY_CHOICE','SAMPLE_PROPERTY_KIND']);

export function sampleError(error: unknown, t: (key: string) => string, messages: (key: string) => string) {
  if (error instanceof ApiClientError && error.details && typeof error.details === 'object') {
    const body = error.details as { detail?: { code?: string; property_key?: string }; code?: string };
    const code = body.detail?.code ?? body.code;
    if (code && codes.has(code)) return t('properties.errors.' + code) + (body.detail?.property_key ? ` (${body.detail.property_key})` : '');
  }
  return getApiErrorMessage(error, messages);
}
