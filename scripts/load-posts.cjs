const fs = require('fs');
const path = require('path');
const { ROOT } = require('./content-policy.cjs');

const readList = (file) => {
  if (!fs.existsSync(file)) return [];
  const value = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (!Array.isArray(value)) throw new Error(`${file} must contain an array`);
  return value;
};

const readCatalogDirectory = (dir) => {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((name) => name.endsWith('.json'))
    .sort()
    .flatMap((name) => readList(path.join(dir, name)));
};

const loadPosts = () => {
  const historical = readList(path.join(ROOT, 'src', 'data', 'posts.json'));
  const recent = readList(path.join(ROOT, 'src', 'data', 'postsRecent.json'));
  const p1 = readCatalogDirectory(path.join(ROOT, 'src', 'data', 'p1'));
  const combined = [...recent, ...p1, ...historical];
  const seen = new Set();
  for (const post of combined) {
    const id = String(post?.id || '').trim();
    if (!id) throw new Error('Post without id in combined catalog');
    if (seen.has(id)) throw new Error(`Duplicate post id across catalogs: ${id}`);
    seen.add(id);
  }
  return combined;
};

module.exports = { loadPosts };
