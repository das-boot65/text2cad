import { test, expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
const secret = readFileSync('../.env', 'utf8')
  .split(/\r?\n/)
  .find((line) => line.startsWith('TEXT2CAD_SECRET='))!
  .slice('TEXT2CAD_SECRET='.length)
  .trim();
async function login(page: Page) {
  await page.goto('/');
  await page.getByLabel('Local secret').fill(secret);
  const response = page.waitForResponse((r) => r.url().endsWith('/api/sessions'));
  await page.getByRole('button', { name: /Connect workspace/ }).click();
  const auth = await (await response).json();
  await expect(page.getByLabel('Local secret')).not.toBeVisible();
  return auth;
}
async function navigate(page: Page, name: string) {
  const menu = page.getByRole('button', { name: 'Toggle project navigation', exact: true });
  if ((await menu.isVisible()) && (await menu.getAttribute('aria-expanded')) !== 'true')
    await menu.click();
  await page
    .getByRole('navigation', { name: 'Workspace' })
    .getByRole('button', { name, exact: true })
    .click();
}
async function savedModel(page: Page, family?: string) {
  const auth = await login(page);
  const headers = { Authorization: `Bearer ${auth.token}` };
  const projects = await (await page.request.get('/api/projects', { headers })).json();
  for (let i = 0; i < Math.min(8, projects.length); i++) {
    if (!projects[i].head_id) continue;
    const revision = await (
      await page.request.get(`/api/revisions/${projects[i].head_id}`, { headers })
    ).json();
    if (
      revision.generation?.state === 'completed' &&
      (!family || revision.spec.part_family === family)
    ) {
      await page.locator('.project-list button').nth(i).click();
      await expect(
        page.getByText('Validated STL · dimensions in mm', { exact: true }),
      ).toBeVisible();
      return revision;
    }
  }
  test.skip(true, 'No completed saved revision is available; run native design workflows first.');
  throw Error('No saved model');
}
test('draft constraints stay distinct from the previous generated model', async ({ page }) => {
  const revision = await savedModel(page);
  await page
    .getByLabel('Design request', { exact: true })
    .fill(`Increase thickness to ${revision.spec.parameters.thickness_mm + 1} mm.`);
  await page.getByRole('button', { name: /Interpret change/ }).click();
  await expect(page.locator('.build-summary')).toContainText('Uncommitted draft');
  await expect(page.locator('.draft-banner')).toContainText(revision.id.slice(0, 8));
  await navigate(page, 'Validation');
  await expect(page.getByText('CONSTRAINTS PASSED', { exact: true })).toBeVisible();
  await expect(page.getByText(/Prebuild parameters only/)).toBeVisible();
  await expect(page.getByText('CHECKS PASSED', { exact: true })).not.toBeVisible();
  await navigate(page, 'Exports');
  await expect(page.locator('.export-revision')).toContainText(revision.id.slice(0, 8));
  await expect(
    page.getByText('Uncommitted draft edits are not included in these files.', { exact: true }),
  ).toBeVisible();
  await navigate(page, 'Design studio');
  await page.getByRole('button', { name: 'Discard proposed changes', exact: true }).click();
  await expect(page.locator('.draft-banner')).not.toBeVisible();
  await expect(page.getByLabel('thickness_mm', { exact: true })).toHaveValue(
    String(revision.spec.parameters.thickness_mm),
  );
});
test('camera tools change real rendered pixels and both canvas themes work', async ({ page }) => {
  await savedModel(page);
  const canvas = page.getByRole('img', { name: /Interactive 3D model/ });
  const before = await canvas.screenshot();
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  await expect
    .poll(async () => Buffer.compare(before, await canvas.screenshot()), { timeout: 10000 })
    .not.toBe(0);
  await page.getByRole('button', { name: /Reset view/ }).click();
  await page.locator('.camera-menu summary').click();
  await page.getByRole('button', { name: 'Top view', exact: true }).click();
  await expect.poll(async () => Buffer.compare(before, await canvas.screenshot())).not.toBe(0);
  await page.locator('.camera-menu summary').click();
  await page.getByRole('button', { name: /Reset view/ }).click();
  const light = await canvas.screenshot();
  await page.getByRole('button', { name: 'Dark appearance', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect.poll(async () => Buffer.compare(light, await canvas.screenshot())).not.toBe(0);
  await page.getByRole('button', { name: /Wireframe/ }).click();
  await expect(page.getByRole('button', { name: /Wireframe/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await canvas.focus();
  await page.keyboard.press('+');
  await page.keyboard.press('0');
});
test('all tools and recent designs remain reachable at narrow widths', async ({ page }) => {
  await login(page);
  for (const width of [1440, 1024, 820, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const name of [
      'Design studio',
      'Revision history',
      'Validation',
      'Exports',
      'Evaluation',
      'Field guide',
    ]) {
      await navigate(page, name);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      await expect(page.locator('nav button[aria-current="page"]')).toHaveText(name);
    }
    await navigate(page, 'Design studio');
    for (const name of ['Requirements', 'Parameters', 'Model']) {
      await page.getByRole('button', { name, exact: true }).click();
      await expect(page.locator(`#studio-${name.toLowerCase()}`)).toBeVisible();
    }
    const menu = page.getByRole('button', { name: 'Toggle project navigation', exact: true });
    if (await menu.isVisible()) await menu.click();
    await expect(page.getByRole('button', { name: 'Dark appearance', exact: true })).toBeVisible();
    if (await menu.isVisible()) await menu.click();
  }
});
test('cancelling a real native job retains source and never enables a successful export', async ({
  page,
}) => {
  await login(page);
  await page.getByRole('button', { name: /Interpret requirements/ }).click();
  await page.getByRole('checkbox', { name: /I reviewed dimensions/ }).check();
  await page.getByRole('button', { name: /Confirm & generate/ }).click();
  await page.getByRole('button', { name: 'Cancel active build', exact: true }).click();
  await expect(page.locator('.build-summary')).toContainText('Build cancelled', { timeout: 20000 });
  await expect(page.locator('.project-identity')).toContainText('confirmed source');
  await expect(page.getByRole('button', { name: /Engineering handoff/ })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Retry geometry', exact: true })).toBeEnabled();
});
