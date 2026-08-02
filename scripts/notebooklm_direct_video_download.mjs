import fs from "node:fs";
import path from "node:path";
import playwright from "playwright";

const { chromium } = playwright;

const notebookUrl =
  "https://notebooklm.google.com/notebook/e101e7d7-5305-45b3-a611-21a5475ceb63?hl=en";
const outputPath =
  process.argv[2] ||
  `/Users/ninja/Documents/Kesher/notebooklm-output/direct-download-${Date.now()}.mp4`;
const inspectOnly = process.argv.includes("--inspect-only");
const countOnly = process.argv.includes("--count-only");
const minimumCountArg = process.argv.find((arg) => arg.startsWith("--min-artifact-count="));
const minimumArtifactCount = minimumCountArg
  ? Number(minimumCountArg.split("=", 2)[1])
  : null;
const waitSecondsArg = process.argv.find((arg) => arg.startsWith("--wait-seconds="));
const waitSeconds = waitSecondsArg ? Number(waitSecondsArg.split("=", 2)[1]) : 3600;
const profileDir =
  "/Users/ninja/Library/Application Support/notebooklm-mcp/chrome_profile";

async function clickFirstVisible(page, selectors, timeout = 1500) {
  for (const selector of selectors) {
    const item = page.locator(selector).first();
    try {
      if (await item.isVisible({ timeout })) {
        await item.click();
        return selector;
      }
    } catch {
      // Try next selector.
    }
  }
  return null;
}

async function artifactSummary(page) {
  return await page.locator('button:has-text("more_vert"), mat-icon:has-text("more_vert"), .artifact-more-button, [aria-label*="More options"]').evaluateAll((buttons) =>
    buttons.map((button, index) => {
      let card = button;
      while (card && card.parentElement && card.parentElement.textContent?.trim().length < 4) {
        card = card.parentElement;
      }
      const container =
        button.closest(".artifact-container, .artifact-card, [class*='artifact-item']") ||
        card?.parentElement ||
        card;
      return {
        index,
        text: (container?.textContent || "").replace(/\s+/g, " ").trim().slice(0, 300),
      };
    }),
  );
}

async function main() {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  console.log("launching-browser");
  const context = await chromium.launchPersistentContext(profileDir, {
    headless: true,
    acceptDownloads: true,
    viewport: { width: 1280, height: 900 },
  });
  console.log("browser-launched");
  const page = context.pages()[0] || (await context.newPage());
  try {
    console.log("goto-start");
    await Promise.race([
      page.goto(notebookUrl, { waitUntil: "domcontentloaded", timeout: 60000 }),
      new Promise((_, reject) => setTimeout(() => reject(new Error("manual goto timeout")), 70000)),
    ]);
    console.log("goto-done");
    await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
    console.log("networkidle-or-timeout");
    await page.waitForTimeout(5000);

    const studioSelector = await clickFirstVisible(page, [
      '[role="tab"]:has-text("Studio")',
      'button:has-text("Studio")',
      'a:has-text("Studio")',
      '[aria-label*="Studio"]',
    ]);
    console.log(`studio-selector=${studioSelector}`);
    await page.waitForTimeout(2500);

    const closeDialog = page.locator('button[aria-label="Close dialog"]').first();
    if (await closeDialog.isVisible({ timeout: 1000 }).catch(() => false)) {
      await closeDialog.click();
      await page.waitForTimeout(1000);
      console.log("closed-dialog=true");
    }
    await page.waitForTimeout(1500);

    if (minimumArtifactCount !== null) {
      const deadline = Date.now() + waitSeconds * 1000;
      while (Date.now() < deadline) {
        const artifacts = await artifactSummary(page);
        console.log(JSON.stringify({ waitingForArtifactCount: minimumArtifactCount, artifacts }));
        if (artifacts.length >= minimumArtifactCount) {
          break;
        }
        await page.waitForTimeout(15000);
        await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 }).catch(() => {});
        await page.waitForTimeout(5000);
      }
      const artifacts = await artifactSummary(page);
      if (artifacts.length < minimumArtifactCount) {
        throw new Error(
          `Timed out waiting for artifact count ${minimumArtifactCount}; found ${artifacts.length}`,
        );
      }
    }

    if (countOnly) {
      const artifacts = await artifactSummary(page);
      console.log(JSON.stringify({ success: true, artifactCount: artifacts.length, artifacts }));
      return;
    }

    if (inspectOnly) {
      const screenshotPath = "/Users/ninja/Documents/Kesher/notebooklm-output/direct-download-inspect.png";
      await page.screenshot({ path: screenshotPath, fullPage: true });
      const items = await page.evaluate(() => {
        return [...document.querySelectorAll("button, [role=button], [role=menuitem], a")]
          .map((el) => ({
            tag: el.tagName,
            role: el.getAttribute("role"),
            aria: el.getAttribute("aria-label"),
            cls: el.getAttribute("class"),
            text: (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 160),
          }))
          .filter((item) => item.aria || item.text || item.cls)
          .slice(0, 220);
      });
      const artifacts = await artifactSummary(page);
      console.log(JSON.stringify({ screenshotPath, url: page.url(), artifacts, items }, null, 2));
      return;
    }

    const moreSelector = await clickFirstVisible(
      page,
      [
        ".artifact-more-button",
        "button.artifact-more-button",
        'button:has-text("more_vert").artifact-more-button',
        'button[aria-label*="More options"]',
        'button[aria-label*="More"]',
        'button:has(mat-icon:has-text("more_vert"))',
      ],
      7000,
    );
    if (!moreSelector) {
      await page.screenshot({
        path: "/Users/ninja/Documents/Kesher/notebooklm-output/direct-download-no-menu.png",
        fullPage: true,
      });
      throw new Error("Could not find artifact more menu.");
    }
    console.log(`more-selector=${moreSelector}`);

    const downloadItem = page
      .locator(
        '[role="menuitem"]:has-text("Download"), button:has-text("Download"), [role="menuitem"]:has-text("Télécharger"), button:has-text("Télécharger")',
      )
      .first();
    await downloadItem.waitFor({ state: "visible", timeout: 15000 });
    const downloadPromise = page.waitForEvent("download", { timeout: 120000 });
    await downloadItem.click();
    const download = await downloadPromise;
    await download.saveAs(outputPath);
    console.log(JSON.stringify({
      success: true,
      outputPath,
      suggestedFilename: download.suggestedFilename(),
      bytes: fs.statSync(outputPath).size,
    }));
  } finally {
    await context.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
