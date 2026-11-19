# Parenting coordination: image asset staging and visual QA

Prepared 2026-11-19 for `kesher.saharoni.com` on a **non-production branch**. Four distinct original synthetic editorial photographs generated through the connected Adobe Firefly tool. Each rendered as JPEG at 16:9; original generated PNGs were previewed/re-encoded to JPEG by the service's image preview endpoint at max edge 1600px. All are **fictional scenes**, not actual customers, therapists, or depictions of a real case. Human editorial review is required before release.

- `parenting-coordination-first-meeting-process.jpg` — מפגש בירור ראשוני במסגרת תיאום הורי, עם מנחה והורים סביב שולחן; stored Git blob `b85effd7f8e61dda5ac379a9ed22d9031e4c3640`; Adobe request `4ea84b60-12a0-40f8-821f-6f08f7bf5d4d`.
- `parenting-coordination-cost-private-public.jpg` — שני הורים בוחנים מסמכים ותכנון הוצאות לפני התחייבות לתהליך; stored Git blob `ddbabda660264e2964d1da655f5420f3f46f2136`; Adobe request `77c082b7-9411-438d-b7d7-65f7e5638cf2`.
- `parenting-coordination-domestic-violence-safety.jpg` — אישה בשיחת בירור פרטית עם אשת מקצוע בחדר שקט ובטוח; stored Git blob `6e6478ed961f095ac11491fd0644b29a11dbaf0a`; Adobe request `b930bc85-6d9b-4ed2-9fa8-32085a3db9eb`.
- `child-refuses-parenting-time-after-divorce.jpg` — הורה משוחחת ברוגע עם ילד הנושא תיק ליד דלת הבית; stored Git blob `eafe3c5307107e902744e690f0253743b3cf11cf`; Adobe request `2bc32132-a2f6-439c-a196-160747542ca8`.

## Review checklist before publication

- [ ] Independently open and inspect the **actual committed JPEG bytes** at full size for compression, anatomy, scene relevance and absence of text/logos/watermarks.
- [ ] Verify image dimensions at least 1200×675, format, no collisions/duplicate SHA, exact correspondence to the article title and alt text.
- [ ] Confirm generation and commercial-use rights under the connected Adobe Firefly account's terms. Do not infer human subjects are Shira or real families.
- [ ] Obtain Shira/qualified editor's signoff on suitability, especially non-graphic portrayal of child refusal and domestic-violence safety.
- [ ] Only after professional legal/safety review, enter `image`, `imageAlt`, `imageProvider`, `imageSourceUrl`, `imageCredit` into the four still-unpublished draft items, without adding publication dates or importing into the live catalog.
- [ ] After genuine Schema-6 gateway approval, publish in small true-date batches, verify public JPEG HTTP 200, exact dimensions, social OG, alt, mobile crop and no confusion with real clients.

**No user-facing pages, sitemap, ads or automation changed by this asset branch.** This is only a reviewable checkpoint; media itself is not evidence of release approval.
