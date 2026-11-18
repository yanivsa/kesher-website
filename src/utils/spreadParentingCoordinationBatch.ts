/**
 * Spread a large same-day parenting-coordination release among nearby blog posts.
 *
 * Input order is the existing editorial archive order, which already includes
 * explicitly approved financial-guidance archive slots. Keep that order intact
 * for every other topic, and never alter real publication dates or metadata.
 *
 * Used only for the unfiltered /blog overview. Search, tab filters and focused
 * topic hubs retain their existing behavior.
 */
type DatedBlogPost = Readonly<{
  id: string;
  category: string;
  date: string;
}>;

const TOPIC = 'תיאום הורי';
const MIN_SAME_DAY_BATCH = 3;
const BETWEEN_BATCH_ARTICLES = 3;

export const spreadParentingCoordinationBatch = <T extends DatedBlogPost>(
  editoriallySorted: readonly T[],
): T[] => {
  const dates = new Map<string, number>();

  for (const post of editoriallySorted) {
    if (post.category === TOPIC) {
      dates.set(post.date, (dates.get(post.date) || 0) + 1);
    }
  }

  // The input is already sorted; disperse only the latest substantial batch.
  const batchDate = editoriallySorted.find(
    (post) => post.category === TOPIC && (dates.get(post.date) || 0) >= MIN_SAME_DAY_BATCH,
  )?.date;

  if (!batchDate) return [...editoriallySorted];

  const batch = editoriallySorted.filter(
    (post) => post.category === TOPIC && post.date === batchDate,
  );
  const beforeBatch = editoriallySorted.findIndex(
    (post) => post.category === TOPIC && post.date === batchDate,
  );
  const others = editoriallySorted.filter(
    (post) => !(post.category === TOPIC && post.date === batchDate),
  );

  const output = others.slice(0, beforeBatch);
  let cursor = beforeBatch;

  for (const article of batch) {
    output.push(article);

    // Display three other articles after each item before the next topic card.
    const nextCursor = Math.min(cursor + BETWEEN_BATCH_ARTICLES, others.length);
    output.push(...others.slice(cursor, nextCursor));
    cursor = nextCursor;
  }

  output.push(...others.slice(cursor));
  return output;
};
