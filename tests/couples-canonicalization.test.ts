import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const repoRoot = process.cwd();
const legacyPathPattern = /\/services\/couples(?:\/(?=["'\x60\s<),}\]?#]|$)|(?=["'\x60\s<),}\]?#]|$))/g;
const textExtensions = new Set(['.ts', '.tsx', '.js', '.jsx', '.cjs', '.mjs', '.json', '.html', '.xml', '.txt', '.md']);

const walkTextFiles = (root: string): string[] => {
  if (!fs.existsSync(root)) return [];
  return fs.readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = path.join(root, entry.name);
    if (entry.isDirectory()) return walkTextFiles(fullPath);
    if (!textExtensions.has(path.extname(entry.name))) return [];
    if (entry.name === '_redirects') return [];
    return [fullPath];
  });
};

describe('couples counseling canonicalization', () => {
  it('keeps the retired URL out of source and generated public content', () => {
    const files = [
      ...walkTextFiles(path.join(repoRoot, 'src')),
      ...walkTextFiles(path.join(repoRoot, 'scripts')),
      ...walkTextFiles(path.join(repoRoot, 'public')),
    ];
    const offenders = files.flatMap((file) => {
      const content = fs.readFileSync(file, 'utf8');
      legacyPathPattern.lastIndex = 0;
      return legacyPathPattern.test(content) ? [path.relative(repoRoot, file)] : [];
    });
    expect(offenders).toEqual([]);
  });

  it('redirects both retired URL variants before the SPA fallback', () => {
    const redirects = fs.readFileSync(path.join(repoRoot, 'public/_redirects'), 'utf8').split(/\r?\n/);
    const catchAllIndex = redirects.indexOf('/* /index.html 200');
    const rules = [
      '/services/couples /couples-counseling-ashdod 301',
      '/services/couples/ /couples-counseling-ashdod 301',
    ];

    expect(catchAllIndex).toBeGreaterThan(-1);
    for (const rule of rules) {
      const index = redirects.indexOf(rule);
      expect(index).toBeGreaterThan(-1);
      expect(index).toBeLessThan(catchAllIndex);
    }
  });
});
