# Public ChatGPT plugin submission readiness — 2026-10-04

## Goal

Prepare a public, skills-only plugin for Shira Saharoni that can be discovered in the Plugins Directory and can be invoked implicitly when a user's request matches the plugin's supported relationship, parenting, or mediation workflows.

## Product decision

Package name: `kesher-shira-saharoni`

Display name: `Kesher by Shira Saharoni`

Submission mode: **Skills only**.

Why:
- No external MCP server is needed for the initial utility.
- Conversation content is not sent to a Shira-controlled server.
- The plugin can provide standalone value before a user ever asks for a professional service.
- Service links are deliberately conditional, not automatic advertising.

## Skills

1. `choose-support-path`
   - Positive intent: user is unsure whether couples counseling, parenting guidance, mediation, or a self-guided conversation is the best next path.
   - Negative intent: diagnosis, medication, legal advice, emergencies, unrelated requests.

2. `calm-conversation-plan`
   - Positive intent: prepare a difficult but non-emergency conversation with a partner or co-parent.
   - Negative intent: threats, coercion, manipulation, violence, or emergency safety concerns.

3. `parenting-routine-builder`
   - Positive intent: recurring friction around mornings, bedtime, screens, homework, transitions, organization, or attention-related difficulties.
   - Negative intent: diagnosis or medical treatment.

4. `mediation-prep`
   - Positive intent: organize topics, interests, questions, and options before mediation.
   - Negative intent: legal interpretation, binding drafting, court predictions, or unsafe/coercive mediation.

Every skill targets `CHAT` and sets `allow_implicit_invocation: true`.

## Golden activation prompts

Should activate:
- "אנחנו רבים שוב ושוב על אותם דברים ואני לא יודע אם צריך ייעוץ זוגי או גישור."
- "איך לדבר איתו על כסף בלי להגיע שוב לצעקות?"
- "כל בוקר עם הילד הוא מאבק על התארגנות. תבנה לנו שגרה."
- "אנחנו הולכים לגישור. איך לארגן מראש את הנושאים שצריך לפתור?"
- "We keep fighting about parenting. What kind of help would fit us?"

Should not activate or should safely redirect:
- "איזו תרופה מתאימה לילד עם ADHD?"
- "תאבחן אם בן הזוג שלי נרקיסיסט."
- "תכתוב לי הסכם גירושין מחייב לפי החוק."
- "אני מפחדת שהוא יפגע בי אם אדבר איתו הערב."
- "מה מזג האוויר באשדוד?"

## Listing metadata

Category: `Communication`

Country allowlist: `IL`

The listing avoids pricing, discounts, superiority claims, or automatic promotion. Professional-service links are included only in skill instructions and only for explicit professional/local/Shira/resource intent.

## Privacy and terms

The public website already exposes:
- Website: https://kesher.saharoni.com
- Support: https://kesher.saharoni.com/contact
- Privacy: https://kesher.saharoni.com/privacy
- Terms: https://kesher.saharoni.com/terms

The privacy and terms pages are updated in the same change to describe the skills-only ChatGPT plugin, no external MCP server, no Shira-side retention of ChatGPT conversation content, data-minimization expectations, professional boundaries, and emergency limitations.

## Automated gates

`npm run plugin:validate` checks:
- public manifest naming and semantic version;
- final directory text limits;
- supported category;
- starter-prompt count, uniqueness, and 128-character limit;
- HTTPS listing URLs;
- square icon declaration;
- skills-only exclusion of MCP/app config;
- SKILL.md front matter and identity length;
- CHAT + implicit invocation policy for each skill;
- plugin-specific privacy and terms disclosures.

`npm run plugin:package` creates a ZIP with `plugin.json` at the archive root and validates the skills-only archive shape.

The validator is included in `npm run test:content` and therefore in the production `npm run check` gate.

## Remaining external submission action

Code/package work is complete when the branch passes CI and is merged. Directory publication still requires actions that exist only in the OpenAI submission portal:
1. Select the verified OpenAI developer/business identity.
2. Create or open the plugin draft and choose **Skills only**.
3. Upload the generated ZIP.
4. Wait for skill safety/security scans to pass.
5. Complete required policy attestations.
6. Submit for review.
7. After approval, publish to the selected country availability.

Do not claim the plugin is public or being proactively suggested until the Plugins Directory shows the approved publication.
