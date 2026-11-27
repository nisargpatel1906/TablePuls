import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const API_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
const E2E_OWNER_EMAIL = process.env.E2E_OWNER_EMAIL || "e2e-owner@example.com";
const E2E_OWNER_PASSWORD = process.env.E2E_OWNER_PASSWORD || "E2eStrongPass!2026";

async function assertNoHorizontalOverflow(page: import("@playwright/test").Page) {
  const overflow = await page.evaluate(() => {
    return document.documentElement.scrollWidth - window.innerWidth;
  });
  expect(overflow).toBeLessThanOrEqual(2);
}

async function assertNoCriticalA11y(page: import("@playwright/test").Page, routeLabel: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  const severe = results.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious",
  );
  expect(
    severe,
    `Expected 0 critical/serious WCAG violations on ${routeLabel}, got: ${JSON.stringify(
      severe.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })),
    )}`,
  ).toEqual([]);
}

test.describe("TablePulse End-to-End & WCAG 2.1 AA Suite", () => {
  test("full operational journey, all 16 direct URLs, responsive layout & axe audits", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("pageerror", (err) => consoleErrors.push(err.message));

    // 1. Check bootstrap status & establish OWNER session via UI (SCR-002 or SCR-001)
    const bsRes = await page.request.get(`${API_URL}/api/v1/auth/bootstrap-status`);
    expect(bsRes.ok()).toBeTruthy();
    const bsJson = await bsRes.json();
    const bootstrapRequired: boolean = Boolean(bsJson?.data?.bootstrap_required);

    if (bootstrapRequired) {
      await page.goto("/register");
      await assertNoHorizontalOverflow(page);
      await assertNoCriticalA11y(page, "/register");
      await page.getByLabel(/Organization/i).fill("TablePulse E2E Group");
      await page.getByLabel(/Owner Email/i).fill(E2E_OWNER_EMAIL);
      await page.getByLabel(/Full Name/i).fill("E2E Owner");
      await page.getByLabel(/Password \(min 12 characters\)/i).fill(E2E_OWNER_PASSWORD);
      await page.getByLabel(/Confirm Password/i).fill(E2E_OWNER_PASSWORD);
      await page.getByRole("button", { name: /Create Account/i }).click();
      await page.waitForURL(/\/onboarding|\/venues\//, { timeout: 15000 });
    } else {
      await page.goto("/login");
      await assertNoHorizontalOverflow(page);
      await assertNoCriticalA11y(page, "/login");
      await page.getByLabel(/Email address/i).fill(E2E_OWNER_EMAIL);
      await page.getByLabel("Password", { exact: true }).fill(E2E_OWNER_PASSWORD);
      await page.getByRole("button", { name: /^Sign In$/i }).click();
      await page.waitForURL(/\/onboarding|\/venues\//, { timeout: 15000 });
    }

    // 2. Onboarding SCR-004 if no venue exists yet
    if (page.url().includes("/onboarding")) {
      await assertNoHorizontalOverflow(page);
      await page.getByLabel(/Venue Name/i).fill("E2E Bistro");
      await page.getByRole("checkbox").check();
      await page.getByRole("button", { name: /^Continue$/i }).click();
      await page.getByRole("button", { name: /Load Sample Restaurant Video/i }).click();
      await expect(page.getByAltText(/Face-blurred camera preview/i)).toBeVisible({
        timeout: 15000,
      });
      await page.getByRole("button", { name: /^Continue$/i }).click();
      await page.getByRole("button", { name: /Initialize Starter Tables/i }).click();
      await expect(page.getByText(/Mapped Polygons: 3 tables/i)).toBeVisible({ timeout: 10000 });
      await page.getByRole("button", { name: /^Continue$/i }).click();
      await page.getByRole("button", { name: /Launch Live Floor/i }).click();
      await page.waitForURL(/\/venues\/[^/]+\/floor/, { timeout: 15000 });
    }

    const match = page.url().match(/\/venues\/([^/]+)/);
    const venueId = match?.[1] || "";
    expect(venueId).not.toBe("");

    // 3. SCR-005 Live Floor Map + List Toggle + SCR-007 Drawer Override & Flag
    await expect(page.getByRole("heading", { name: "Live Floor Map" })).toBeVisible();
    await assertNoHorizontalOverflow(page);
    await assertNoCriticalA11y(page, "/venues/:v/floor");

    await page.getByRole("button", { name: "List" }).click();
    await expect(page.getByRole("button", { name: "Inspect" }).first()).toBeVisible();
    await page.getByRole("button", { name: "Inspect" }).first().click();
    await expect(page.getByRole("region", { name: "Table Detail Inspector" })).toBeVisible();
    await page.getByRole("button", { name: "Mark Clean (Free)" }).click();
    await expect(page.getByText(/updated to FREE/i)).toBeVisible();

    await page.getByRole("button", { name: "Flag Wrong AI Detection" }).click();
    await page.getByLabel("Issue Description").fill("E2E test chair false positive");
    await page.getByRole("button", { name: /Submit to ML Review Queue/i }).click();
    await expect(page.getByText(/Flagged detection/i)).toBeVisible();

    // Verify SCR-007 direct URL
    const fullHref = await page
      .getByRole("link", { name: "Open full table detail page" })
      .getAttribute("href");
    expect(fullHref).toContain("/tables/");
    await page.goto(fullHref!);
    await expect(page.getByRole("region", { name: "Table Detail Inspector" })).toBeVisible();
    await assertNoHorizontalOverflow(page);

    // 4. SCR-006 Live Camera Wall
    await page.goto(`/venues/${venueId}/cameras/live`);
    await expect(page.getByRole("heading", { name: "Live Camera Wall" })).toBeVisible();
    await expect(page.getByText(/Main Floor|Floor Camera|Stream Type|DEMO_MP4/i).first()).toBeVisible({
      timeout: 10000,
    });
    await assertNoHorizontalOverflow(page);

    // 5. SCR-008 Alerts Queue
    await page.goto(`/venues/${venueId}/alerts`);
    await expect(page.getByRole("heading", { name: /Service & Cleaning Alerts/i })).toBeVisible();
    await expect(page.getByRole("button", { name: "Refresh" })).toBeVisible({ timeout: 10000 });
    await assertNoHorizontalOverflow(page);

    // 6. SCR-009 Waitlist & Turnover
    await page.goto(`/venues/${venueId}/waitlist`);
    await expect(page.getByRole("heading", { name: /Waitlist & Turnover ETAs/i })).toBeVisible();
    await page.getByRole("button", { name: /Add Party/i }).click({ timeout: 10000 });
    await page.getByLabel(/Party Name/i).fill("E2E Party");
    await page.getByRole("button", { name: /Save Party/i }).click();
    await expect(page.getByText("E2E Party").first()).toBeVisible();
    await page.getByRole("button", { name: /Seat Party Here/i }).first().click();
    await expect(page.getByText(/Seated E2E Party/i)).toBeVisible();
    await assertNoHorizontalOverflow(page);

    // 7. SCR-010 Peak Hours Analytics & CSV Export
    await page.goto(`/venues/${venueId}/analytics`);
    await expect(page.getByRole("heading", { name: /Peak Hours & Staffing Analytics/i })).toBeVisible();
    await page.getByRole("button", { name: /View as Data Table/i }).click({ timeout: 10000 });
    await expect(page.getByRole("table")).toBeVisible();
    await assertNoHorizontalOverflow(page);

    // 8. SCR-011 ML Review Queue
    await page.goto(`/venues/${venueId}/ml-review`);
    await expect(page.getByRole("heading", { name: /ML Confidence & Human-Review Queue/i })).toBeVisible();
    await page.getByRole("button", { name: /Save & Next/i }).click({ timeout: 10000 });
    await expect(page.getByText(/Saved label/i)).toBeVisible();
    await assertNoHorizontalOverflow(page);

    // 9. SCR-012 Camera Settings & SCR-013 Polygon Calibration
    await page.goto(`/venues/${venueId}/settings/cameras`);
    await expect(page.getByRole("heading", { name: /Camera & RTSP Stream Management/i })).toBeVisible();
    const calibrateHref = await page
      .getByRole("link", { name: /Calibrate Polygons/i })
      .first()
      .getAttribute("href", { timeout: 10000 });
    expect(calibrateHref).toBeTruthy();
    await page.goto(calibrateHref!);
    await expect(page.getByRole("heading", { name: /Interactive Table Polygon/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Save Calibration/i })).toBeVisible({
      timeout: 10000,
    });
    await assertNoHorizontalOverflow(page);

    // 10. SCR-014 Alert Rules
    await page.goto(`/venues/${venueId}/settings/alerts`);
    await expect(page.getByRole("heading", { name: /Alert Rules & Threshold Settings/i })).toBeVisible();
    await page.getByRole("button", { name: /Save Changes/i }).click({ timeout: 10000 });
    await expect(page.getByText(/Saved alert thresholds/i)).toBeVisible();
    await assertNoHorizontalOverflow(page);

    // 11. SCR-015 Users & Audit Log
    await page.goto("/org/users");
    await expect(page.getByRole("heading", { name: /Users, Roles & Audit Log/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Team Members/i })).toBeVisible({ timeout: 10000 });
    await assertNoHorizontalOverflow(page);

    // 12. SCR-016 System Health & Kill Switch Toggle
    await page.goto("/org/system");
    await expect(page.getByRole("heading", { name: /System Health, Model Registry & Privacy/i })).toBeVisible();
    await assertNoCriticalA11y(page, "/org/system");
    await page.getByRole("button", { name: /Pause All AI Inference/i }).click();
    await expect(page.getByText(/AI Paused/i).first()).toBeVisible();
    await page.getByRole("button", { name: /Resume AI Inference/i }).click();
    await assertNoHorizontalOverflow(page);

    // 13. Direct URL checks for remaining auth / reset routes (zero 404s)
    for (const staticPath of ["/login", "/register", "/reset-password", "/onboarding"]) {
      const resp = await page.goto(staticPath);
      expect(resp?.status()).toBeLessThan(400);
      await assertNoHorizontalOverflow(page);
    }

    expect(consoleErrors).toEqual([]);
  });
});
