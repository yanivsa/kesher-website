/**
 * Editorial variety for the unfiltered blog overview only.
 *
 * Rebalance large same-day topic batches without editing publication metadata.
 * Original order is preserved within each category; the first suitable article
 * from another topic may be shown slightly earlier to avoid a solid wall of
 * same-topic cards. Search and category-filter results stay chronological.
 */
type DatedPost = Readonly<{
  id: string;
  date: string;
  category: string;
}>;

const MAX_SAME_DAY_TOPIC_RUN = 2;
const MAX_LOOKAHEAD = 32;
const MAX_DATE_GAP_DAYS = 14;
const MS_PER_DAY = 86_400_000;

const normalizedCategory = (category: string): string =>
  category === 'הנחיית הורים' ? 'הדרכת הורים' : category;

const publishedDay = (date: string): number =>
  Date.parse(`${date}T00:00:00Z`);

export const interleaveBlogTopicBatches = <T extends DatedPost>(
  chronologicalPosts: readonly T[],
): T[] => {
  const pending = [...chronologicalPosts];
  const ordered: T[] = [];

  let previousCategory = '';
  let previousDate = '';
  let sameDayRun = 0;

  while (pending.length > 0) {
    const first = pending[0];
    let pickIndex = 0;
    const firstCategory = normalizedCategory(first.category);

    // Only break up an actual batch from the same topic AND publication day.
    if (
      sameDayRun >= MAX_SAME_DAY_TOPIC_RUN
      && firstCategory === previousCategory
      && first.date === previousDate
    ) {
      const anchorDay = publishedDay(first.date);
      if (Number.isFinite(anchorDay)) {
        const end = Math.min(pending.length - 1, MAX_LOOKAHEAD);

        for (let index = 1; index <= end; index += 1) {
          const candidate = pending[index];
          const candidateDay = publishedDay(candidate.date);
          const gapInDays = (anchorDay - candidateDay) / MS_PER_DAY;

          if (
            Number.isFinite(candidateDay)
            && gapInDays >= 0
            && gapInDays <= MAX_DATE_GAP_DAYS
            && normalizedCategory(candidate.category) !== previousCategory
          ) {
            pickIndex = index;
            break;
          }
        }
      }
    }

    const [next] = pending.splice(pickIndex, 1);
    const category = normalizedCategory(next.category);

    if (category === previousCategory && next.date === previousDate) {
      sameDayRun += 1;
    } else {
      previousCategory = category;
      previousDate = next.date;
      sameDayRun = 1;
    }

    ordered.push(next);
  }

  return ordered;
};
