# Kesher Website Remediation Plan

Date: 2026-06-11

## Goal

Bring the site, repository automation, and Cloudflare deployment to a production-ready state where leads are delivered reliably, private data is handled safely, search engines receive route-specific HTML, automated changes cannot bypass meaningful quality gates, and the live deployment can be verified end to end.

## Verified Baseline

- The production site is deployed from `main` to Cloudflare Pages.
- `npm run build` succeeds and `npm audit` reports no known dependency vulnerabilities.
- There are no automated tests or lint checks.
- Unknown routes and unsupported API methods currently return `200`.
- The contact Pages Function acknowledges leads without delivering them and logs submitted data.
- Route-specific metadata and structured data are client-rendered only.
- `main` is not protected and Jules PRs can be merged after a build-only check.
- The deployed assets use revalidation instead of long-lived immutable caching.

## Workstreams

### 1. Leads, Privacy, and Security

- Route all forms through a validated same-origin Pages Function.
- Deliver valid submissions to Formspree and never log submitted personal data.
- Reject invalid methods, origins, payloads, oversized fields, bots, and rapid duplicate submissions.
- Return accurate success/error responses and expose accessible status messages in the UI.
- Make the lead magnet a real downloadable resource after a successful request.
- Load the ElevenLabs widget only after explicit user consent.
- Update privacy and accessibility statements to match actual behavior.
- Add security headers and a restrictive Content Security Policy.

Proof:

- Automated API tests cover success, validation failure, spam, and unsupported methods.
- Browser tests prove both forms expose accurate accessible states.
- Live `GET /api/contact` returns `405`; valid `POST` reaches the configured provider.

### 2. Routing, SEO, and Cloudflare

- Add a real application 404 route and a generated `404.html`.
- Prerender every public route, including blog posts, so route content, metadata, canonical links, and Schema.org data exist in the first HTML response.
- Remove the catch-all `200` redirect.
- Correct Schema.org claims and broken asset references.
- Add route-specific social images and accurate canonical URLs.
- Add `_headers` rules for security and immutable asset caching.
- Retire the self-linking backlink Worker and document/deploy only Workers that have a legitimate route.

Proof:

- Built route HTML contains route-specific content and metadata before JavaScript.
- Unknown live URLs return `404`.
- Schema, sitemap, robots, and all internal routes pass validation.

### 3. Performance and Accessibility

- Lazy-load route modules, search, and the consent-gated chatbot.
- Use local optimized service images and avoid third-party image hotlinks.
- Add intrinsic image dimensions, eager loading only for the LCP image, and lazy loading elsewhere.
- Add dialog semantics, focus management, keyboard navigation, and accessible live regions.
- Ensure reduced-motion behavior and mobile layouts remain correct.

Proof:

- Initial JavaScript bundle is materially smaller than the baseline `481.71 kB`.
- Automated browser checks pass at desktop and mobile widths with no horizontal overflow.
- Axe reports no serious or critical accessibility violations on key routes.

### 4. Content Integrity

- Remove or neutralize unsupported credential, clinical, and guaranteed-result claims.
- Keep business positioning consistent across visible pages, structured data, search index, `llms.txt`, and automation prompts.
- Add an automated content validator for duplicate slugs/images, broken images, missing sitemap entries, unsafe HTML, unsupported claims, and minimum article quality.
- Remove low-quality legacy posts from public discovery until they meet the quality gate.

Proof:

- Content validation passes with no exceptions.
- All indexed posts have unique local images, valid structure, and matching sitemap entries.

### 5. Repository and Deployment Controls

- Add lint, unit/content tests, browser tests, and a single `npm run check` quality gate.
- Add CI for pull requests and pushes.
- Make deploy depend on the complete quality gate.
- Restrict Jules auto-merge to narrowly allowed files and require the same complete gate.
- Pin third-party Actions to immutable commit SHAs.
- Enable branch protection/rules for `main`, required CI, and automatic branch deletion.
- Replace the marketing README with operating documentation.
- Remove obsolete scripts, screenshots, and unused Worker code.

Proof:

- Local and GitHub CI checks pass.
- `main` protection is visible through the GitHub API.
- A production deployment from the corrected commit succeeds and live smoke tests pass.

## Implementation Evidence

Completed locally:

- `npm run check` passes.
- Browser coverage passes `18/18` tests across desktop and mobile Chromium.
- API coverage passes `6/6` unit tests.
- The build prerenders all `22` public routes plus `404.html`.
- Initial JavaScript is `258.03 kB` (`81.83 kB` gzip), reduced from the `481.71 kB` baseline.
- The obsolete `kesher-external-articles` and `kesher-seo-worker` Cloudflare Workers were deleted.

Pending publication proof:

- GitHub CI must pass on the remediation pull request and merged `main`.
- Cloudflare Pages must deploy the merged commit.
- Live routes, headers, metadata, API behavior, and `404` handling must pass the final smoke test.

## Completion Audit

Completion requires all proof items above, a clean working tree, a merged GitHub change, a successful Cloudflare Pages production deployment, and a final live-site verification. Findings discovered during verification are added to the appropriate workstream and fixed before completion.
