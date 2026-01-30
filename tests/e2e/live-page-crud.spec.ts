import { test, expect } from '@playwright/test';
import { login } from './auth';

// Uses Test Podcast (id=2) / Test Episode 1 (id=6) which starts empty.
// Test user (testuser@example.com) has admin access to this podcast.
const LIVE_URL = '/podcasts/2/episodes/6/live';

test.describe('Live Page - Item CRUD', () => {
  test.beforeEach(async ({ page }) => {
    // Auto-accept confirm dialogs (delete confirmations)
    page.on('dialog', dialog => dialog.accept());
    await login(page);
    await page.goto(LIVE_URL);
    await expect(page.getByRole('heading', { name: 'Test Episode 1' })).toBeVisible();
  });

  test('page loads with all sections and empty states', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'INTRO' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'NEWS' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'COMMUNITY RECAP' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'PERSONAL RAMBLINGS' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'OUTRO' })).toBeVisible();

    // All sections should have + Add buttons (intro + 4 news + community + personal + outro)
    const addButtons = page.getByRole('button', { name: '+ Add' });
    await expect(addButtons).toHaveCount(8);

    // Timer should show 00:00
    await expect(page.getByText('00:00')).toBeVisible();
  });

  test('add item via Add Item button', async ({ page }) => {
    // Click the first + Add button (Intro section)
    await page.getByRole('button', { name: '+ Add' }).first().click();

    // The visible title input should be focused
    const titleInput = page.getByPlaceholder('Topic title...').first();
    await expect(titleInput).toBeVisible();

    await titleInput.fill('Test Topic: Welcome Message');
    await page.getByRole('button', { name: 'Add Item' }).click();

    // Item should appear
    await expect(page.getByText('Test Topic: Welcome Message')).toBeVisible();

    // Clean up
    await page.getByRole('button', { name: 'Delete' }).first().click();
    await expect(page.getByText('Test Topic: Welcome Message')).not.toBeVisible();
  });

  test('add item via Enter key', async ({ page }) => {
    // Click Mice + Add button (2nd add button)
    await page.getByRole('button', { name: '+ Add' }).nth(1).click();

    const titleInput = page.getByPlaceholder('Topic title...').nth(1);
    await expect(titleInput).toBeVisible();
    await titleInput.fill('Razer Viper V3 HyperSpeed');
    await titleInput.press('Enter');

    // Item should appear and form should close
    await expect(page.getByText('Razer Viper V3 HyperSpeed')).toBeVisible();
    await expect(page.getByText('Mice (1)')).toBeVisible();

    // Clean up
    await page.getByRole('button', { name: 'Delete' }).first().click();
    await expect(page.getByText('Mice (0)')).toBeVisible();
  });

  test('cancel add form via Escape key', async ({ page }) => {
    await page.getByRole('button', { name: '+ Add' }).first().click();

    const titleInput = page.getByPlaceholder('Topic title...').first();
    await expect(titleInput).toBeVisible();
    await titleInput.fill('This should not be saved');
    await titleInput.press('Escape');

    // Form should close, item should NOT be added
    await expect(page.getByText('This should not be saved')).not.toBeVisible();
    await expect(page.getByText('No topics').first()).toBeVisible();
  });

  test('cancel add form via Cancel button', async ({ page }) => {
    await page.getByRole('button', { name: '+ Add' }).first().click();

    const titleInput = page.getByPlaceholder('Topic title...').first();
    await expect(titleInput).toBeVisible();
    await titleInput.fill('This should not be saved either');
    await page.getByRole('button', { name: 'Cancel' }).first().click();

    await expect(page.getByText('This should not be saved either')).not.toBeVisible();
  });

  test('edit item inline and save', async ({ page }) => {
    // Add an item first
    await page.getByRole('button', { name: '+ Add' }).nth(1).click();
    const addInput = page.getByPlaceholder('Topic title...').nth(1);
    await addInput.fill('Original Title');
    await addInput.press('Enter');
    await expect(page.getByText('Original Title')).toBeVisible();

    // Click edit button
    await page.getByRole('button', { name: 'Edit' }).first().click();

    // Edit form should show with current title
    const editTitleInput = page.locator('input[x-model="editingItem.title"]');
    await expect(editTitleInput).toBeVisible();
    await expect(editTitleInput).toHaveValue('Original Title');

    // Change title and add a link
    await editTitleInput.fill('Edited Title');
    const linkInput = page.locator('input[x-model="editingItem.links[linkIdx]"]').first();
    await linkInput.fill('https://example.com/review');

    // Save
    await page.getByRole('button', { name: 'Save' }).click();

    // Verify changes
    await expect(page.getByText('Edited Title')).toBeVisible();
    await expect(page.getByText('Original Title')).not.toBeVisible();
    await expect(page.getByRole('link', { name: 'https://example.com/review' })).toBeVisible();

    // Clean up
    await page.getByRole('button', { name: 'Delete' }).first().click();
  });

  test('edit item and cancel via Escape', async ({ page }) => {
    // Add an item
    await page.getByRole('button', { name: '+ Add' }).nth(1).click();
    const addInput = page.getByPlaceholder('Topic title...').nth(1);
    await addInput.fill('Should Stay Unchanged');
    await addInput.press('Enter');
    await expect(page.getByText('Should Stay Unchanged')).toBeVisible();

    // Edit and cancel
    await page.getByRole('button', { name: 'Edit' }).first().click();
    const editTitleInput = page.locator('input[x-model="editingItem.title"]');
    await editTitleInput.fill('Changed But Cancelled');
    await editTitleInput.press('Escape');

    // Original title should remain
    await expect(page.getByText('Should Stay Unchanged')).toBeVisible();
    await expect(page.getByText('Changed But Cancelled')).not.toBeVisible();

    // Clean up
    await page.getByRole('button', { name: 'Delete' }).first().click();
  });

  test('delete item with confirmation', async ({ page }) => {
    // Add an item
    await page.getByRole('button', { name: '+ Add' }).nth(1).click();
    const addInput = page.getByPlaceholder('Topic title...').nth(1);
    await addInput.fill('To Be Deleted');
    await addInput.press('Enter');
    await expect(page.getByText('To Be Deleted')).toBeVisible();
    await expect(page.getByText('Mice (1)')).toBeVisible();

    // Delete (dialog auto-accepted via beforeEach)
    await page.getByRole('button', { name: 'Delete' }).first().click();

    // Item should be gone
    await expect(page.getByText('To Be Deleted')).not.toBeVisible();
    await expect(page.getByText('Mice (0)')).toBeVisible();
  });

  test('items persist across page reload', async ({ page }) => {
    // Add an item to Keyboards section (5th add button)
    await page.getByRole('button', { name: '+ Add' }).nth(4).click();
    const addInput = page.getByPlaceholder('Topic title...').nth(4);
    await addInput.fill('Persistent Keyboard Item');
    await addInput.press('Enter');
    await expect(page.getByText('Persistent Keyboard Item')).toBeVisible();

    // Reload page
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Test Episode 1' })).toBeVisible();

    // Item should still be there
    await expect(page.getByText('Persistent Keyboard Item')).toBeVisible();
    await expect(page.getByText('Keyboards (1)')).toBeVisible();

    // Clean up
    await page.getByRole('button', { name: 'Delete' }).first().click();
    await expect(page.getByText('Keyboards (0)')).toBeVisible();
  });

  test('drag handle is visible on each item', async ({ page }) => {
    // Add an item
    await page.getByRole('button', { name: '+ Add' }).nth(1).click();
    const addInput = page.getByPlaceholder('Topic title...').nth(1);
    await addInput.fill('Drag Handle Test');
    await addInput.press('Enter');

    // Drag handle should exist with correct class and title
    const dragHandle = page.locator('.sort-handle').first();
    await expect(dragHandle).toBeVisible();
    await expect(dragHandle).toHaveAttribute('title', 'Drag to reorder');

    // Clean up
    await page.getByRole('button', { name: 'Delete' }).first().click();
  });

  test('no console errors on page load', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.goto(LIVE_URL);
    await expect(page.getByRole('heading', { name: 'Test Episode 1' })).toBeVisible();

    // Filter out known benign errors (favicon, tailwind CDN warning)
    const realErrors = errors.filter(e =>
      !e.includes('favicon') && !e.includes('tailwindcss')
    );
    expect(realErrors).toHaveLength(0);
  });
});

test.describe('Live Page - Timer & Timestamps', () => {
  test.beforeEach(async ({ page }) => {
    page.on('dialog', dialog => dialog.accept());
    await login(page);
    // Use podcast 1, episode 5 which has existing items
    await page.goto('/podcasts/1/episodes/5/live');
    await expect(page.getByRole('heading', { name: 'MouseCast 064' })).toBeVisible();
  });

  test('MARK buttons are disabled before timer starts', async ({ page }) => {
    const markButtons = page.getByRole('button', { name: 'MARK' });
    const count = await markButtons.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < count; i++) {
      await expect(markButtons.nth(i)).toBeDisabled();
    }
  });

  test('timer display shows 00:00', async ({ page }) => {
    await expect(page.getByText('00:00')).toBeVisible();
  });
});
