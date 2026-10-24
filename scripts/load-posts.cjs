const fs = require('fs');
const path = require('path');
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
  const giftedParentOverrides = readObject(path.join(ROOT, 'src', 'data', 'giftedParentOverrides.json'));
  const giftedParentWave2Overrides = readObject(path.join(ROOT, 'src', 'data', 'giftedParentWave2Overrides.json'));
  const topicOverrides = { ...giftedParentOverrides, ...giftedParentWave2Overrides };

  const topicPosts = [...giftedParentPosts, ...giftedParentPostsWave2];
  const topicPostIds = requireUniqueIds(topicPosts, 'gifted topic catalogs');
  const legacyPosts = [...recent, ...historical];

  // Some Wave 2 IDs have older, intentionally non-publishable editorial stubs in
  // the legacy catalogs. The dedicated topic catalog is the authoritative version.
  // Shadow only those exact IDs and fail closed if a legacy copy ever becomes
  // publishable, so a real duplicate can never be hidden silently.
  for (const post of legacyPosts) {
    const id = String(post?.id || '').trim();
    if (topicPostIds.has(id) && isPublishable(post)) {
      throw new Error(`Duplicate publishable post id across topic and legacy catalogs: ${id}`);
    }
  }

  const combined = [
    ...topicPosts,
    ...legacyPosts.filter((post) => !topicPostIds.has(String(post?.id || '').trim())),
  ]
    .map((post) => ({ ...post, ...(topicOverrides[post.id] || {}) }))
    .sort((a, b) => String(b?.date || '').localeCompare(String(a?.date || '')));

  requireUniqueIds(combined, 'combined catalog');
  return combined;
};

module.exports = { loadPosts };
