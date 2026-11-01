import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  server: { port: 5174, strictPort: true, proxy: { '/api': 'http://127.0.0.1:8001' } },
  test: {
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
  },
  build: { chunkSizeWarningLimit: 750 },
});
