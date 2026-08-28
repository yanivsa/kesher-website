import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const sourceDir = '.image-staging';
const outputDir = 'public/images/shira';

const assets = [
  {
    name: 'shira-professional',
    parts: ['shira-professional.part00.b64', 'shira-professional.part01.b64'],
  },
  {
    name: 'shira-moments',
    parts: ['shira-moments.b64'],
  },
];

await mkdir(outputDir, { recursive: true });

for (const asset of assets) {
  const encodedParts = await Promise.all(
    asset.parts.map((part) => readFile(join(sourceDir, part), 'utf8')),
  );

  const encoded = encodedParts.map((part) => part.trim()).join('');
  const buffer = Buffer.from(encoded, 'base64');

  const isWebp =
    buffer.subarray(0, 4).toString('ascii') === 'RIFF' &&
    buffer.subarray(8, 12).toString('ascii') === 'WEBP';

  if (!isWebp) {
    throw new Error(`Invalid WebP data for ${asset.name}`);
  }

  const outputPath = join(outputDir, `${asset.name}.webp`);
  await writeFile(outputPath, buffer);
  console.log(`Prepared ${outputPath} (${buffer.length} bytes)`);
}
