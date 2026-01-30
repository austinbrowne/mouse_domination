import { Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

export const TEST_USER = {
  email: 'testuser@example.com',
  password: 'TestPassword123!',
};

const STORAGE_STATE_PATH = path.join(__dirname, '..', '..', 'test-results', '.auth-state.json');

export async function login(page: Page) {
  // Reuse stored session if available and fresh (< 5 min old)
  if (fs.existsSync(STORAGE_STATE_PATH)) {
    const stat = fs.statSync(STORAGE_STATE_PATH);
    const ageMs = Date.now() - stat.mtimeMs;
    if (ageMs < 5 * 60 * 1000) {
      await page.context().addCookies(
        JSON.parse(fs.readFileSync(STORAGE_STATE_PATH, 'utf-8'))
      );
      // Verify session is still valid
      const resp = await page.goto('/');
      if (resp && !resp.url().includes('/auth/login')) {
        return; // Session still valid
      }
    }
  }

  // Fresh login
  await page.goto('/auth/login');
  await page.getByRole('textbox', { name: 'Email' }).fill(TEST_USER.email);
  await page.getByRole('textbox', { name: 'Password' }).fill(TEST_USER.password);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForURL('**/', { timeout: 15000 });

  // Save cookies for reuse
  const cookies = await page.context().cookies();
  const dir = path.dirname(STORAGE_STATE_PATH);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(STORAGE_STATE_PATH, JSON.stringify(cookies));
}
