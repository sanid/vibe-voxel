// Headless screenshot of a running viewer, for checking renders.
// Usage: node tools/shot.mjs <url> <out.png> [hour] [date]
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const [url = 'http://127.0.0.1:5174/', out = 'shot.png', hour, date] = process.argv.slice(2);
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
await page.goto(url, { waitUntil: 'load' });
await page.waitForFunction(() => window.__loaded || document.getElementById('status')?.textContent.startsWith('failed'), null, { timeout: 240000 });
if (hour) await page.evaluate((h) => { const el = document.getElementById('hour'); el.value = h; el.dispatchEvent(new Event('input')); }, hour);
if (date) await page.evaluate((d) => { const el = document.getElementById('date'); el.value = d; el.dispatchEvent(new Event('input')); }, date);
await page.waitForTimeout(1500);
console.log('status:', await page.textContent('#status'), '| sun:', await page.textContent('#sun'));
await page.screenshot({ path: out });
if (errors.length) console.log('console errors:', errors.slice(0, 5));
await browser.close();
