// E2E tests for sign language practice feature
const { test, expect } = require('@playwright/test');

test.describe('Sign Language Practice', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should load word list', async ({ page }) => {
    const wordList = page.locator('[data-testid="word-list"]');
    await expect(wordList).toBeVisible({ timeout: 10000 });
  });

  test('should navigate to practice page', async ({ page }) => {
    const firstWord = page.locator('[data-testid="word-item"]').first();
    await firstWord.click();
    
    await expect(page).toHaveURL(/\/practice/);
    await expect(page.locator('h1')).toContainText('Practice');
  });

  test('should show camera interface', async ({ page }) => {
    const firstWord = page.locator('[data-testid="word-item"]').first();
    await firstWord.click();
    
    const cameraView = page.locator('video, canvas');
    await expect(cameraView).toBeVisible({ timeout: 5000 });
  });

  test('should display practice button', async ({ page }) => {
    const firstWord = page.locator('[data-testid="word-item"]').first();
    await firstWord.click();
    
    const practiceButton = page.locator('button:has-text("Start Practice")');
    await expect(practiceButton).toBeVisible();
  });
});

