// Visual + console-error check of the running frontend against the live API.
// Requires: API on :8000 and `npm run preview` on :4173.
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = process.env.WEB_URL ?? "http://localhost:4173";
const VIEWS = ["Today", "Dashboard", "Watchlist", "Forecast", "Opportunities", "Riven Deals", "Disposition", "Validation", "Arbitrage", "Ducats", "Journal", "Baro", "Resurgence", "Markets"];

mkdirSync("scripts/shots", { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const problems = [];
page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
page.on("console", (m) => {
  if (m.type() === "error") problems.push(`console.error: ${m.text()}`);
});

await page.goto(BASE, { waitUntil: "networkidle", timeout: 30000 });
await page.waitForSelector("nav", { timeout: 10000 });

for (const view of VIEWS) {
  await page.locator("nav button", { hasText: view }).first().click();
  await page.waitForTimeout(view === "Markets" ? 1800 : 700);
  const file = `scripts/shots/${view.toLowerCase().replace(/ /g, "-")}.png`;
  await page.screenshot({ path: file, fullPage: process.env.FULLPAGE === "1" });
  const heading = await page.locator("main h2").first().textContent().catch(() => "(none)");
  console.log(`✓ ${view.padEnd(14)} → ${file}   heading: ${heading?.trim()}`);
}

// Forecast: expand a row's reasoning and capture the nerf filter.
await page.locator("nav button", { hasText: "Forecast" }).first().click();
await page.waitForTimeout(900);
const fRow = page.locator("main .surface > div button").first();
const fRows = await page.locator("main .surface > div").count();
await fRow.click();
await page.waitForTimeout(450);
await page.screenshot({ path: "scripts/shots/forecast-expanded.png" });
await page.locator("main button", { hasText: "Nerf risk" }).first().click();
await page.waitForTimeout(450);
await page.screenshot({ path: "scripts/shots/forecast-nerf.png" });
console.log(`\n✓ forecast rows rendered: ${fRows}`);

// Interaction captures: detail drawer + search typeahead.
await page.locator("nav button", { hasText: "Dashboard" }).first().click();
await page.waitForTimeout(600);
await page.locator("main table tbody tr").first().click();
await page.waitForTimeout(1200);
await page.screenshot({ path: "scripts/shots/drawer.png" });
const drawerOpen = await page.locator("aside").count();
console.log(`\n✓ detail drawer opened: ${drawerOpen > 0}`);
await page.keyboard.press("Escape");
await page.waitForTimeout(450); // exit animation (240ms) + unmount
console.log(`✓ drawer closed after Escape: ${(await page.locator("aside").count()) === 0}`);

await page.locator("nav button", { hasText: "Markets" }).first().click();
await page.waitForTimeout(800);
const box = page.locator('input[placeholder^="Search"]');
await box.click();
await box.fill("prime");
await page.waitForTimeout(700);
await page.screenshot({ path: "scripts/shots/markets-search.png" });
const suggestions = await page.locator("form ul li").count();
console.log(`✓ search suggestions for "prime": ${suggestions}`);

// Sidebar: settings popover, then collapsed rail.
await page.locator("nav button", { hasText: "Dashboard" }).first().click();
await page.waitForTimeout(300);
await page.locator('nav button[aria-label="Settings"]').click();
await page.waitForTimeout(300);
await page.screenshot({ path: "scripts/shots/sidebar-settings.png" });
await page.locator("div.fixed.inset-0.z-40").click({ position: { x: 10, y: 10 } }).catch(() => {});
await page.waitForTimeout(250);
await page.locator('nav button[aria-label="Collapse sidebar"]').click();
await page.waitForTimeout(500);
await page.screenshot({ path: "scripts/shots/sidebar-collapsed.png" });
const railWidth = await page.locator("nav").first().evaluate((el) => el.clientWidth);
console.log(`✓ collapsed sidebar width: ${railWidth}px`);
await page.locator('nav button[aria-label="Expand sidebar"]').click();
await page.waitForTimeout(400);

console.log("\nconsole / page errors:", problems.length);
for (const p of problems.slice(0, 20)) console.log("  -", p);

await browser.close();
