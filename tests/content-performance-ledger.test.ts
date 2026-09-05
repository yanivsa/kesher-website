import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { describe, expect, it } from 'vitest';

const script = 'scripts/content_performance_ledger.py';

function sample(clicks = 3) {
  return {
    schema_version: 1,
    content_id: 'article:example',
    content_type: 'article',
    slug: 'example',
    publish_date: '2026-09-04',
    topic: 'זוגיות',
    public_url: 'https://kesher.saharoni.com/blog/example',
    window: '24h',
    source: 'ga4+search-console',
    observed_at: '2026-09-04T00:00:00+03:00',
    metrics: {
      lead_clicks: 1,
      search_clicks: clicks,
      search_impressions: 10,
      search_ctr: clicks / 10,
    },
    decision: 'observe',
  };
}

function run(record: object, ledger: string) {
  const dir = mkdtempSync(join(tmpdir(), 'kesher-performance-'));
  const input = join(dir, 'record.json');
  writeFileSync(input, JSON.stringify(record), 'utf8');
  return spawnSync('python3', [script, input, '--ledger', ledger], {
    cwd: process.cwd(),
    encoding: 'utf8',
  });
}

describe('content performance ledger', () => {
  it('rejects unrecognized or negative metrics', () => {
    const dir = mkdtempSync(join(tmpdir(), 'kesher-ledger-'));
    const ledger = join(dir, 'ledger.jsonl');
    const unknown = sample() as ReturnType<typeof sample> & { metrics: Record<string, number> };
    unknown.metrics.unknown = 1;
    expect(run(unknown, ledger).status).not.toBe(0);

    const negative = sample();
    negative.metrics.search_clicks = -1;
    expect(run(negative, ledger).status).not.toBe(0);
  });

  it('rejects malformed or timezone-less observation timestamps', () => {
    const dir = mkdtempSync(join(tmpdir(), 'kesher-ledger-'));
    const ledger = join(dir, 'ledger.jsonl');

    const malformed = sample();
    malformed.observed_at = 'not-a-timestamp';
    expect(run(malformed, ledger).status).not.toBe(0);

    const withoutTimezone = sample();
    withoutTimezone.observed_at = '2026-09-04T00:00:00';
    expect(run(withoutTimezone, ledger).status).not.toBe(0);
  });

  it('upserts the same content/window/source instead of duplicating it', () => {
    const dir = mkdtempSync(join(tmpdir(), 'kesher-ledger-'));
    const ledger = join(dir, 'ledger.jsonl');
    expect(run(sample(3), ledger).status).toBe(0);
    expect(run(sample(4), ledger).status).toBe(0);

    const rows = readFileSync(ledger, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
    expect(rows).toHaveLength(1);
    expect(rows[0].metrics.search_clicks).toBe(4);
  });

  it('validates mandatory fields: publish_date, topic, public_url', () => {
    const dir = mkdtempSync(join(tmpdir(), 'kesher-ledger-'));
    const ledger = join(dir, 'ledger.jsonl');

    const missingPublishDate = sample();
    delete (missingPublishDate as Record<string, unknown>).publish_date;
    expect(run(missingPublishDate, ledger).status).not.toBe(0);

    const missingTopic = sample();
    delete (missingTopic as Record<string, unknown>).topic;
    expect(run(missingTopic, ledger).status).not.toBe(0);

    const invalidUrl = sample();
    invalidUrl.public_url = 'http://invalid-url.com';
    expect(run(invalidUrl, ledger).status).not.toBe(0);
  });

  it('accepts decision values: continue_topic, change_headline, change_time, stop_type', () => {
    const dir = mkdtempSync(join(tmpdir(), 'kesher-ledger-'));
    const ledger = join(dir, 'ledger.jsonl');

    const rec = sample();
    rec.decision = 'continue_topic';
    expect(run(rec, ledger).status).toBe(0);
  });

  it('validates the seed ledger analytics/content-performance.jsonl', () => {
    const seed = readFileSync('analytics/content-performance.jsonl', 'utf8').trim();
    expect(seed).not.toBe('');
    const parsed = JSON.parse(seed.split('\n')[0]);
    expect(parsed.content_id).toMatch(/^article:[a-z0-9-]+$/);
    expect(parsed.public_url).toMatch(/^https:\/\/kesher\.saharoni\.com\/blog\//);
    expect(parsed.publish_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
