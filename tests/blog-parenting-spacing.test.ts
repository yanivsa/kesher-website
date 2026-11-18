import { describe, expect, it } from 'vitest';
import summaries from '../src/data/postSummaries.json';
import { getEditorialArchiveSortDate, getFinancialArchiveSlot } from '../src/data/financialGuidanceArchive';
import { spreadParentingCoordinationBatch } from '../src/utils/spreadParentingCoordinationBatch';

type Article = { id: string; category: string; date: string };
const ids = (posts: readonly Article[]) => posts.map((post) => post.id);

describe('unfiltered blog topic spacing', () => {
  it('spreads all five real parenting guides without disturbing finance archive slots or publication dates', () => {
    const source = [...summaries].sort((a, b) =>
      getEditorialArchiveSortDate(b.id, b.date).localeCompare(getEditorialArchiveSortDate(a.id, a.date))
      || b.date.localeCompare(a.date),
    );
    const original = JSON.stringify(source);
    const output = spreadParentingCoordinationBatch(source);

    const originalCoordination = source.filter((post) => post.category === 'תיאום הורי');
    const displayedCoordination = output.filter((post) => post.category === 'תיאום הורי');
    expect(originalCoordination).toHaveLength(5);
    expect(ids(displayedCoordination)).toEqual(ids(originalCoordination));

    const positions = output.flatMap((post, index) =>
      post.category === 'תיאום הורי' ? [index] : []);
    for (let index = 1; index < positions.length; index += 1) {
      expect(positions[index] - positions[index - 1]).toBeGreaterThanOrEqual(3);
    }

    expect(output).toHaveLength(source.length);
    expect(new Set(ids(output)).size).toBe(source.length);
    expect([...ids(output)].sort()).toEqual([...ids(source)].sort());
    const otherArticles = (posts: readonly Article[]) => posts.filter((post) => post.category !== 'תיאום הורי');
    expect(ids(otherArticles(output))).toEqual(ids(otherArticles(source)));

    // Financial posts already have approved editorial archive positions.
    const financeIds = (posts: readonly Article[]) => posts
      .filter((post) => Boolean(getFinancialArchiveSlot(post.id))).map((post) => post.id);
    expect(financeIds(output)).toEqual(financeIds(source));
    expect(JSON.stringify(source)).toBe(original);
    expect(ids(spreadParentingCoordinationBatch(output))).toEqual(ids(output));

    for (const item of source) {
      expect(output.find((post) => post.id === item.id)?.date).toBe(item.date);
    }
  });

  it('does nothing without a substantial same-day topic batch or without any other articles', () => {
    const data = [
      { id: 'a', date: '2026-11-18', category: 'הדרכת הורים' },
      { id: 'b', date: '2026-11-17', category: 'תיאום הורי' },
      { id: 'c', date: '2026-11-16', category: 'תיאום הורי' },
      { id: 'd', date: '2026-11-15', category: 'ייעוץ זוגי' },
    ];
    expect(spreadParentingCoordinationBatch(data)).toEqual(data);

    const onlyCoordination = ['one', 'two', 'three'].map((id) => ({
      id, date: '2026-11-12', category: 'תיאום הורי',
    }));
    expect(spreadParentingCoordinationBatch(onlyCoordination)).toEqual(onlyCoordination);
  });

  it('keeps the ordinary feed in place while placing three other topics between a same-day batch', () => {
    const data = [
      { id: 'latest', date: '2026-11-18', category: 'ייעוץ זוגי' },
      ...['a', 'b', 'c', 'd'].map((id) => ({ id, date: '2026-11-12', category: 'תיאום הורי' })),
      ...['x', 'y', 'z', 'w', 'u', 'v', 't'].map((id) => ({ id, date: '2026-11-11', category: 'הדרכת הורים' })),
    ];
    expect(ids(spreadParentingCoordinationBatch(data))).toEqual([
      'latest', 'a', 'x', 'y', 'z', 'b', 'w', 'u', 'v', 'c', 't', 'd',
    ]);
  });
});
