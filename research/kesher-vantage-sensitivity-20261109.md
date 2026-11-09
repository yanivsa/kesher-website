# KESHER 2026-11-09 — Vantage Sensitivity / ילדים רגישים ומחוננים
Owner-authored, single immutable source. This document is editorial input, NOT proof of YouTube publication.

## Identity and deduplication
- source_slug: `vantage-sensitivity-sensitive-gifted-children`
- canonical_article_url: `https://kesher.saharoni.com/blog/vantage-sensitivity-sensitive-gifted-children`
- article_source: `src/data/manualPostsNov2026.ts`
- original_photo: `public/images/blog/vantage-sensitivity-parenting-hero.jpg`
- authoritative_content_sha256: COMPUTE from exact article content using the repository's canonical source hashing path after merge; refuse any upload with a mismatched SHA.
- provider identities / uploaded YouTube IDs: NONE at authoring time, inspect durable state prior to every attempt.
- NOTE: This is an entirely distinct topic from stress-crossover-after-work; never reuse its Video/Short IDs.
- Do not use Jules, Make or Composio for YouTube uploads; use GitHub Actions OAuth secrets and existing allowed media pipeline only after safety gates.

## Evidence boundaries
- Pluess & Belsky (2013): Vantage sensitivity is variability in benefit from positive experiences, not a promise of IQ/creativity gains. https://pubmed.ncbi.nlm.nih.gov/23025924/
- Nocentini, Menesini & Pluess (2018): randomized antibullying intervention involving 2,042 pupils, especially more responsive highly sensitive boys; do not claim universal advantage or quantified "tens of percent" gain. https://www.psychologicalscience.org/journals/clinical/2167702618782194/
- de Villiers, Lionetti & Pluess (2018): review of intervention response. https://pmc.ncbi.nlm.nih.gov/articles/PMC5959990/
- Highly Sensitive Child Scale is a research measure and not proof of giftedness or a clinical diagnosis. https://pubmed.ncbi.nlm.nih.gov/28933890/
- Never attribute the user's supplied fictional "translated quote" to Pluess. All wording below is original KESHER editorial material.

## Video Overview, target 95–125 s, Hebrew voice, landscape 16:9
[00–13, original photo: calm parent and child] "תגית קטנה בחולצה גורמת לבכי. רעש בכיתה מרגיש בלתי נסבל. והערה אחת נשארת בלב כל הערב. אולי שמעתם שצריך פשוט לחשל את הילד. אבל יש דרך נוספת להבין רגישות."
[13–30, graphic: two children in same supportive environment] "הפסיכולוג מייקל פלואס וג'יי בלסקי הציעו רעיון שנקרא רגישות יתרון. יש אנשים שעשויים להרוויח יותר מאחרים מסביבה חיובית ותומכת. זו לא נוסחה שמבטיחה הצלחה, ולא סימן לכך שהילד מחונן."
[30–50, visual: research book / school without fabricated data] "במחקר מבוקר של יותר מאלפיים תלמידים, השפעת תוכנית נגד בריונות הייתה בולטת במיוחד בקרב בנים בעלי רגישות גבוהה. זה לא אומר שכל ילד רגיש יהיה יצירתי או מנהיג יותר. זה אומר שכדאי לקחת ברצינות את הכוח של התערבות טובה."
[50–76, visual: parent kneeling at child height] "מה עושים בבית? קודם מזהים מה מציף באמת: אור, צליל, מגע או שינוי לא צפוי. אומרים: אני רואה שזה קשה לך. בוא ננסה פתרון. אפשר להקשיב לרגש ועדיין להציב גבול ברור."
[76–99, simple icons: quiet space, routine, social activity] "מכינים ילד לשינויים. נותנים מרחב רגוע להתאושש. שומרים על כללים עקביים, ושמים לב גם למה שמיטיב איתו: סקרנות, משחק, שיחה, הזדמנויות להצליח בקצב שלו."
[99–115, original photo and article call to action] "רגישות היא לא בהכרח תקלה, ולא כוח־על. היא הזמנה להכיר את הילד שלנו יותר טוב. לקריאה נוספת וכלים מעשיים, המאמר המלא באתר קשר."
- QA: no mechanical "10x", no promises of exceptional leadership or superiority, no false causal inference, no copyrighted footage.

## YouTube Short, target 53–60 s, native portrait 9:16
[00–07, hook; child touching fabric tag] "הילד שלכם בוכה מתגית בבגד, נבהל מרעש או נעלב מכל הערה? אל תמהרו לומר שהוא רגיש מדי."
[07–18, parent and child] "לפי תיאוריית רגישות היתרון של מייקל פלואס, יש ילדים שעשויים להרוויח במיוחד מסביבה תומכת, רגועה ועקבית."
[18–31, simple evidence slide] "במחקר מבוקר של יותר מאלפיים תלמידים, חלק מהילדים הרגישים הגיבו טוב יותר לתוכנית נגד בריונות. זה לא אומר שלכל ילד רגיש יש כוח־על."
[31–47, one practical example] "כשמשהו מציף, נסו לומר: אני רואה שהרעש קשה לך. בוא נמצא מקום שקט. ואת הגבול נשאיר ברור."
[47–58, confident CTA] "אל תנסו למחוק את הרגישות. עזרו לילד ללמוד מה טוב לו. המאמר המלא באתר קשר."
- Visual language: warm photographic original hero, pale cream and ocean teal brand, large legible Hebrew subtitles in RTL safe zones, correct narration spoken.
- YouTube title: "הילד רגיש במיוחד? יכול להיות שדווקא תמיכה תעזור לו לפרוח | שירה סהרוני"
- Description: includes https://kesher.saharoni.com/blog/vantage-sensitivity-sensitive-gifted-children and research caveat.
- Source-proof upload: require identical article slug+SHA in both metadata manifests, dedup check by identity & channel, public processing succeeded, authentic Hebrew audio review, final three public links.

## Release contract
- Article HTTP 200, correct title/canonical/body/photo.
- Overview and Short public YouTube URLs, valid playback and processing succeeded.
- Short 9:16, original topic-accurate visuals, actual Hebrew audio QA; no ASR-only hard fail.
- Until all 3 are independently verified: NOT DONE. Never report PR/video artifact as published URL.
