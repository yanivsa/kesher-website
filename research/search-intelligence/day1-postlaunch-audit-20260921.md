# Day 1 Post-Launch Audit — 2026-09-21

## Scope

Post-launch verification for Search Intelligence Wave 1 after merge/deploy, plus the first PPC and conversion-tracking readiness audit.

Production domain:

`https://kesher.saharoni.com`

Audit date:

2026-09-21 (Asia/Jerusalem)

---

## Google Search Console

Property:

`sc-domain:saharoni.com`

### Wave 1 URL Inspection

All seven Wave 1 URLs currently return:

- verdict: PASS
- coverageState: Submitted and indexed
- indexingState: INDEXING_ALLOWED
- pageFetchState: SUCCESSFUL
- robotsTxtState: ALLOWED
- Google canonical matches the intended Kesher URL

| URL | GSC state | Last crawl (UTC) |
| --- | --- | --- |
| /services/couples | Submitted and indexed | 2026-09-19T23:55:08Z |
| /blog/relationship-after-childbirth | Submitted and indexed | 2026-09-21T16:47:04Z |
| /blog/dating-transition-to-relationship-boundaries | Submitted and indexed | 2026-09-11T18:56:45Z |
| /blog/communication-breakdown | Submitted and indexed | 2026-09-10T11:36:44Z |
| /blog/boundaries-without-punishments | Submitted and indexed | 2026-09-13T01:33:47Z |
| /services/parenting | Submitted and indexed | 2026-09-11T16:34:37Z |
| /blog/money-fights-communication | Submitted and indexed | 2026-09-21T18:02:05Z |

The two newly publishable Wave 1 articles were crawled by Google on 2026-09-21 and are already reported as indexed.

### Sitemap

Before refresh, Search Console still showed the older 102-URL snapshot.

The production sitemap was resubmitted during this audit.

Current Search Console sitemap state:

- path: https://kesher.saharoni.com/sitemap.xml
- submitted URLs: 108
- indexed field reported by sitemap API: 0
- errors: 0
- warnings: 0
- pending: false
- last submitted: 2026-09-21T18:23:42.616Z
- last downloaded: 2026-09-21T18:23:43.199Z

Important interpretation:

The sitemap-level `indexed=0` field remains inconsistent with direct URL Inspection, because all seven audited Wave 1 URLs return `Submitted and indexed`.

Do not use the sitemap `indexed=0` value alone as evidence that the site is not indexed.

### Pre-change Search Analytics baseline

Final-data window:

2026-08-22 → 2026-09-18

Notable Wave 1 page rows:

- /blog/communication-breakdown — 2 clicks / 3 impressions / CTR 66.7% / avg position 5.33
- /services/parenting — 1 click / 6 impressions / CTR 16.7% / avg position 3
- /services/couples — 0 clicks / 1 impression / avg position 4
- /blog/dating-transition-to-relationship-boundaries — 0 clicks / 1 impression / avg position 95

Exact query rows exposed by GSC:

- `לא להראות התלהבות בתחילת קשר` → dating-transition-to-relationship-boundaries — 1 impression / position 95
- `פגישה ראשונה` → new-relationship-initial-intentions — 1 impression / position 82

Privacy filtering means this is not a complete query inventory.

---

## GA4

Property:

`properties/551923843`

Display name:

`קשר - שירה סהרוני`

Timezone:

`Asia/Jerusalem`

### Pre-change baseline

Window:

2026-08-24 → 2026-09-19

Sessions by source/medium:

- direct / none — 32
- chatgpt.com / ai-assistant — 5
- google / organic — 2
- l.instagram.com / referral — 2

Total sessions represented by the source rows: 41.

Top landing pages:

- / — 27 sessions
- /blog/new-relationship-initial-intentions — 5
- /friends — 2
- /appointment — 1
- /blog/dating-apps-exhaustion — 1
- /blog/dating-fatigue-resilience — 1

No key events were reported in the baseline report.

### Immediate post-launch data

GA4 standard reports for 2026-09-20 → 2026-09-21 currently return no rows.

Realtime audit during this review also returned no active event rows in the sampled 30-minute window.

This does not by itself prove measurement failure: there may simply have been no consented/current traffic in the sampled period.

Production deployment status confirms that a valid Google measurement configuration is injected into the production build.

### GA4 Key Events configuration

Current GA4 Key Events:

- purchase
- close_convert_lead
- qualify_lead

The desired Kesher events are not currently configured as GA4 Key Events:

- whatsapp_click
- phone_click
- booking_start
- booking_complete
- lead_submit

This is a GA4 Admin configuration gap.

Current Composio GA4 tooling is read-only for Key Event administration, so this cannot be corrected through the connected GA4 API tool.

---

## Website conversion instrumentation

Repository review confirms the site already emits:

- phone_click
- whatsapp_click
- booking_start
- booking_complete
- lead_submit
- generate_lead

Attribution support exists for:

- utm_source
- utm_medium
- utm_campaign
- utm_term
- utm_content
- entry page
- variant ID
- presence of gclid / gbraid / wbraid

Calendly booking tracking includes:

- booking_start
- booking_complete
- booking confirmation context
- browser/server reconciliation path
- UTM forwarding into Calendly

The deployment status `booking-tracking/google-measurement` is SUCCESS.

---

## Google Ads

Accessible working customer:

`3920602983`

Currency:

ILS

Timezone:

Asia/Jerusalem

The second accessible resource returned by OAuth currently requires manager scoping and was not used.

### Current Kesher campaign

Campaign:

`Search_CouplesCounseling_Ashdod_Optimized_1785995331`

Campaign ID:

`24114214927`

Current state:

`PAUSED`

No spend was enabled during this audit.

Settings:

- channel: Search
- budget: 50 ILS/day
- bidding: MANUAL_CPC
- ad-group CPC bid: 0.01 ILS
- Google Search: enabled
- Search Partners: enabled
- Display Network: disabled

### Geographic targeting

Positive geo target:

`Ashdod, South District, Israel`

Geo target ID:

`1007965`

Location mode:

- positiveGeoTargetType: PRESENCE
- negativeGeoTargetType: PRESENCE

Therefore the paused Kesher campaign is configured for physical presence in Ashdod, not merely search interest in Ashdod.

### Keywords

The current ad group uses tightly local terms with Exact/Phrase matching, including:

- ייעוץ זוגי באשדוד
- טיפול זוגי באשדוד
- יועצת זוגית באשדוד
- יועץ זוגי באשדוד
- ייעוץ נישואין באשדוד
- קליניקה לייעוץ זוגי באשדוד
- couple therapy ashdod

It also includes `סדנת זוגיות באשדוד`, which should be reviewed before launch because it may represent a different service intent.

Campaign/ad-group negatives include informational/employment/training intents such as:

- לימודים
- דרושים
- פורום
- קורס
- חינם / חינמי
- מאמר
- ויקיפדיה
- עבודה סוציאלית
- רווחה

### Google Ads conversions

Four Kesher conversion actions exist and are enabled:

1. KESHER - Lead Form
   - primary
   - included in Conversions

2. KESHER - Booking Complete
   - primary
   - included in Conversions

3. KESHER - Phone Click
   - secondary
   - not included in primary Conversions

4. KESHER - WhatsApp Click
   - secondary
   - not included in primary Conversions

Repository code was checked against Google Ads tag snippets.

The four `send_to` destinations match exactly.

Therefore direct Google Ads conversion forwarding is wired correctly in code.

### Campaign performance

For 2026-08-22 → 2026-09-20:

- no impressions
- no clicks
- no cost
- no search-term rows
- no landing-page performance rows

Reason: the current campaign is paused and has not delivered during the audited period.

### PPC issues before activation

1. Campaign is paused.
2. Manual CPC ad-group bid is only 0.01 ILS and is not a realistic launch bid.
3. Search Partners are enabled; decide deliberately whether to keep them for the initial controlled test.
4. GA4 custom conversion events are not marked as GA4 Key Events.
5. One enabled RSA contained the unsupported absolute claim:
   `שמירה מלאה על הפרטיות`.

### PPC correction performed during audit

The campaign remained PAUSED.

Ad `823025452795` was paused.

Reason:

It contained the unsupported absolute privacy statement.

Replacement RSA created:

`825513173446`

Replacement wording uses cautious language such as:

- פרטיות ושיח מכבד
- מרחב מכבד לשני בני הזוג

Current replacement state immediately after creation:

- ad status: ENABLED inside the paused campaign
- policy/ad-strength: still pending initial Google review

No campaign spend was enabled.

---

## Current decision

### SEO

No additional Wave 1 content changes are recommended now.

All seven target URLs are indexed.

Allow GSC/GA4 time to accumulate post-change data.

### PPC

Do NOT activate the campaign yet.

Before activation:

1. Mark the real Kesher conversion events as GA4 Key Events in GA4 Admin.
2. Choose a realistic CPC/bidding setup; 0.01 ILS Manual CPC should not be used for launch.
3. Decide whether Search Partners should remain enabled for the first controlled test.
4. Review/remove `סדנת זוגיות באשדוד` unless workshops are intentionally part of this campaign.
5. Wait for the new RSA to complete Google policy review.
6. Then run a small controlled Ashdod-only launch.

---

## Next measurement checkpoints

Recommended:

- Early review: 7–14 days after 2026-09-20
- Strategy review / Wave 2 decision: approximately 4–6 weeks after 2026-09-20

At those checkpoints compare against this file rather than reconstructing the baseline from memory.
