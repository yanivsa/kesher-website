/**
 * Spread parenting-coordination cards in the unfiltered blog overview.
 *
 * The input has already been sorted into approved editorial archive order.
 * Preserve every publication date, the relative order of all other topics,
 * and the relative order of parenting-coordination posts. Do not change
 * filtered/search results or the dedicated topic hub.
 *
 * Multiple substantial same-day batches must remain spread out as the archive
 * grows. A single newly published topic post should not undo an older batch.
 */
type DatedBlogPost = Readonly<{
  id: string;
  category: string;
  date: string;
}>;

const TOPIC = 'תיאום הורי';
const MIN_SAME_DAY_BATCH = 3;
const OTHER_ARTICLES_BETWEEN_TOPIC_CARDS = 3;

export const spreadParentingCoordinationBatch = <T extends DatedBlogPost>(
  editoriallySorted: readonly T[],
): T[] => {
  const dates = new Map<string, number>();

  for (const post of editoriallySorted) {
    if (post.category === TOPIC) {
      dates.set(post.date, (dates.get(post.date) ?? 0) + 1);
    }
  }

  // Leave ordinary archive searches and unrelated single topic posts alone.
  // Existing substantial releases stay eligible even after new posts arrive.
  if (![...dates.values()].some((count) => count >= MIN_SAME_DAY_BATCH)) {
    return [...editoriallySorted];
  }

  const result: T[] = [];
  const pendingTopic: T[] = [];
  let otherArticlesSinceTopic = Number.POSITIVE_INFINITY;

  for (const post of editoriallySorted) {
    if (post.category === TOPIC) {
      if (pendingTopic.length === 0 && otherArticlesSinceTopic >= OTHER_ARTICLES_BETWEEN_TOPIC_CARDS) {
        result.push(post);
        otherArticlesSinceTopic = 0;
      } else {
        pendingTopic.push(post);
      }
      continue;
    }

    // Never reshuffle the unrelated editorial archive, including approved
    // financial article slots; we only insert pending topic cards between it.
    result.push(post);
    otherArticlesSinceTopic += 1;
    if (pendingTopic.length > 0 && otherArticlesSinceTopic >= OTHER_ARTICLES_BETWEEN_TOPIC_CARDS) {
      result.push(pendingTopic.shift()!);
      otherArticlesSinceTopic = 0;
    }
  }

  // When there are too few unrelated cards, keep every remaining article.
  // In this edge case three-card spacing is mathematically impossible.
  result.push(...pendingTopic);
  return result;
};
