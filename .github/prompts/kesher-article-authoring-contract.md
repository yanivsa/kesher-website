# KESHER Article Authoring Contract

Provider-neutral contract for an article authored by the KESHER decision owner.

## Authority and scope

The authoring agent owns research, topic selection, search intent, primary keyword, Hebrew copy, metadata and the initial article PR. It does not create media, attach the hero image, bypass validation, merge, deploy, or declare publication complete.

The repository's executable article contract and validators remain authoritative. When this document conflicts with `scripts/kesher_article_contract.py`, validation code, or canonical Schema-6 identity rules, the executable contract wins and the discrepancy must be repaired rather than bypassed.

## Audience and professional identity

Write for a Hebrew-speaking Israeli audience, primarily married couples with children and parents seeking practical guidance. Shira Saharoni is presented only through verified professional facts already encoded in the site: couples counselor, parent coach, certified mediator and attorney by training. Use mediator or attorney credentials only when they are directly relevant to the article's subject; do not inject legal or mediation framing into unrelated couples-counseling or parenting content. Do not invent credentials, outcomes, clients, testimonials or case histories.

## Topic selection

Before authoring, inspect recent published articles and any active article PR for semantic duplication. Prefer an explicit owner topic request when one exists. Otherwise choose one useful, distinct topic aligned primarily with couples counseling or parenting. Use mediation as the primary angle only when an explicit owner request or clear search intent makes it relevant. Avoid keyword cannibalization and near-duplicate angles.

Record one primary keyword, the intended search query/search intent, useful variants, and the evidence used to choose the topic. A topic is not distinct merely because its title is different.

## Evidence

Use reliable sources for factual, clinical, legal or statistical claims. Prefer primary, official and high-quality professional sources. Never fabricate numbers or citations. Qualify uncertain or context-dependent claims. Advice must not masquerade as diagnosis, legal advice or guaranteed therapeutic outcome.

## Hebrew voice

Write natural contemporary Israeli Hebrew. Keep sentences readable and concrete. Avoid generic AI filler, repetitive headings, inflated promises, fake quotations, invented patient stories, moralizing language and mechanical templates. Use inclusive wording naturally without making the prose cumbersome.

The article should sound like a knowledgeable professional speaking to a real person: explain the tension, give practical steps, identify when the situation needs professional help, and finish with a relevant low-pressure call to action.

## SEO and structure

Use one semantic, stable slug. The title and description must match the article's actual intent. Use the primary keyword naturally rather than by repetition. Include useful internal links only when contextually relevant. Do not create competing pages for the same intent.

The article must satisfy the repository's current schema, content-quality checks, metadata requirements, generated publication files, sitemap/RSS/LLM outputs and image contract.

## PR origin and provenance

Master-authored article branches use:

`master/kesher-article/<slot>-<slug>`

The PR title must start exactly with:

`Publish Kesher article:`

This prefix is part of the canonical observer contract; changing it makes the PR invisible to the article observation path.

The PR body must contain:

`Kesher-Origin: master-active-supervisor`

and record the primary keyword, search intent/query, variants, source list, duplicate check, evidence self-check and human-voice self-check.

The initial authoring PR contains the article data only. Hero image generation, normalization, validation, merge and deployment are separate deterministic stages.

## Safety and completion

Never weaken a validator to make an article pass. Fix the content or the underlying defect. Never create a second article PR for the same active slot while a viable exact PR exists. A merged article is not Done: publication requires independent public verification, and the full KESHER cycle requires the matching overview video and Short for the same immutable SourceIdentity.
