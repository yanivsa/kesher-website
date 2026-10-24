const fs = require('fs');
const path = require('path');
const vm = require('node:vm');
const { ROOT } = require('./content-policy.cjs');

const readList = (file) => {
  if (!fs.existsSync(file)) return [];
  const value = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (!Array.isArray(value)) throw new Error(`${file} must contain an array`);
  return value;
};

const readObject = (file) => {
  if (!fs.existsSync(file)) return {};
  const value = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (!value || Array.isArray(value) || typeof value !== 'object') {
    throw new Error(`${file} must contain an object`);
  }
  return value;
};

const readTrustedTsList = (file, exportName) => {
  if (!fs.existsSync(file)) return [];
  const source = fs.readFileSync(file, 'utf8');
  const exportPattern = new RegExp(`export\\s+default\\s+${exportName}\\s*;?\\s*$`);
  if (!exportPattern.test(source)) {
    throw new Error(`${file} must default-export ${exportName}`);
  }

  const executable = source.replace(exportPattern, '');
  const context = Object.create(null);
  vm.runInNewContext(
    `${executable}\nthis.__kesherLoadedPosts = ${exportName};`,
    context,
    { filename: file, timeout: 1000 },
  );
  const value = context.__kesherLoadedPosts;
  if (!Array.isArray(value)) throw new Error(`${file} must contain an array export`);
  return value;
};

const loadPosts = () => {
  const historical = readList(path.join(ROOT, 'src', 'data', 'posts.json'));
  const recent = readList(path.join(ROOT, 'src', 'data', 'postsRecent.json'));
  const giftedParentPosts = readList(path.join(ROOT, 'src', 'data', 'giftedParentPosts.json'));
  const giftedParentPostsWave2 = readList(path.join(ROOT, 'src', 'data', 'giftedParentPostsWave2.json'));
  const manualPostsOct2026 = readTrustedTsList(
    path.join(ROOT, 'src', 'data', 'manualPostsOct2026.ts'),
    'manualPostsOct2026',
  );
  const giftedParentOverrides = readObject(path.join(ROOT, 'src', 'data', 'giftedParentOverrides.json'));
  const giftedParentWave2Overrides = readObject(path.join(ROOT, 'src', 'data', 'giftedParentWave2Overrides.json'));

  const combined = [
    ...manualPostsOct2026,
    ...giftedParentPosts,
    ...giftedParentPostsWave2,
    ...recent,
    ...historical,
  ].map((post) => ({
    ...post,
    ...(giftedParentOverrides[post.id] || {}),
    ...(giftedParentWave2Overrides[post.id] || {}),
  }));

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
