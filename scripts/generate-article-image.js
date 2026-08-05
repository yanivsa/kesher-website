import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const MAX_IMAGE_BYTES = 15 * 1024 * 1024;

const FALLBACK_PHOTO_POOLS = {
  relocation: [
    "https://images.unsplash.com/photo-1513694203232-719a280e022f?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1507652313519-d4e9174996dd?auto=format&fit=crop&w=1200&q=80"
  ],
  dating: [
    "https://images.unsplash.com/photo-1516589178581-6cd7833ae3b2?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1522529599102-193c0d76b5b6?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1494774157365-9e04c6720e47?auto=format&fit=crop&w=1200&q=80"
  ],
  singleness: [
    "https://images.unsplash.com/photo-1508214751196-bcfd4ca60f91?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1499209974431-9dddcece7f88?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=1200&q=80"
  ],
  boundaries: [
    "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1543269865-cbf427effbad?auto=format&fit=crop&w=1200&q=80"
  ],
  parenting: [
    "https://images.unsplash.com/photo-1485546246426-74dc88dec4d9?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1511895426328-dc8714191300?auto=format&fit=crop&w=1200&q=80"
  ],
  default: [
    "https://images.unsplash.com/photo-1516589178581-6cd7833ae3b2?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1522529599102-193c0d76b5b6?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1511895426328-dc8714191300?auto=format&fit=crop&w=1200&q=80"
  ]
};

function selectFallbackImageUrl(slug, title) {
  const combined = (slug + " " + title).toLowerCase();
  let category = "default";
  if (combined.includes("relocation") || combined.includes("רילוקיישן")) category = "relocation";
  else if (combined.includes("dating") || combined.includes("דייט") || combined.includes("סמס")) category = "dating";
  else if (combined.includes("singleness") || combined.includes("רווקות") || combined.includes("חברים")) category = "singleness";
  else if (combined.includes("boundaries") || combined.includes("מרחב") || combined.includes("מחנק")) category = "boundaries";
  else if (combined.includes("parent") || combined.includes("הורים") || combined.includes("ילדים")) category = "parenting";

  const pool = FALLBACK_PHOTO_POOLS[category] || FALLBACK_PHOTO_POOLS.default;
  let hash = 0;
  for (let i = 0; i < slug.length; i++) {
    hash = (hash << 5) - hash + slug.charCodeAt(i);
    hash |= 0;
  }
  const index = Math.abs(hash) % pool.length;
  return pool[index];
}

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

  const outputDir = path.join(__dirname, "..", "public", "images", "generated", "blog");
  fs.mkdirSync(outputDir, { recursive: true });
  const outputPath = path.join(outputDir, `${slug}.jpg`);

  const apiKey = process.env.DEEPAI_API_KEY;
  delete process.env.DEEPAI_API_KEY;

  if (apiKey) {
    try {
      const response = await fetch("https://api.deepai.org/api/text2img", {
        method: "POST",
        headers: {
          "Api-Key": apiKey,
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({ text: buildPrompt(title, customPrompt) }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.output_url) {
          await downloadImage(data.output_url, outputPath);
          console.log(`/images/generated/blog/${slug}.jpg`);
          return;
        }
      }
      console.warn("WARNING: DeepAI call failed or returned no image. Switching to royalty-free fallback.");
    } catch (error) {
      console.warn(`WARNING: DeepAI image generation failed: ${error.message}. Switching to royalty-free fallback.`);
    }
  } else {
    console.warn("WARNING: DEEPAI_API_KEY is missing. Using high-quality royalty-free image fallback.");
  }

  // Royalty-free fallback download
  try {
    const fallbackUrl = selectFallbackImageUrl(slug, title);
    await downloadImage(fallbackUrl, outputPath);
    console.log(`/images/generated/blog/${slug}.jpg`);
  } catch (error) {
    console.error(`ERROR: Royalty-free image fallback failed: ${error.message}`);
    process.exit(1);
  }
}

main();
