// Proposed read-only staging benchmark, NOT executed during the audit.
// k6 run -e BASE_URL=https://isolated-staging/api/v1 -e TOKEN=... -e VUS=25 load-baseline.js
// Obtain a fresh token before each run; never commit tokens or target a live tenant.
import http from 'k6/http';
import { check, sleep } from 'k6';
if (!__ENV.BASE_URL || !__ENV.TOKEN) throw new Error('Explicit isolated staging BASE_URL and TOKEN required');
export const options = {
  vus: Number(__ENV.VUS || 5), duration: '5m',
  summaryTrendStats: ['avg', 'med', 'p(95)', 'p(99)', 'max'],
};
const headers = { Authorization: `Bearer ${__ENV.TOKEN}` };
export default function () {
  const pick = Math.random();
  const path = pick < 0.7 ? '/commercial/customers?page=1&page_size=50' :
    pick < 0.9 ? '/commercial/samples?page=1&page_size=50' : '/commercial/dashboard?period=3m';
  const response = http.get(__ENV.BASE_URL.replace(/\/$/, '') + path, { headers, timeout: '30s', tags: { endpoint: path.split('?')[0] } });
  check(response, { 'status 200': r => r.status === 200 });
  sleep(1);
}
