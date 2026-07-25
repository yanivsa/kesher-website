import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const MAX_IMAGE_BYTES = 15 * 1024 * 1024;

async function downloadImage(url, filepath) {
  const response = await fetch(url, { redirect: "follow" });
  if (!response.ok) {
    throw new Error(`Failed to download image (${response.status})`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.startsWith("image/")) {
    throw new Error(`Unexpected image content type: ${contentType || "missing"}`);
  }

  const contentLength = Number(response.headers.get("content-length") || 0);
  if (contentLength > MAX_IMAGE_BYTES) {
    throw new Error("Generated image exceeds the 15 MB limit");
  }

  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.byteLength > MAX_IMAGE_BYTES) {
    throw new Error("Generated image exceeds the 15 MB limit");
  }
  fs.writeFileSync(filepath, bytes);
}

function buildPrompt(title, customPrompt = "") {
  return [
    `Realistic professional editorial photography for a Hebrew counseling article titled: ${title}.`,
    customPrompt ? `${customPrompt}.` : "",
    "Warm natural light, modest everyday Israeli home or counseling room.",
    "Emotionally respectful scene of a couple, parent and child, or family conversation.",
    "Show the natural diversity of Israeli couples and families without stereotypes.",
    "No text, no logos, no watermark, no clinical stock-photo feeling.",
    "High-quality 8k resolution, photorealistic, cinematic lighting, sharp focus, detailed textures.",
  ].filter(Boolean).join(" ");
}

async function main() {
  const [slug, title = slug, customPrompt = ""] = process.argv.slice(2);
  if (!slug) {
    console.error("ERROR: Usage: node scripts/generate-article-image.js <slug> [title] [customPrompt]");
    process.exit(1);
  }
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
    console.error("ERROR: slug must contain only lowercase letters, digits, and single hyphens.");
    process.exit(1);
  }

  const apiKey = process.env.DEEPAI_API_KEY;
  delete process.env.DEEPAI_API_KEY;
  if (!apiKey) {
    console.warn("WARNING: DEEPAI_API_KEY is missing. Skipping DeepAI image generation.");
    process.exit(0);
  }

  try {
    const response = await fetch("https://api.deepai.org/api/text2img", {
      method: "POST",
      headers: {
        "Api-Key": apiKey,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({ text: buildPrompt(title, customPrompt) }),
    });

    if (!response.ok) {
      console.warn(`WARNING: DeepAI returned ${response.status}. Falling back to non-DeepAI image.`);
      process.exit(0);
    }

    const data = await response.json();
    if (!data.output_url) {
      console.warn("WARNING: DeepAI response did not include output_url. Falling back to non-DeepAI image.");
      process.exit(0);
    }

    const outputDir = path.join(__dirname, "..", "public", "images", "generated", "blog");
    fs.mkdirSync(outputDir, { recursive: true });

    const outputPath = path.join(outputDir, `${slug}.jpg`);
    await downloadImage(data.output_url, outputPath);
    console.log(`/images/generated/blog/${slug}.jpg`);
  } catch (error) {
    console.warn(`WARNING: DeepAI image generation failed: ${error.message}`);
    process.exit(0);
  }
}

main();
