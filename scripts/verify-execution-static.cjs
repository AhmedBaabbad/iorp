const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'docs/verification/prod-exec-foundation-001');
const jobs = {
 typescript: ['node_modules/typescript/bin/tsc', '--noEmit', '--incremental', 'false'],
 eslint: ['node_modules/eslint/bin/eslint.js', 'src/features/production-execution', 'src/features/shifts', 'src/features/shift-reports/components/ShiftReportForm.tsx', 'src/app/shift-rosters', 'src/features/production-orders/components/ProductionOrderDetail.tsx'],
 i18n: ['scripts/check-i18n.mjs'],
};
const results = {};
for (const [name, args] of Object.entries(jobs)) {
 const r = spawnSync(process.execPath, args, { cwd: path.join(root, 'frontend'), encoding: 'utf8' });
 fs.writeFileSync(path.join(out, `${name}.log`), (r.stdout || '') + (r.stderr || ''));
 results[name] = { exit_code: r.status, command: `node ${args.join(' ')}` };
 if (r.status !== 0) process.exitCode = 1;
}
fs.writeFileSync(path.join(out, 'static-results.json'), JSON.stringify(results, null, 2));
console.log(JSON.stringify(results));
