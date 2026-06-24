// One-off: render the WFM Notion doc in a real browser and dump its text + links.
import { chromium } from "playwright";
import { writeFileSync } from "node:fs";

const URL =
  "https://42bytes.notion.site/WFM-Api-v2-Documentation-5d987e4aa2f74b55a80db1a09932459d";

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForSelector(".notion-page-content", { timeout: 45000 });
// Notion lazy-loads; scroll to force content in, then settle.
for (let i = 0; i < 12; i++) {
  await page.mouse.wheel(0, 4000);
  await page.waitForTimeout(500);
}
await page.waitForTimeout(2000);

const text = await page.evaluate(() => {
  const main = document.querySelector(".notion-page-content") || document.body;
  return main.innerText;
});
const links = await page.evaluate(() =>
  [...document.querySelectorAll("a")]
    .map((a) => ({ text: a.innerText.trim(), href: a.href }))
    .filter((l) => l.text && l.href.includes("notion.site")),
);

writeFileSync("scripts/notion-main.txt", text);
writeFileSync("scripts/notion-links.json", JSON.stringify(links, null, 2));
console.log("main text length:", text.length);
console.log("sub-page links:", links.length);
console.log("first 1200 chars:\n", text.slice(0, 1200));
await browser.close();
