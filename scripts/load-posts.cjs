const fs = require('fs');
const path = require('path');
const vm = require('node:vm');
const { ROOT, isPublishable } = require('./content-policy.cjs');

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

const requireUniqueIds = (posts, label) => {
  const seen = new Set();
  for (const post of posts) {
    const id = String(post?.id || '').trim();
    if (!id) throw new Error(`Post without id in ${label}`);
    if (seen.has(id)) throw new Error(`Duplicate post id in ${label}: ${id}`);
    seen.add(id);
  }
  return seen;
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
  const legacyHeroOverrides = readObject(path.join(ROOT, 'src', 'data', 'legacyHeroOverrides.json'));

  const authoritativePosts = [
    ...manualPostsOct2026,
    ...giftedParentPosts,
    ...giftedParentPostsWave2,
  ];
  const authoritativeIds = requireUniqueIds(authoritativePosts, 'authoritative publication catalogs');
  const legacyPosts = [...recent, ...historical];

  // Dedicated publication catalogs are authoritative over older editorial stubs.
  // Shadow only an exact legacy ID whose old copy is non-publishable. If both
  // copies are publishable, fail closed instead of silently hiding a real duplicate.
  for (const post of legacyPosts) {
    const id = String(post?.id || '').trim();
    if (authoritativeIds.has(id) && isPublishable(post)) {
      throw new Error(`Duplicate publishable post id across authoritative and legacy catalogs: ${id}`);
    }
  }

  const combined = [
    ...authoritativePosts,
    ...legacyPosts.filter((post) => !authoritativeIds.has(String(post?.id || '').trim())),
  ].map((post) => ({
    ...post,
    ...(giftedParentOverrides[post.id] || {}),
    ...(giftedParentWave2Overrides[post.id] || {}),
    ...(legacyHeroOverrides[post.id] || {}),
  }));

  requireUniqueIds(combined, 'combined catalog');
  return combined;
};

module.exports = { loadPosts };
