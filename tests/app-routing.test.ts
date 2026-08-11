import { describe, expect, it } from 'vitest';
import { preloadRoute } from '../src/App';

describe('preloadRoute', () => {
  it('returns memoized promises proving correct loader invocation', async () => {
    const aboutPromise = preloadRoute('/about');
    const aboutPromise2 = preloadRoute('/about/');
    expect(aboutPromise).toBe(aboutPromise2);

    const couplesPromise = preloadRoute('/services/couples');
    expect(couplesPromise).not.toBe(aboutPromise);

    const notFoundPromise1 = preloadRoute('/this-does-not-exist');
    const notFoundPromise2 = preloadRoute('/also-missing');

    expect(notFoundPromise1).toBe(notFoundPromise2);
    expect(notFoundPromise1).not.toBe(aboutPromise);

    await Promise.all([aboutPromise, couplesPromise, notFoundPromise1]);
  });
});
