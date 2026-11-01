import { test, expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
const secret =
  process.env.TEXT2CAD_SECRET ??
  readFileSync('../.env', 'utf8')
    .trim()
    .replace(/^TEXT2CAD_SECRET=/, '');
async function login(page: Page) {
  await expect
    .poll(
      async () => {
        try {
          return (await (await page.request.get('/api/health')).json()).ready;
        } catch {
          return false;
        }
      },
      { timeout: 60000 },
    )
    .toBe(true);
  await page.goto('/');
  await page.getByLabel('Local secret').fill(secret);
  const loggedIn = page.waitForResponse((r) => r.url().endsWith('/sessions'));
  await page.getByRole('button', { name: /Connect workspace/ }).click();
  expect((await loggedIn).ok()).toBe(true);
  await expect(page.getByLabel('Local secret')).not.toBeVisible();
  await page.getByRole('button', { name: 'Requirements', exact: true }).click();
  await expect(page.getByRole('button', { name: /Interpret requirements/ })).toBeEnabled();
}
async function screenshot(page: Page, path: string) {
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({ path, fullPage: true });
}
async function generate(page: Page) {
  await page.getByRole('checkbox', { name: /I reviewed dimensions/ }).check();
  const submitted = page.waitForResponse(
    (r) => r.url().endsWith('/generate') && r.request().method() === 'POST',
  );
  await page.getByRole('button', { name: /Confirm & generate/ }).click();
  expect((await submitted).ok()).toBe(true);
  await expect(page.getByRole('button', { name: 'Cancel generation' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Cancel generation' })).not.toBeVisible({
    timeout: 70000,
  });
  await expect(page.getByRole('alert')).not.toBeVisible();
  await expect(page.getByText('Validated STL · dimensions in mm', { exact: true })).toBeVisible({
    timeout: 15000,
  });
}

test('brief to generated CAD, revision diff, invalid hole, undo and handoff', async ({ page }) => {
  await login(page);
  await page.getByRole('button', { name: /Interpret requirements/ }).click();
  await expect(page.getByLabel('thickness_mm', { exact: true })).toHaveValue('5');
  await expect(page.getByRole('button', { name: /Confirm & generate/ })).toBeDisabled();
  await generate(page);
  await screenshot(page, '../assets/screenshots/studio.png');
  await page.getByLabel('Design request').fill('Increase thickness to 6 mm.');
  await page.getByRole('button', { name: /Interpret change/ }).click();
  await expect(page.getByLabel('thickness_mm', { exact: true })).toHaveValue('6');
  await expect(page.getByText('Review the changes')).toBeVisible();
  await generate(page);
  const parsed = page.waitForResponse(
    (r) => r.url().endsWith('/parse') && r.request().method() === 'POST',
  );
  await page.getByLabel('Design request').fill('Move one hole beyond the edge.');
  await page.getByRole('button', { name: /Interpret change/ }).click();
  expect((await (await parsed).json()).status).toBe('invalid');
  await expect(page.locator('.parse-result')).toContainText('clearance');
  await page.getByRole('button', { name: /Revision history/ }).click();
  await expect(page.locator('.revision-list article')).toHaveCount(2);
  await page
    .getByRole('button', { name: /Preview revision/ })
    .last()
    .click();
  await expect(page.getByLabel('thickness_mm', { exact: true })).toHaveValue('5');
  await expect(page.getByText('Validated STL · dimensions in mm', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /Validation/ }).click();
  await expect(page.getByText('CHECKS PASSED')).toBeVisible();
  await screenshot(page, '../assets/screenshots/validation.png');
  await page.getByRole('button', { name: /Exports/ }).click();
  const exported = page.waitForEvent('download');
  await page.getByRole('button', { name: /Download ZIP/ }).click();
  expect((await exported).suggestedFilename()).toContain('.zip');
});

for (const family of ['L-bracket', 'Electronics enclosure', 'Gripper finger'])
  test(`generate and preview ${family}`, async ({ page }) => {
    await login(page);
    await page
      .locator('.sample-grid')
      .getByRole('button', { name: new RegExp(family) })
      .click();
    await page.getByRole('button', { name: /Interpret requirements/ }).click();
    await expect(page.getByText('Interpretation ready for review')).toBeVisible();
    await generate(page);
    await screenshot(
      page,
      `../assets/screenshots/${family.toLowerCase().replaceAll(' ', '-')}.png`,
    );
  });

test('tablet layout and missing-dimension clarification', async ({ page }) => {
  await page.setViewportSize({ width: 820, height: 1180 });
  await login(page);
  await page.getByLabel('Design request').fill('Plate length 60 mm width 25 mm.');
  await page.getByRole('button', { name: /Interpret requirements/ }).click();
  await expect(page.locator('.parse-result')).toContainText('Provide thickness');
  await page.getByLabel('Clarification', { exact: true }).fill('thickness 5 mm');
  await page.getByRole('button', { name: /Add detail & reinterpret/ }).click();
  await expect(page.getByText('Interpretation ready for review')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
