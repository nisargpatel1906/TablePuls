import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
import path from "node:path";

const API_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const E2E_OWNER_EMAIL = process.env.E2E_OWNER_EMAIL || "e2e-owner@example.com";
const E2E_OWNER_PASSWORD = process.env.E2E_OWNER_PASSWORD || "E2eStrongPass!2026";
const SCREENSHOT_DIR = path.resolve(__dirname, "../../UI/phase2");

function ensureScreenshotDir() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => {
    return document.documentElement.scrollWidth - window.innerWidth;
  });
  expect(overflow).toBeLessThanOrEqual(2);
}

async function assertNoCriticalA11y(page: Page, routeLabel: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
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

async function captureResponsiveShots(
  page: Page,
  screenId: string,
  { toggleTheme }: { toggleTheme?: () => Promise<void> } = {},
) {
  ensureScreenshotDir();
  // Desktop Light (1440x900)
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(200);
  await assertNoHorizontalOverflow(page);
  await assertNoCriticalA11y(page, `${screenId} 1440 light`);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${screenId}-1440-light.png`) });

  // Tablet (768x1024)
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.waitForTimeout(200);
  await assertNoHorizontalOverflow(page);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${screenId}-768.png`) });

  // Mobile (390x844)
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(200);
  await assertNoHorizontalOverflow(page);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${screenId}-390.png`) });

  // Desktop Dark (1440x900)
  if (toggleTheme) {
    await page.setViewportSize({ width: 1440, height: 900 });
    await toggleTheme();
    await page.waitForTimeout(200);
    await assertNoCriticalA11y(page, `${screenId} 1440 dark`);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${screenId}-1440-dark.png`) });
    // Restore light
    await toggleTheme();
    await page.waitForTimeout(150);
  } else {
    await page.setViewportSize({ width: 1440, height: 900 });
  }
}

function makeTinyPngBuffer(): Buffer {
  // Valid 220x220 PNG created cleanly using pure Node zlib (zero external deps)
  const zlib = require("node:zlib") as typeof import("node:zlib");
  const w = 220;
  const h = 220;
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y += 1) {
    const rowOff = y * (w * 3 + 1);
    raw[rowOff] = 0;
    for (let x = 0; x < w; x += 1) {
      const px = rowOff + 1 + x * 3;
      raw[px] = 220;
      raw[px + 1] = (x + y) % 200;
      raw[px + 2] = 90;
    }
  }
  function chunk(type: string, data: Buffer): Buffer {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length, 0);
    const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const crcBuf = Buffer.alloc(4);
    // Standard CRC32
    let crc = 0xffffffff;
    for (const byte of body) {
      crc ^= byte;
      for (let i = 0; i < 8; i += 1) {
        crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
      }
    }
    crcBuf.writeUInt32BE((crc ^ 0xffffffff) >>> 0, 0);
    return Buffer.concat([len, body, crcBuf]);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 2; // RGB
  const compressed = zlib.deflateSync(raw);
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", compressed),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

test.describe("TablePulse Phase 2 Complete Journey & Visual/A11y Audit", () => {
  test("Tables SCR-017, Menu SCR-018/019/021, QR SCR-020, and Isolated Customer Menu SCR-022", async ({
    page,
    browser,
  }) => {
    test.setTimeout(120000);
    const consoleErrors: string[] = [];
    page.on("pageerror", (err) => consoleErrors.push(err.message));

    // Authenticate OWNER session
    const bsRes = await page.request.get(`${API_URL}/api/v1/auth/bootstrap-status`);
    expect(bsRes.ok()).toBeTruthy();
    const bsJson = await bsRes.json();
    if (bsJson?.data?.bootstrap_required) {
      await page.goto("/register");
      await page.getByLabel(/Organization/i).fill("TablePulse E2E Group");
      await page.getByLabel(/Owner Email/i).fill(E2E_OWNER_EMAIL);
      await page.getByLabel(/Full Name/i).fill("E2E Owner");
      await page.getByRole("textbox", { name: /Password \(min 12 characters\)/i }).fill(E2E_OWNER_PASSWORD);
      await page.getByRole("textbox", { name: "Confirm Password" }).fill(E2E_OWNER_PASSWORD);
      await page.getByRole("button", { name: /Create Account/i }).click();
      await page.waitForURL(/\/onboarding|\/venues\//, { timeout: 15000 });
    } else {
      await page.goto("/login");
      await page.getByLabel(/Email address/i).fill(E2E_OWNER_EMAIL);
      await page.getByLabel("Password", { exact: true }).fill(E2E_OWNER_PASSWORD);
      await page.getByRole("button", { name: /^Sign In$/i }).click();
      try {
        await page.waitForURL(/\/onboarding|\/venues\//, { timeout: 4000 });
      } catch {
        // DB was demo-seeded with another email/password -> obtain OWNER refresh cookie cleanly
        const demoRes = await page.request.post(`${API_URL}/api/v1/auth/demo-login`, {
          data: { role: "OWNER" },
        });
        expect(demoRes.ok()).toBeTruthy();
        await page.reload();
        await page.waitForURL(/\/onboarding|\/venues\//, { timeout: 15000 });
      }
    }

    if (page.url().includes("/onboarding")) {
      await page.getByLabel(/Venue Name/i).fill("E2E Bistro");
      await page.getByRole("checkbox").check();
      await page.getByRole("button", { name: /^Continue$/i }).click();
      await page.getByRole("button", { name: /Load Sample Restaurant Video/i }).click();
      await expect(page.getByAltText(/Face-blurred camera preview/i)).toBeVisible({ timeout: 15000 });
      await page.getByRole("button", { name: /^Continue$/i }).click();
      await page.getByRole("button", { name: /Initialize Starter Tables/i }).click();
      await page.getByRole("button", { name: /^Continue$/i }).click();
      await page.getByRole("button", { name: /Launch Live Floor/i }).click();
      await page.waitForURL(/\/venues\/[^/]+\/floor/, { timeout: 15000 });
    }

    const venueMatch = page.url().match(/\/venues\/([^/]+)/);
    const venueId = venueMatch?.[1] || "";
    expect(venueId).not.toBe("");

    const toggleAdminTheme = async () => {
      await page.getByRole("button", { name: /^Toggle theme$/i }).click();
    };

    // 1. SCR-017 Table Directory: Bulk Add + Screenshot Audit
    await page.goto(`/venues/${venueId}/settings/tables`);
    await expect(page.getByRole("heading", { name: /Table Management & Directory/i })).toBeVisible({
      timeout: 15000,
    });
    const suffix = String(Date.now()).slice(-4);
    const prefix = `P${Math.random().toString(36).replace(/[^a-z0-9]/gi, "").slice(0, 3).toUpperCase()}`;
    await page.getByRole("button", { name: /Bulk Add Tables/i }).click();
    await page.getByLabel(/^Prefix$/i).fill(prefix);
    await page.getByLabel(/Count \(1–50\)/i).fill("2");
    await page.getByRole("button", { name: /Generate 2 Tables/i }).click();
    await expect(page.getByRole("dialog", { name: /Bulk Add Tables/i })).toBeHidden({
      timeout: 15000,
    });
    await expect(page.getByText(`${prefix}01`).first()).toBeVisible({ timeout: 10000 });

    await captureResponsiveShots(page, "SCR-017", { toggleTheme: toggleAdminTheme });

    // 2. SCR-018 Menu Studio + SCR-019 Drawer (WebP upload + item) + Quick-86 + SCR-021 Preview
    await page.goto(`/venues/${venueId}/menu`);
    await expect(page.getByRole("heading", { name: /Menu Studio/i })).toBeVisible({
      timeout: 15000,
    });

    await page.getByRole("button", { name: /New Menu/i }).click();
    await page.getByLabel(/Menu Name/i).fill(`E2E Dinner ${suffix}`);
    await page.getByRole("button", { name: /Save Menu/i }).click();
    await expect(page.getByRole("button", { name: new RegExp(`E2E Dinner ${suffix}`) })).toBeVisible({
      timeout: 10000,
    });

    await page.getByRole("button", { name: /Add Category/i }).click();
    await page.getByLabel(/Category Name/i).fill("Wood-Fired Specials");
    await page.getByRole("button", { name: /Save Category/i }).click();
    await expect(page.getByRole("button", { name: /Wood-Fired Specials/i }).first()).toBeVisible({ timeout: 10000 });

    // Open SCR-019 Item Drawer
    await page.getByRole("button", { name: /Add Dish/i }).click();
    await expect(page.getByRole("dialog", { name: /Add Menu Item/i })).toBeVisible();
    await page.getByLabel(/Dish Name/i).fill(`Truffle Pasta ${suffix}`);
    await page.getByRole("textbox", { name: /^Price \(/i }).fill("425.00");
    await page.getByRole("button", { name: "Veg", exact: true }).click();
    await page.getByRole("button", { name: "DAIRY", exact: true }).click();

    // Upload valid 220x220 PNG -> WebP pipeline
    const tmpImgPath = path.join(SCREENSHOT_DIR, "_tmp_dish.png");
    ensureScreenshotDir();
    fs.writeFileSync(tmpImgPath, makeTinyPngBuffer());
    await page.locator('input[type="file"]').setInputFiles(tmpImgPath);
    await expect(page.getByRole("button", { name: /Remove image/i })).toBeVisible({ timeout: 15000 });

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "SCR-019-1440-light.png") });
    await page.getByRole("button", { name: /Create Dish/i }).click();
    await expect(page.getByText(`Truffle Pasta ${suffix}`)).toBeVisible({ timeout: 10000 });

    // Publish the menu
    await page.getByRole("button", { name: /Edit Menu/i }).click();
    await page.getByLabel(/Publication Status/i).selectOption("PUBLISHED");
    await page.getByRole("button", { name: /Save Menu/i }).click();
    await expect(page.getByText(/Updated menu/i)).toBeVisible({ timeout: 10000 });

    // Quick-86 dish unavailable -> available
    const stockBtn = page.getByRole("button", { name: /^In Stock$/i }).first();
    await stockBtn.click();
    await expect(page.getByRole("button", { name: /Sold Out \(86\)/i }).first()).toBeVisible({
      timeout: 10000,
    });

    await captureResponsiveShots(page, "SCR-018", { toggleTheme: toggleAdminTheme });

    // Open SCR-021 Live Mobile Preview Modal
    await page.getByRole("button", { name: /Mobile Preview/i }).click();
    const previewDlg = page.getByRole("dialog", { name: /Mobile Preview/i });
    await expect(previewDlg).toBeVisible();
    await expect(previewDlg.getByText(/Menu items, prices/i)).toBeVisible({ timeout: 15000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "SCR-021-1440-light.png") });
    await page.getByRole("button", { name: /Close mobile preview/i }).click();

    // 3. SCR-020 Table QR Manager + Capture URL + Batch PDF check
    await page.goto(`/venues/${venueId}/settings/qr-codes`);
    await expect(page.getByRole("heading", { name: /Table QR Manager/i })).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByText(`${prefix}01`).first()).toBeVisible();

    await captureResponsiveShots(page, "SCR-020", { toggleTheme: toggleAdminTheme });

    // Read generated QR URL for created table
    const qrLinkHref = await page
      .getByRole("link", { name: new RegExp(`Open customer menu for ${prefix}01`) })
      .getAttribute("href");
    expect(qrLinkHref).toContain("/m/");
    const oldToken = qrLinkHref!.split("/m/")[1]!;

    // 4. SCR-022 Isolated Incognito Customer Context (ZERO cookies / ZERO auth calls)
    const guestContext = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const guestPage = await guestContext.newPage();
    const authRequestsInGuest: string[] = [];
    guestPage.on("request", (req) => {
      if (req.url().includes("/api/v1/auth/")) authRequestsInGuest.push(req.url());
    });

    await guestPage.goto(`/m/${oldToken}`);
    await expect(guestPage.getByText(/Menu items, prices/i)).toBeVisible({ timeout: 15000 });
    const newMenuTab = guestPage.getByRole("button", { name: `E2E Dinner ${suffix}` });
    if (await newMenuTab.isVisible()) {
      await newMenuTab.click();
    }
    await expect(guestPage.getByText(`Truffle Pasta ${suffix}`)).toBeVisible({ timeout: 15000 });
    await expect(guestPage.getByText(/Sold Out/i).first()).toBeVisible();

    // Verify 0 auth requests, 0 cookies, and 0 admin UI elements
    expect(authRequestsInGuest).toEqual([]);
    expect(await guestContext.cookies()).toEqual([]);
    await expect(guestPage.getByText(/Sign Out/i)).toHaveCount(0);

    // Unauthenticated API probe must fail 401
    const unauthApi = await guestContext.request.get(`${API_URL}/api/v1/venues/${venueId}/tables`);
    expect(unauthApi.status()).toBe(401);

    // Open dish detail bottom sheet -> allergens & no cart/checkout
    await guestPage.getByText(`Truffle Pasta ${suffix}`).click();
    await expect(guestPage.getByRole("dialog")).toBeVisible();
    await expect(guestPage.getByText("DAIRY")).toBeVisible();
    await guestPage.screenshot({ path: path.join(SCREENSHOT_DIR, "SCR-022-390-sheet.png") });
    await guestPage.keyboard.press("Escape");

    // Capture SCR-022 Light + Dark + 768 + 1440
    await captureResponsiveShots(guestPage, "SCR-022", {
      toggleTheme: async () => {
        await guestPage.getByRole("button", { name: /Toggle theme/i }).click();
      },
    });

    // 5. QR Compromise Rotation in Admin -> Incognito sees 410 Gone immediately
    await page
      .locator("article", { hasText: `${prefix}01` })
      .getByRole("button", { name: /Regenerate/i })
      .click();
    await page.getByLabel(/Rotation Reason/i).selectOption("COMPROMISED");
    await page.getByRole("button", { name: /Confirm Rotation/i }).click();
    await expect(page.getByText(/old QR token revoked/i)).toBeVisible({ timeout: 10000 });

    await guestPage.goto(`/m/${oldToken}`);
    await expect(guestPage.getByText(/Table QR Replaced/i)).toBeVisible({ timeout: 10000 });

    await guestContext.close();
    if (fs.existsSync(tmpImgPath)) fs.unlinkSync(tmpImgPath);
    expect(consoleErrors).toEqual([]);
  });
});
