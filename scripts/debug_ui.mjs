import playwright from "playwright";
const { chromium } = playwright;

const notebookUrl = "https://notebooklm.google.com/notebook/e101e7d7-5305-45b3-a611-21a5475ceb63?hl=en";
const profileDir = "/Users/ninja/Library/Application Support/notebooklm-mcp/chrome_profile";

async function main() {
  console.log("launching...");
  const context = await chromium.launchPersistentContext(profileDir, {
    headless: true,
    viewport: { width: 1280, height: 900 },
  });
  const page = context.pages()[0] || (await context.newPage());
  console.log("goto notebooklm...");
  await page.goto(notebookUrl, { waitUntil: "domcontentloaded", timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(6000);
  
  await page.screenshot({ path: "/Users/ninja/Documents/Kesher/notebooklm-output/debug-ui-current.png", fullPage: true });
  console.log("Screenshot saved.");

  const textContent = await page.locator("body").innerText();
  console.log("BODY TEXT SAMPLE:", textContent.slice(0, 1500).replace(/\n+/g, " | "));

  const elements = await page.locator("button, [role='tab'], a, [aria-label]").evaluateAll(els => 
    els.map(el => ({ tag: el.tagName, text: el.textContent?.trim().slice(0, 50), aria: el.getAttribute("aria-label"), role: el.getAttribute("role") }))
       .filter(el => (el.text || el.aria) && (el.text?.length < 60))
  );
  console.log("INTERACTIVE ELEMENTS:", JSON.stringify(elements.slice(0, 40), null, 2));

  await context.close();
}

main().catch(console.error);
