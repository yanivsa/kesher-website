import { describe, expect, it } from 'vitest';
import postSummaries from '../src/data/postSummaries.json';
import { interleaveBlogTopicBatches } from '../src/utils/interleaveBlogTopicBatches';

type Post = { id: string; date: string; category: string };

const idList = (posts: readonly Post[]) => posts.map(({ id }) => id);
const sameDayRun = (posts: readonly Post[]) => posts.reduce((max, post, index) => {
  let current = 1;
  for (let j = index - 1; j >= 0 && posts[j].category === post.category && posts[j].date === post.date; j--) current += 1;
  return Math.max(max, current);
}, 0);

describe('editorial variety on the unfiltered blog', () => {
  it('spreads the real one-day financial and parenting-coordination batches', () => {
    const input = postSummaries as Post[];
    const output = interleaveBlogTopicBatches(input);
    expect(output).toHaveLength(input.length);
    expect(new Set(idList(output)).size).toBe(input.length);
    expect([...idList(output)].sort()).toEqual([...idList(input)].sort());

    for (const category of ['כלכלת המשפחה', 'תיאום הורי']) {
      const original = input.filter((post) => post.category === category);
      const diversified = output.filter((post) => post.category === category);
      expect(idList(diversified)).toEqual(idList(original));
      expect(diversified.length).toBeGreaterThanOrEqual(category === 'כלכלת המשפחה' ? 17 : 5);
    }

    const finance = output.flatMap((post, index) =>
      post.category === 'כלכלת המשפחה' && post.date === '2026-11-17' ? [index] : []);
    const coordination = output.flatMap((post, index) =>
      post.category === 'תיאום הורי' && post.date === '2026-11-12' ? [index] : []);

    expect(finance).toHaveLength(17);
    expect(coordination).toHaveLength(5);
    expect(coordination[4] - coordination[0]).toBeGreaterThanOrEqual(8);
    expect(sameDayRun(output.slice(0, 35))).toBeLessThanOrEqual(2);
    expect(output[0].date).toBe(input[0].date);
    expect(output.map((p) => ({ id: p.id, date: p.date, category: p.category })).sort((a, b) => a.id.localeCompare(b.id)))
      .toEqual(input.map((p) => ({ id: p.id, date: p.date, category: p.category })).sort((a, b) => a.id.localeCompare(b.id)));
  });

  it('never mutates the original feed or moves articles more than 14 days forward', () => {
    const sample = [
      { id: 'a1', date: '2026-11-17', category: 'A' },
      { id: 'a2', date: '2026-11-17', category: 'A' },
      { id: 'a3', date: '2026-11-17', category: 'A' },
      { id: 'b1', date: '2026-11-15', category: 'B' },
      { id: 'a4', date: '2026-11-14', category: 'A' },
      { id: 'c1', date: '2026-10-01', category: 'C' },
    ] as const;
    const original = JSON.stringify(sample);
    const result = interleaveBlogTopicBatches(sample);

    expect(idList(result)).toEqual(['a1', 'a2', 'b1', 'a3', 'a4', 'c1']);
    expect(JSON.stringify(sample)).toBe(original);
    expect(result.find((post) => post.id === 'c1')?.date).toBe('2026-10-01');
    expect(interleaveBlogTopicBatches(result)).toEqual(result);
  });

  it('does not reshuffle short or single-topic result sets', () => {
    const singleCategory = [
      { id: 'x1', date: '2026-11-12', category: 'תיאום הורי' },
      { id: 'x2', date: '2026-11-12', category: 'תיאום הורי' },
      { id: 'x3', date: '2026-11-12', category: 'תיאום הורי' },
    ];
    expect(interleaveBlogTopicBatches(singleCategory)).toEqual(singleCategory);
    expect(interleaveBlogTopicBatches([])).toEqual([]);
  });
});
