// Detect "snap" in the sidebar collapse: sample a nav icon's x position every frame
// through the transition. A snap shows as one large jump; smooth = small even steps.
import { chromium } from "playwright";

const BASE = process.env.WEB_URL ?? "http://localhost:4173";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.addInitScript(() => localStorage.setItem("vb_sidebar_collapsed", "0"));
await page.goto(BASE, { waitUntil: "domcontentloaded" });
await page.waitForSelector("nav ul li button");

const icon = page.locator("nav ul li button").first();
const xAt = async () => (await icon.boundingBox())?.x ?? null;

async function sample(label) {
  const xs = [];
  for (let i = 0; i < 24; i++) {
    xs.push(await xAt());
    await page.waitForTimeout(18);
  }
  const deltas = xs.slice(1).map((x, i) => +(x - xs[i]).toFixed(1));
  const maxStep = Math.max(...deltas.map(Math.abs));
  const total = Math.abs(xs[xs.length - 1] - xs[0]);
  console.log(`\n${label}: start=${xs[0]?.toFixed(0)} end=${xs[xs.length - 1]?.toFixed(0)} total=${total.toFixed(0)}px`);
  console.log("  per-frame Δ:", deltas.join(" "));
  console.log(`  max single-frame jump: ${maxStep}px (smooth if no single step dominates the total)`);
}

await page.locator('nav button[aria-label="Collapse sidebar"]').click();
await sample("COLLAPSE");

await page.locator('nav button[aria-label="Expand sidebar"]').click();
await sample("EXPAND");

await browser.close();
