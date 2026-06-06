import fs from "fs";
import https from "https";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function downloadImage(url, filepath) {
  return new Promise((resolve, reject) => {
    const request = https.get(url, (response) => {
      if (response.statusCode !== 200) {
        reject(new Error(`Failed to download image (${response.statusCode})`));
        response.resume();
        return;
      }

      const file = fs.createWriteStream(filepath);
      response.pipe(file);
      file.on("finish", () => file.close(resolve));
      file.on("error", (error) => {
        fs.unlink(filepath, () => reject(error));
      });
    });

    request.on("error", reject);
  });
}

function buildPrompt(title) {
  return [
    `Realistic professional editorial photography for a Hebrew counseling article titled: ${title}.`,
    "Warm natural light, modest everyday Israeli home or counseling room.",
    "Emotionally respectful scene of a couple, parent and child, or family conversation.",
    "No text, no logos, no watermark, no clinical stock-photo feeling.",
    "High-quality 8k resolution, photorealistic, cinematic lighting, sharp focus, detailed textures.",
  ].join(" ");
}

async function main() {
  const apiKey = process.env.DEEPAI_API_KEY;
  if (!apiKey) {
    console.warn("WARNING: DEEPAI_API_KEY is missing. Skipping DeepAI image generation.");
    process.exit(0);
  }

  const [slug, title = slug] = process.argv.slice(2);
  if (!slug) {
    console.error("ERROR: Usage: node scripts/generate-article-image.js <slug> [title]");
    process.exit(1);
  }

  try {
    const response = await fetch("https://api.deepai.org/api/text2img", {
      method: "POST",
      headers: {
        "Api-Key": apiKey,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({ text: buildPrompt(title) }),
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
