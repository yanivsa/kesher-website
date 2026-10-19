import rules from './internalLinkBackfill.json';

type BackfillItem = {
  target: string;
  anchor: string;
  before: string;
  after: string;
};

type BackfillRule = {
  source: string;
  afterHeadingIncludes: string;
  items: BackfillItem[];
};

type LinkablePost = {
  id: string;
  content: string;
};

const backfillRules = rules as BackfillRule[];

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const decodeHeadingText = (html: string) => html
  .replace(/<[^>]+>/g, ' ')
  .replace(/&quot;/gi, '"')
  .replace(/&#(?:39|x27);/gi, "'")
  .replace(/&amp;/gi, '&')
  .replace(/&nbsp;/gi, ' ')
  .replace(/\s+/g, ' ')
  .trim();

const escapeText = (value: string) => value
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;');

const hasInternalTarget = (content: string, target: string) => {
  const slug = escapeRegExp(target);
  const pattern = new RegExp(
    `href=["'](?:https:\\/\\/kesher\\.saharoni\\.com)?\\/blog\\/${slug}(?:[?#][^"']*)?["']`,
    'i',
  );
  return pattern.test(content);
};

const findInsertionOffset = (content: string, headingNeedle: string) => {
  const headingPattern = /<h3\b[^>]*>([\s\S]*?)<\/h3>/gi;
  let match: RegExpExecArray | null;
  while ((match = headingPattern.exec(content))) {
    if (decodeHeadingText(match[1]).includes(headingNeedle)) {
      return match.index + match[0].length;
    }
  }
  return null;
};

const renderItem = (item: BackfillItem) =>
  `${escapeText(item.before)}<a href="/blog/${item.target}">${escapeText(item.anchor)}</a>${escapeText(item.after)}`;

export const applyInternalLinkBackfill = <T extends LinkablePost>(post: T): T => {
  const rule = backfillRules.find((candidate) => candidate.source === post.id);
  if (!rule) return post;

  const missingItems = rule.items.filter((item) => !hasInternalTarget(post.content, item.target));
  if (missingItems.length === 0) return post;

  const insertionOffset = findInsertionOffset(post.content, rule.afterHeadingIncludes);
  if (insertionOffset === null) return post;

  const paragraph = `<p data-kesher-internal-link-backfill="${post.id}">${missingItems.map(renderItem).join(' ')}</p>`;
  return {
    ...post,
    content: `${post.content.slice(0, insertionOffset)}${paragraph}${post.content.slice(insertionOffset)}`,
  };
};

export const internalLinkBackfillRules = backfillRules;
