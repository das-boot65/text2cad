import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  timeout: 180000,
  workers: 1,
  use: {
    baseURL: process.env.TEXT2CAD_BASE_URL ?? 'http://127.0.0.1:5174',
    viewport: { width: 1440, height: 1100 },
    video: 'on',
    trace: 'retain-on-failure',
    launchOptions: {
      args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
    },
  },
  reporter: 'list',
});
