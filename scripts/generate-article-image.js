import fs from 'fs';
import path from 'path';
import https from 'https';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function downloadImage(url, filepath) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      if (res.statusCode !== 200) {
        reject(new Error(`Failed to get '${url}' (${res.statusCode})`));
        return;
      }
      const file = fs.createWriteStream(filepath);
      res.pipe(file);
      file.on('finish', () => {
        file.close();
        resolve();
      });
    }).on('error', (err) => {
      fs.unlink(filepath, () => reject(err));
    });
  });
}

async function main() {
  const apiKey = process.env.DEEPAI_API_KEY;
  if (!apiKey) {
    console.warn('WARNING: DEEPAI_API_KEY is missing. Skipping DeepAI image generation.');
    console.warn('The article will be published with a fallback image. Please add DEEPAI_API_KEY to GitHub Secrets.');
    process.exit(0);
  }

  const args = process.argv.slice(2);
  const slug = args[0];
  const title = args[1] || slug;

  if (!slug) {
    console.error('ERROR: Missing required arguments. Usage: node generate-article-image.js <slug> [title]');
    process.exit(1);
  }

  const prompt = `A warm, natural, non-stock-looking image for a therapy, counseling, or family mediation blog post titled: "${title}". Calm, comforting, professional.`;

  console.log(`Generating image for '${slug}' with DeepAI...`);

  try {
    const response = await fetch('https://api.deepai.org/api/text2img', {
      method: 'POST',
      headers: {
        'Api-Key': apiKey,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text: prompt,
      }),
    });

    if (!response.ok) {
      console.error(`DeepAI API error: ${response.status} ${response.statusText}`);
      console.warn('Skipping image generation due to API failure. Fallback image will be used.');
      process.exit(0);
    }

    const data = await response.json();
    if (!data.output_url) {
      console.error('DeepAI API response missing output_url');
      console.warn('Skipping image generation. Fallback image will be used.');
      process.exit(0);
    }

    const imageUrl = data.output_url;
    const outputDir = path.join(__dirname, '..', 'public', 'images', 'generated', 'blog');

    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    const outputPath = path.join(outputDir, `${slug}.jpg`);
    console.log(`Downloading image from ${imageUrl} to ${outputPath}...`);

    await downloadImage(imageUrl, outputPath);
    console.log(`Image successfully generated and saved to ${outputPath}`);

  } catch (error) {
    console.error('Error during image generation:', error);
    console.warn('Skipping image generation due to an error. Fallback image will be used.');
    process.exit(0);
  }
}

main();
