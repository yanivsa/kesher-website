import { describe, expect, it } from 'vitest';
import { preloadRoute } from '../src/App';

describe('preloadRoute', () => {
  it('returns memoized promises proving correct loader invocation', async () => {
    const aboutPromise = preloadRoute('/about');
    const aboutPromise2 = preloadRoute('/about/');
    expect(aboutPromise).toBe(aboutPromise2);

    const couplesPromise = preloadRoute('/services/couples');
    expect(couplesPromise).not.toBe(aboutPromise);

    const nowPromise = preloadRoute('/now');
    const nowPromise2 = preloadRoute('/now/');
    expect(nowPromise).toBe(nowPromise2);
    expect(nowPromise).not.toBe(aboutPromise);

    const friendsPromise = preloadRoute('/friends');
    const friendsPromise2 = preloadRoute('/friends/');
    expect(friendsPromise).toBe(friendsPromise2);
    expect(friendsPromise).not.toBe(nowPromise);

    const linksPromise = preloadRoute('/links');
    const linksPromise2 = preloadRoute('/links/');
    expect(linksPromise).toBe(linksPromise2);
    expect(linksPromise).not.toBe(friendsPromise);

    const crisisPromise = preloadRoute('/couples-crisis-ashdod');
    const crisisPromise2 = preloadRoute('/couples-crisis-ashdod/');
    expect(crisisPromise).toBe(crisisPromise2);
    expect(crisisPromise).not.toBe(aboutPromise);

    const adhdPromise = preloadRoute('/parenting-adhd-ashdod');
    const adhdPromise2 = preloadRoute('/parenting-adhd-ashdod/');
    expect(adhdPromise).toBe(adhdPromise2);
    expect(adhdPromise).not.toBe(crisisPromise);

    const ganYavnePromise = preloadRoute('/couples-counseling-gan-yavne');
    const ganYavnePromise2 = preloadRoute('/couples-counseling-gan-yavne/');
    expect(ganYavnePromise).toBe(ganYavnePromise2);
    expect(ganYavnePromise).not.toBe(adhdPromise);

    const toolsPromise = preloadRoute('/tools/chatgpt');
    const toolsPromise2 = preloadRoute('/tools/chatgpt/');
    expect(toolsPromise).toBe(toolsPromise2);
    expect(toolsPromise).not.toBe(adhdPromise);

    const mediationPromise = preloadRoute('/couples-mediation-ashdod');
    const mediationPromise2 = preloadRoute('/couples-mediation-ashdod/');
    expect(mediationPromise).toBe(mediationPromise2);
    expect(mediationPromise).not.toBe(ganYavnePromise);

    const notFoundPromise1 = preloadRoute('/this-does-not-exist');
    const notFoundPromise2 = preloadRoute('/also-missing');

    expect(notFoundPromise1).toBe(notFoundPromise2);
    expect(notFoundPromise1).not.toBe(aboutPromise);

    await Promise.all([
      aboutPromise,
      couplesPromise,
      nowPromise,
      friendsPromise,
      linksPromise,
      crisisPromise,
      adhdPromise,
      ganYavnePromise,
      mediationPromise,
      toolsPromise,
      notFoundPromise1,
    ]);
  });
});
