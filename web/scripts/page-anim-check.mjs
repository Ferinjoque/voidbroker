// Confirm the page-enter animation actually fires when switching views.
import { chromium } from "playwright";
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto("http://localhost:4173", { waitUntil: "domcontentloaded" });
await p.waitForSelector("nav ul li button");
await p.locator("nav button", { hasText: "Forecast" }).first().click();
const info = await p.evaluate(() => {
  const el = document.querySelector("main > div");
  const cs = getComputedStyle(el);
  return { cls: el.className, name: cs.animationName, dur: cs.animationDuration };
});
console.log("wrapper class:", info.cls);
console.log("animationName:", info.name, " duration:", info.dur);
await b.close();
