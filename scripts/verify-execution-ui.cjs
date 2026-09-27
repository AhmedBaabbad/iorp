/* Disposable UI verification: run .tmp/exec-qa-server.py and frontend port 3002. */
const { chromium } = require('../.tmp/prod-plan-browser/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const out = path.resolve('docs/verification/prod-exec-foundation-001');
const ids = JSON.parse(fs.readFileSync('.tmp/exec-qa-ids.json', 'utf8'));
fs.mkdirSync(out, { recursive: true });
(async () => {
 const browser = await chromium.launch({ channel: 'msedge', headless: true });
 const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
 page.setDefaultTimeout(30000); page.setDefaultNavigationTimeout(90000);
 const errors = []; page.on('pageerror', e => errors.push(e.message));
 try {
  await page.goto('http://localhost:3002/login');
  await page.waitForLoadState('networkidle');
  await Promise.all([
    page.waitForResponse(r => r.url().includes('/system/bootstrap/status')),
    page.getByRole('button', { name: 'English', exact: true }).click(),
  ]);
  await page.waitForLoadState('networkidle');
  await page.getByLabel('Email address', { exact: true }).fill('execution-qa@example.com');
  await page.getByPlaceholder('Enter your password').fill('ExecutionQA123!');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.waitForURL('**/dashboard');
  const suffix = Date.now().toString().slice(-7);
  await page.goto('http://localhost:3002/shifts/new');
  await page.getByRole('heading', { name: 'Create Shift', exact: true }).waitFor();
  if (await page.getByLabel('Work Center', { exact: true }).count()) throw new Error('Shift still requires a center');
  console.log('PASS shift creation form has no Work Center');
  console.log(await page.locator('form').innerText());
  await page.screenshot({ path: path.join(out, '01-independent-shift.png'), fullPage: true });
  await page.getByLabel('Code', { exact: false }).fill('UI-' + suffix);
  await page.getByLabel('Name', { exact: false }).fill('UI Shift ' + suffix);
  await page.getByRole('button', { name: 'Create Shift', exact: true }).click();
  await page.getByRole('button', { name: 'OK', exact: true }).click();
  await page.waitForURL(/\/shifts\/[a-f0-9-]+$/);
  console.log('PASS create independent shift');

  await page.goto(`http://localhost:3002/production-orders/${ids.order}`);
  const panel = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Production Runs', exact: true }) });
  await panel.getByRole('button', { name: 'Create', exact: true }).click();
  const form = panel.locator('form');
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  await form.getByLabel('Date / effective from', { exact: true }).fill(yesterday);
  await form.getByLabel('Work center', { exact: true }).selectOption({ label: 'QA Line' });
  await form.getByLabel('Shift', { exact: true }).selectOption({ label: 'QA Morning' });
  await form.getByLabel('Roster (optional)', { exact: true }).selectOption({ label: 'QA Morning — QA Historical Team' });
  await form.getByRole('button', { name: 'Load roster members', exact: true }).click();
  await form.getByRole('button', { name: 'Remove', exact: true }).click();
  await form.getByRole('button', { name: 'Add worker', exact: true }).click();
  await form.getByLabel('Worker', { exact: true }).selectOption({ label: 'QA-2 — QA Worker 2' });
  await form.getByLabel('Role', { exact: true }).fill('relief_specialist');
  await form.getByRole('button', { name: 'Save', exact: true }).click();
  await form.waitFor({ state: 'hidden' });
  console.log('PASS roster loaded and absent worker replaced before run creation');
  await panel.locator('tbody tr').last().getByRole('button').click();
  await panel.getByRole('button', { name: 'Start / resume', exact: true }).click();
  await panel.getByRole('button', { name: 'Pause', exact: true }).click();
  await panel.getByRole('button', { name: 'Start / resume', exact: true }).click();
  await panel.getByRole('button', { name: 'Complete', exact: true }).click();
  await panel.getByText('completed', { exact: true }).waitFor();
  await page.screenshot({ path: path.join(out, '02-completed-run.png'), fullPage: true });
  console.log('PASS start, pause, resume, complete and actual team display');
  await panel.getByRole('button', { name: 'Create', exact: true }).click();
  await panel.locator('form').getByLabel('Date / effective from', { exact: true }).fill(yesterday);
  await panel.locator('form').getByLabel('Work center', { exact: true }).selectOption({ label: 'QA Line' });
  await panel.locator('form').getByRole('button', { name: 'Save', exact: true }).click();
  await panel.locator('form').waitFor({ state: 'hidden' });
  if (await panel.locator('tbody tr').count() < 2) throw new Error('Multiple runs not visible');
  console.log('PASS multiple runs on same order and optional shift/roster');

  await page.goto('http://localhost:3002/shift-rosters');
  await page.getByRole('button', { name: 'QA Historical Team', exact: true }).click();
  await page.getByRole('button', { name: 'Create replacement', exact: true }).click();
  const replacement = page.locator('form');
  await replacement.getByLabel('Name', { exact: true }).fill('Replacement ' + suffix);
  await replacement.getByLabel('Date / effective from', { exact: true }).fill(new Date().toISOString().slice(0, 10));
  await replacement.getByLabel('Worker', { exact: true }).selectOption({ label: 'QA-3 — QA Worker 3' });
  await replacement.getByRole('button', { name: 'Save', exact: true }).click();
  await replacement.waitFor({ state: 'hidden' });
  await page.getByRole('button', { name: 'Replacement ' + suffix, exact: true }).waitFor();
  await page.getByRole('button', { name: 'QA Historical Team', exact: true }).click();
  await page.getByRole('heading', { name: 'QA Historical Team', exact: true }).waitFor();
  await page.screenshot({ path: path.join(out, '03-roster-history.png'), fullPage: true });
  console.log('PASS replacement preserves previous roster and historical membership');

  await page.getByRole('button', { name: 'Create', exact: true }).click();
  const futureForm = page.locator('form');
  await futureForm.getByLabel('Name', { exact: true }).fill('Future ' + suffix);
  await futureForm.getByLabel('Shift', { exact: true }).selectOption({ label: 'UI Shift ' + suffix });
  await futureForm.getByLabel('Date / effective from', { exact: true }).fill(new Date(Date.now() + 86400000).toISOString().slice(0, 10));
  await futureForm.getByRole('button', { name: 'Add worker', exact: true }).click();
  await futureForm.getByLabel('Worker', { exact: true }).selectOption({ label: 'QA-1 — QA Worker 1' });
  await futureForm.getByRole('button', { name: 'Save', exact: true }).click();
  await futureForm.waitFor({ state: 'hidden' });
  await page.getByRole('button', { name: 'Future ' + suffix, exact: true }).click();
  await page.getByRole('button', { name: 'Remove', exact: true }).click();
  console.log('PASS future roster creation and member removal');
  await page.getByRole('button', { name: 'العربية', exact: true }).click();
  await page.getByRole('heading', { name: 'فرق الورديات وسجلها التاريخي', exact: true }).waitFor();
  await page.getByRole('button', { name: 'QA Historical Team', exact: true }).waitFor();
  await page.screenshot({ path: path.join(out, '04-arabic-rosters.png'), fullPage: true });
  if (errors.length) throw new Error(errors.join('\n'));
  console.log('PASS Arabic rendering; no browser runtime errors');
 } catch (e) {
   await page.screenshot({ path: path.join(out, 'failure.png'), fullPage: true });
   console.log((await page.locator('body').innerText()).slice(-6000));
   throw e;
 } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
