import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const MAX_IMAGE_BYTES = 15 * 1024 * 1024;

const SEO_KEYWORD_MAP = {
  relocation: "ייעוץ זוגי ברילוקיישן ועלייה - שירה סהרוני",
  dating: "מציאת זוגיות ודייטים - יועצת זוגית ומנחת הורים",
  singleness: "התמודדות עם רווקות מאוחרת - שירה סהרוני ייעוץ זוגי",
  boundaries: "גבולות אישיים בזוגיות ובנישואים - יועצת זוגית באשדוד",
  parenting: "הדרכת הורים והנחיית משפחה - שירה סהרוני",
  default: "ייעוץ זוגי והדרכת הורים - שירה סהרוני אשדוד"
};

const FALLBACK_PHOTO_POOLS = {
  relocation: [
    "https://images.unsplash.com/photo-1513694203232-719a280e022f?auto=format&fit=crop&w=1200&h=675&q=80",
    "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?auto=format&fit=crop&w=1200&h=675&q=80",
    "https://images.unsplash.com/photo-1507652313519-d4e9174996dd?auto=format&fit=crop&w=1200&h=675&q=80"
  ],
  dating: [
    "https://images.unsplash.com/photo-1516589178581-6cd7833ae3b2?auto=format&fit=crop&w=1200&h=675&q=80",
    "https://images.unsplash.com/photo-1522529599102-193c0d76b5b6?auto=format&fit=crop&w=1200&h=675&q=80",
    "https://images.unsplash.com/photo-1494774157365-9e04c6720e47?auto=format&fit=crop&w=1200&h=675&q=80"
  ],
  singleness: [
    "https://images.unsplash.com/photo-1508214751196-bcfd4ca60f91?auto=format&fit=crop&w=1200&h=675&q=80",
    "https://images.unsplash.com/photo-1499209974431-9dddcece7f88?auto=format&fit=crop&w=1200&h=675&q=80",
    "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=1200&h=675&q=80"
  ],
  boundaries: [
    "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=1200&h=675&q=80",
    "https://images.unsplash.com/photo-1543269865-cbf427effbad?auto=format&fit=crop&w=1200&h=675&q=80"
  ],
  parenting: [
    "https://images.unsplash.com/photo-1485546246426-74dc88dec4d9?auto=format&fit=crop&w=1200&h=675&q=80",
    "https://images.unsplash.com/photo-1511895426328-dc8714191300?auto=format&fit=crop&w=1200&h=675&q=80"
  ],
  default: [
    "https://images.unsplash.com/photo-1516589178581-6cd7833ae3b2?auto=format&fit=crop&w=1200&h=675&q=80",
    "https://images.unsplash.com/photo-1522529599102-193c0d76b5b6?auto=format&fit=crop&w=1200&h=675&q=80",
    "https://images.unsplash.com/photo-1511895426328-dc8714191300?auto=format&fit=crop&w=1200&h=675&q=80"
  ]
};

function getCategoryKey(slug, title) {
  const combined = (slug + " " + title).toLowerCase();
  if (combined.includes("relocation") || combined.includes("רילוקיישן")) return "relocation";
  if (combined.includes("dating") || combined.includes("דייט") || combined.includes("סמס")) return "dating";
  if (combined.includes("singleness") || combined.includes("רווקות") || combined.includes("חברים")) return "singleness";
  if (combined.includes("boundaries") || combined.includes("מרחב") || combined.includes("מחנק")) return "boundaries";
  if (combined.includes("parent") || combined.includes("הורים") || combined.includes("ילדים")) return "parenting";
  return "default";
}

export function generateSeoAltText(slug, title) {
  const categoryKey = getCategoryKey(slug, title);
  const keywordSuffix = SEO_KEYWORD_MAP[categoryKey] || SEO_KEYWORD_MAP.default;
  return `${title} - ${keywordSuffix}`;
}

function selectFallbackImageUrl(slug, title) {
  const categoryKey = getCategoryKey(slug, title);
  const pool = FALLBACK_PHOTO_POOLS[categoryKey] || FALLBACK_PHOTO_POOLS.default;
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

async function tryGeminiImagen(apiKey, title, customPrompt) {
  const prompt = buildPrompt(title, customPrompt);
  const url = `https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:generateImages?key=${apiKey}`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt,
      config: { numberOfImages: 1, aspectRatio: "16:9", outputMimeType: "image/jpeg" }
    })
  });
  if (!response.ok) {
    throw new Error(`Gemini Imagen API returned status ${response.status}`);
  }
  const data = await response.json();
  if (data.generatedImages && data.generatedImages[0]?.image?.imageBytes) {
    return Buffer.from(data.generatedImages[0].image.imageBytes, "base64");
  }
  throw new Error("Gemini Imagen response missing image bytes");
}

async function tryUnsplashApi(accessKey, query) {
  const url = `https://api.unsplash.com/search/photos?query=${encodeURIComponent(query)}&orientation=landscape&per_page=10`;
  const response = await fetch(url, {
    headers: { Authorization: `Client-ID ${accessKey}` }
  });
  if (!response.ok) {
    throw new Error(`Unsplash API returned status ${response.status}`);
  }
  const data = await response.json();
  if (data.results && data.results.length > 0) {
    const photo = data.results[Math.floor(Math.random() * Math.min(5, data.results.length))];
    return `${photo.urls.raw}&auto=format&fit=crop&w=1200&h=675&q=80`;
  }
  throw new Error("No Unsplash search results found");
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

  const unsplashKey = process.env.UNSPLASH_ACCESS_KEY;
  const geminiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;

  // 1. Gemini Imagen
  if (geminiKey) {
    try {
      console.warn("Attempting image generation via Google Gemini Imagen API...");
      const imgBuffer = await tryGeminiImagen(geminiKey, title, customPrompt);
      fs.writeFileSync(outputPath, imgBuffer);
      console.log(`/images/generated/blog/${slug}.jpg`);
      return;
    } catch (error) {
      console.warn(`WARNING: Gemini Imagen API failed: ${error.message}. Trying royalty-safe fallback.`);
    }
  } else {
    console.warn("WARNING: GEMINI_API_KEY/GOOGLE_API_KEY unavailable. Trying royalty-safe fallback.");
  }

  // 3. Royalty-safe photography fallback: Unsplash API, then curated Unsplash/Pexels pool
  if (unsplashKey) {
    try {
      console.warn("Attempting image fallback via Unsplash Search API...");
      const text = (slug + " " + title).toLowerCase();
      let query = "couple warm conversation authentic living room";
      if (/כסף|חשבון|כלכלי|הוצאות|budget|money|financial/.test(text)) {
        query = "couple money finances budget conversation table";
      } else if (/טלפון|מסך|הסחות דעת|distraction|screen|phone/.test(text)) {
        query = "couple smartphone distraction living room disconnect";
      } else if (/בגיד|אמון|שקר|infidelity|trust/.test(text)) {
        query = "couple emotional reconciliation serious discussion daylight";
      } else if (/רווקות|שישי|singleness|single/.test(text)) {
        query = "thoughtful person reflection dining table warm light";
      } else if (/רילוקיישן|שפה|relocation|aliyah/.test(text)) {
        query = "couple living room relocation moving boxes conversation";
      } else if (/מחוננ|פרפקציוניזם|gifted|perfectionism/.test(text)) {
        query = "parent comforting young child desk studying";
      } else if (/קשב|adhd|ילקוט|בוקר|routine/.test(text)) {
        query = "parent helping young child morning routine school bag";
      } else if (/דייט|היכרות|dating/.test(text)) {
        query = "two people coffee date outdoor seating authentic conversation";
      } else if (/נישוא|חתונה|premarital|wedding/.test(text)) {
        query = "engaged couple planning table smiling natural light";
      } else if (/הור|ילד|parent|child/.test(text)) {
        query = "parent child warm emotional support home";
      }
      const imgUrl = await tryUnsplashApi(unsplashKey, query);
      await downloadImage(imgUrl, outputPath);
      console.log(`/images/generated/blog/${slug}.jpg`);
      return;
    } catch (error) {
      console.warn(`WARNING: Unsplash API fallback failed: ${error.message}. Trying curated photo pool.`);
    }
  }

  try {
    const fallbackUrl = selectFallbackImageUrl(slug, title);
    await downloadImage(fallbackUrl, outputPath);
    console.log(`/images/generated/blog/${slug}.jpg`);
    return;
  } catch (error) {
    console.error(`ERROR: DeepAI, Gemini, and royalty-safe fallback all failed: ${error.message}`);
    process.exit(1);
  }

}

main();
