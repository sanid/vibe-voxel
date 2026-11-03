import { resolve } from 'node:path';
import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  worker: { format: 'es' },
  build: {
    chunkSizeWarningLimit: 2000,
    // two pages, one engine: Warsaw at /, Berlin at /berlin/ (its data in public/berlin/data, see src/place.ts)
    rollupOptions: { input: { main: resolve(import.meta.dirname, 'index.html'), berlin: resolve(import.meta.dirname, 'berlin/index.html') } },
  },
});
