import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { createServer, type Server } from 'node:http';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

const script = resolve(process.cwd(), 'scripts/verify-production-internal-links.py');
let server: Server;
let baseUrl = '';
let routes: Record<string, { status: number; body: string }> = {};

beforeAll(async () => {
  server = createServer((req, res) => {
    const route = routes[req.url || ''] || { status: 404, body: 'not found' };
    res.writeHead(route.status, { 'content-type': 'text/html; charset=utf-8' });
    res.end(route.body);
  });

  await new Promise<void>((resolveListen) => {
    server.listen(0, '127.0.0.1', resolveListen);
  });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('test server did not bind');
  baseUrl = `http://127.0.0.1:${address.port}`;
});

afterAll(async () => {
  await new Promise<void>((resolveClose, reject) => {
    server.close((error) => (error ? reject(error) : resolveClose()));
  });
});

const runVerifier = (nextRoutes: typeof routes) => {
  routes = nextRoutes;
  const dir = mkdtempSync(join(tmpdir(), 'kesher-internal-links-'));
  const plan = join(dir, 'plan.json');
  writeFileSync(plan, JSON.stringify([{ source: 'source', targets: ['target'] }]), 'utf8');

  try {
    return spawnSync(
      'python3',
      [
        script,
        '--base-url',
        baseUrl,
        '--plan',
        plan,
        '--retries',
        '1',
        '--delay',
        '0',
      ],
      { cwd: process.cwd(), encoding: 'utf8', timeout: 15_000 },
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
};

describe('production internal-link smoke verifier', () => {
  it('passes when the source has exactly one planned link and the target is public', () => {
    const result = runVerifier({
      '/blog/source': { status: 200, body: '<a href="/blog/target">target</a>' },
      '/blog/target': { status: 200, body: 'ok' },
    });

    expect(result.status, `${result.stdout}\n${result.stderr}`).toBe(0);
    expect(result.stdout).toContain('1/1 planned links verified');
  });

  it('fails when a planned link is missing', () => {
    const result = runVerifier({
      '/blog/source': { status: 200, body: '<p>no planned link</p>' },
      '/blog/target': { status: 200, body: 'ok' },
    });

    expect(result.status).not.toBe(0);
    expect(`${result.stdout}\n${result.stderr}`).toContain('expected exactly once');
  });

  it('fails when a planned link is duplicated', () => {
    const result = runVerifier({
      '/blog/source': {
        status: 200,
        body: '<a href="/blog/target">one</a><a href="/blog/target">two</a>',
      },
      '/blog/target': { status: 200, body: 'ok' },
    });

    expect(result.status).not.toBe(0);
    expect(`${result.stdout}\n${result.stderr}`).toContain('found 2');
  });

  it('fails when a planned target is not public', () => {
    const result = runVerifier({
      '/blog/source': { status: 200, body: '<a href="/blog/target">target</a>' },
      '/blog/target': { status: 404, body: 'missing' },
    });

    expect(result.status).not.toBe(0);
    expect(`${result.stdout}\n${result.stderr}`).toContain('target returned HTTP 404');
  });
});
