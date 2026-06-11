# Kesher website

Production website for Shira Saharoni, built with React, TypeScript, and Vite and deployed to Cloudflare Pages.

## Local development

```bash
npm ci
npm run dev
```

## Quality gates

```bash
npm run check
```

The full gate validates generated discovery files, linting, TypeScript, contact API behavior, content policy, prerendered routes, desktop/mobile layout, route metadata, and serious accessibility findings.

## Content policy

- Public articles must contain at least 500 words and five practical `h3` sections.
- Every public article must use a unique local image under `public/images/`.
- Thin legacy articles remain in `src/data/posts.json` but are excluded from public routes, search, sitemap, and `llms-full.txt`.
- Do not add unsupported credentials, clinical promises, or legal/mediation services.

## Deployment

Changes reach production only from `main`, after the complete quality gate passes. The deployment workflow publishes `dist/` to the `kesher-website` Cloudflare Pages project.

Production: [kesher.saharoni.com](https://kesher.saharoni.com)
