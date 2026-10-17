const fs = require('fs');
const path = require('path');
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

const applySeoEnhancement = (post, override) => {
  if (!override) return post;

  const {
    contentPrefix = '',
    contentSuffix = '',
    ...fields
  } = override;

  const content = [contentPrefix, post.content, contentSuffix]
    .filter((part) => typeof part === 'string' && part.trim())
    .join('\n');

  return {
    ...post,
    ...fields,
    content,
  };
};

const assertUniqueIds = (posts) => {
  const seen = new Set();
  for (const post of posts) {
    const id = String(post?.id || '').trim();
    if (!id) throw new Error('Post without id in combined catalog');
    if (seen.has(id)) throw new Error(`Duplicate post id across catalogs: ${id}`);
    seen.add(id);
  }
};

const loadPosts = () => {
  const historical = readList(path.join(ROOT, 'src', 'data', 'posts.json'));
  const recent = readList(path.join(ROOT, 'src', 'data', 'postsRecent.json'));
  const seo = readObject(path.join(ROOT, 'src', 'data', 'seoQueryEnhancements.json'));
  const overrides = seo.overrides && typeof seo.overrides === 'object' && !Array.isArray(seo.overrides)
    ? seo.overrides
    : {};
  const additionalPosts = Array.isArray(seo.additionalPosts) ? seo.additionalPosts : [];

  const combined = [...recent, ...historical]
    .map((post) => applySeoEnhancement(post, overrides[post.id]));
  const existingIds = new Set(combined.map((post) => String(post?.id || '').trim()));
  const additions = additionalPosts.filter((post) => !existingIds.has(String(post?.id || '').trim()));
  const merged = [...additions, ...combined];

  assertUniqueIds(merged);
  return merged;
};

module.exports = { loadPosts, applySeoEnhancement };
