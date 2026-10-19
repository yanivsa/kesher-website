import { describe, expect, it } from 'vitest';
import postsRecent from '../src/data/postsRecent.json';

const required: Record<string, string[]> = {
  'how-to-stop-repeating-arguments': ['gottman-perpetual-problems-69-percent','how-to-repair-after-couple-fight','money-fights-communication'],
  'gottman-perpetual-problems-69-percent': ['how-to-stop-repeating-arguments','money-fights-communication'],
  'how-to-repair-after-couple-fight': ['how-to-stop-repeating-arguments','why-couples-fight-at-night-fatigue'],
  'why-couples-fight-at-night-fatigue': ['how-to-repair-after-couple-fight','how-to-stop-repeating-arguments'],
  'money-fights-communication': ['marriage-prep-financial-expectations-2026-08-24','how-to-stop-repeating-arguments'],
  'dating-apps-burnout-finding-a-partner': ['dating-fatigue-resilience','dating-emotional-needs-vs-checklists','dating-second-chance-criteria'],
  'dating-apps-exhaustion': ['dating-fatigue-resilience','dating-communication-early-stages'],
  'dating-transition-to-relationship-boundaries': ['dating-fatigue-resilience','dating-exclusivity-conversation','navigating-new-relationships-dating-balance'],
  'dating-second-chance-criteria': ['dating-emotional-needs-vs-checklists','dating-communication-early-stages'],
  'dating-exclusivity-conversation': ['dating-transition-to-relationship-boundaries','navigating-new-relationships-dating-balance'],
  'how-to-identify-a-gifted-child-parents-guide': ['gifted-children-social-difficulties','gifted-children-perfectionism-tears','gifted-adhd-executive-functions-struggle'],
  'gifted-children-social-difficulties': ['how-to-identify-a-gifted-child-parents-guide','gifted-children-first-days-adjustment'],
  'gifted-children-framework-preparation': ['gifted-children-first-days-adjustment','gifted-adhd-executive-functions-struggle'],
  'gifted-children-perfectionism-tears': ['gifted-children-social-difficulties','gifted-adhd-executive-functions-struggle'],
  'gifted-adhd-executive-functions-struggle': ['gifted-children-framework-preparation','gifted-children-first-days-adjustment'],
  'adhd-morning-conflict-dopamine-myth': ['early-habits-building-calm-mornings-children','adhd-morning-routine','first-grade-preparation-morning-routine'],
  'early-habits-building-calm-mornings-children': ['adhd-morning-conflict-dopamine-myth','first-grade-preparation-morning-routine','separation-anxiety-morning-dropoff'],
  'first-grade-preparation-morning-routine': ['early-habits-building-calm-mornings-children','adhd-first-grade-preparation'],
  'adhd-first-grade-preparation': ['school-entry-readiness-emotional-regulation-skills','first-grade-preparation-morning-routine'],
  'toddler-independence-morning-struggles': ['early-habits-building-calm-mornings-children','separation-anxiety-morning-dropoff'],
};

describe('priority-1 internal link backfill', () => {
  it('contains every required contextual blog link', () => {
    const bySlug = new Map((postsRecent as any[]).map(p => [p.slug, p]));
    for (const [source, targets] of Object.entries(required)) {
      const post = bySlug.get(source);
      expect(post, `missing source ${source}`).toBeTruthy();
      for (const target of targets) {
        expect(post.content, `${source} -> ${target}`).toContain(`href=\"/blog/${target}\"`);
      }
    }
  });
});
