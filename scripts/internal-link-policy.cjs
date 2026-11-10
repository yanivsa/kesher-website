const KESHER_ORIGIN = 'https://kesher.saharoni.com';

function normalizeBlogHref(href) {
  if (typeof href !== 'string' || !href.trim()) return null;
  const raw = href.trim();
  let pathname = null;
  try {
    if (raw.startsWith('/')) {
      pathname = new URL(raw, KESHER_ORIGIN).pathname;
    } else {
      const url = new URL(raw);
      if (url.origin !== KESHER_ORIGIN) return null;
      pathname = url.pathname;
    }
  } catch {
    return null;
  }
  if (!/^\/blog\/[^/]+\/?$/.test(pathname)) return null;
  return pathname.replace(/\/$/, '');
}

function extractBlogLinks(content) {
  const html = typeof content === 'string' ? content : '';
  const links = [];
  const seen = new Set();
  const re = /<a\b[^>]*\bhref\s*=\s*(["'])(.*?)\1/gi;
  let match;
  while ((match = re.exec(html))) {
    const normalized = normalizeBlogHref(match[2]);
    if (normalized && !seen.has(normalized)) {
      seen.add(normalized);
      links.push(normalized);
    }
  }
  return links;
}

function validateInternalLinkPlan(posts, plan) {
  const ids = new Set((posts || []).map((post) => post && post.id).filter(Boolean));
  const errors = [];
  for (const entry of plan || []) {
    if (!entry || typeof entry.source !== 'string') {
      errors.push('Invalid plan entry: missing source');
      continue;
    }
    if (!ids.has(entry.source)) errors.push(`Plan has missing source: ${entry.source}`);
    const targets = Array.isArray(entry.targets) ? entry.targets : [];
    const seenTargets = new Set();
    for (const target of targets) {
      if (seenTargets.has(target)) errors.push(`Plan has duplicate target for ${entry.source}: ${target}`);
      seenTargets.add(target);
      if (target === entry.source) errors.push(`Plan has self-link: ${entry.source}`);
      if (!ids.has(target)) errors.push(`Plan has missing target for ${entry.source}: ${target}`);
    }

    const placements = Array.isArray(entry.placements) ? entry.placements : [];
    const seenPlacements = new Set();
    for (const placement of placements) {
      const target = placement && typeof placement.target === 'string' ? placement.target : '';
      if (!target) {
        errors.push(`Plan has invalid placement target for ${entry.source}`);
        continue;
      }
      if (seenPlacements.has(target)) {
        errors.push(`Plan has duplicate placement metadata for ${entry.source}: ${target}`);
      }
      seenPlacements.add(target);
      if (!seenTargets.has(target)) {
        errors.push(`Plan placement target is not planned for ${entry.source}: ${target}`);
      }
      if (typeof placement.anchor !== 'string' || placement.anchor.trim().length < 4) {
        errors.push(`Plan placement missing anchor for ${entry.source}: ${target}`);
      }
      if (typeof placement.placementCue !== 'string' || placement.placementCue.trim().length < 12) {
        errors.push(`Plan placement missing cue for ${entry.source}: ${target}`);
      }
    }
    for (const target of seenTargets) {
      if (!seenPlacements.has(target)) {
        errors.push(`Plan missing placement metadata for ${entry.source}: ${target}`);
      }
    }
  }
  return errors;
}

function auditInternalLinkCoverage(posts, plan) {
  const postById = new Map((posts || []).map((post) => [post.id, post]));
  const rows = [];
  for (const entry of plan || []) {
    const sourcePost = postById.get(entry.source);
    const existing = new Set(extractBlogLinks(sourcePost && sourcePost.content));
    for (const target of Array.isArray(entry.targets) ? entry.targets : []) {
      rows.push({
        source: entry.source,
        target,
        present: existing.has(`/blog/${target}`),
      });
    }
  }
  const present = rows.filter((row) => row.present).length;
  return {
    planned: rows.length,
    present,
    missing: rows.length - present,
    rows,
  };
}

module.exports = {
  KESHER_ORIGIN,
  normalizeBlogHref,
  extractBlogLinks,
  validateInternalLinkPlan,
  auditInternalLinkCoverage,
};
