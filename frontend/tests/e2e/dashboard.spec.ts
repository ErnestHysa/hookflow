import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to dashboard
    await page.goto("http://localhost:3000/dashboard");
  });

  test("shows overview page", async ({ page }) => {
    // Should show dashboard heading
    await expect(page.locator("h1")).toContainText("Dashboard");

    // Should show stat cards
    await expect(page.locator("text=Total Webhooks")).toBeVisible();
    await expect(page.locator("text=Success Rate")).toBeVisible();
  });

  test("displays charts", async ({ page }) => {
    // Charts should be visible
    await expect(page.locator("text=Webhooks Over Time")).toBeVisible();
    await expect(page.locator("text=Delivery Status")).toBeVisible();
  });
});

test.describe("Webhooks", () => {
  test("displays webhook list page", async ({ page }) => {
    await page.goto("http://localhost:3000/dashboard/app/test-app/webhooks");

    // Should show webhooks heading
    await expect(page.locator("h1")).toContainText("Webhooks");

    // Should show pagination
    await expect(page.locator("text=Previous")).toBeVisible();
    await expect(page.locator("text=Next")).toBeVisible();
  });

  test("navigates to webhook detail", async ({ page }) => {
    await page.goto("http://localhost:3000/dashboard/app/test-app/webhooks");

    // Click first webhook row if visible
    const firstRow = page.locator("table tbody tr").first();
    if (await firstRow.isVisible()) {
      await firstRow.click();
      await expect(page).toHaveURL(/\/webhooks\/\w+/);
      
      // Should show webhook detail
      await expect(page.locator("text=Request Headers")).toBeVisible();
      await expect(page.locator("text=Request Body")).toBeVisible();
      await expect(page.locator("text=Delivery Attempts")).toBeVisible();
    }
  });

  test("shows back button on detail page", async ({ page }) => {
    await page.goto("http://localhost:3000/dashboard/app/test-app/webhooks/test-webhook");

    // Back button should be visible
    await expect(page.locator("text=Back to Webhooks")).toBeVisible();
  });
});

test.describe("Destinations", () => {
  test("displays destinations page", async ({ page }) => {
    await page.goto("http://localhost:3000/dashboard/app/test-app/destinations");

    // Should show destinations heading
    await expect(page.locator("h1")).toContainText("Destinations");

    // Should show add button
    await expect(page.locator("button:has-text('Add Destination')")).toBeVisible();
  });

  test("opens destination form", async ({ page }) => {
    await page.goto("http://localhost:3000/dashboard/app/test-app/destinations");

    // Click add destination button
    await page.click("button:has-text('Add Destination')");

    // Modal should appear
    await expect(page.locator("text=Add Destination")).toBeVisible();
    await expect(page.locator("text=Name")).toBeVisible();
    await expect(page.locator("text=Type")).toBeVisible();
  });
});

test.describe("Settings", () => {
  test("displays settings page", async ({ page }) => {
    await page.goto("http://localhost:3000/dashboard/app/test-app/settings");

    // Should show settings heading
    await expect(page.locator("h1")).toContainText("Settings");

    // Should show API Keys section
    await expect(page.locator("text=API Keys")).toBeVisible();
    await expect(page.locator("button:has-text('Create Key')")).toBeVisible();
  });

  test("shows app information", async ({ page }) => {
    await page.goto("http://localhost:3000/dashboard/app/test-app/settings");

    // Should show app info section
    await expect(page.locator("text=App Information")).toBeVisible();
    await expect(page.locator("text=App ID")).toBeVisible();
  });
});
