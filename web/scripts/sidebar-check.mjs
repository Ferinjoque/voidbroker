// Verify the sidebar is pinned (footer visible on a long, scrolled page) and that the
// logo's left edge aligns with the nav icons below it.
import { chromium } from "playwright";

const BASE = process.env.WEB_URL ?? "http://localhost:4173";
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 820 } });
await p.addInitScript(() => localStorage.setItem("vb_sidebar_collapsed", "0"));
await p.goto(BASE, { waitUntil: "domcontentloaded" });
await p.waitForSelector("nav ul li button");

// Go to the longest view.
await p.locator("nav button", { hasText: "Forecast" }).first().click();
await p.waitForTimeout(900);

// Alignment: logo diamond vs first nav icon (both should share a left edge).
const logoX = (await p.locator("nav .display, nav span.block.rotate-45").first().boundingBox())?.x;
const diamondX = (await p.locator("nav span.rotate-45").first().boundingBox())?.x;
const iconX = (await p.locator("nav ul li button svg").first().boundingBox())?.x;
console.log(`diamond.x=${diamondX?.toFixed(1)}  navIcon.x=${iconX?.toFixed(1)}  Δ=${(diamondX - iconX).toFixed(1)}px`);

// Scroll the page to the bottom; the footer must stay in the viewport (pinned sidebar).
await p.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
await p.waitForTimeout(400);
const settings = await p.locator('nav button[aria-label="Settings"]').boundingBox();
const vh = 820;
const settingsVisible = settings && settings.y >= 0 && settings.y + settings.height <= vh;
console.log(`after scroll: Settings button y=${settings?.y?.toFixed(0)} (viewport ${vh}) -> visible=${settingsVisible}`);
await p.screenshot({ path: "scripts/shots/sidebar-pinned.png" });

await b.close();
