// Copies the built chunks into public/ so Vite serves them at /chunks/<tile>/.
// Source: data/processed/chunks/<tile>/ (produced by pipeline/greedy_mesher.py).
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, '..', '..', 'data', 'processed', 'chunks');
const dst = join(here, '..', 'public', 'chunks');

if (!existsSync(src)) {
  console.error(`no chunks at ${src}; run pipeline/greedy_mesher.py first`);
  process.exit(1);
}
rmSync(dst, { recursive: true, force: true });
mkdirSync(dst, { recursive: true });
for (const tile of readdirSync(src)) cpSync(join(src, tile), join(dst, tile), { recursive: true });
console.log(`synced ${readdirSync(dst).join(', ')} -> public/chunks`);
