import fs from 'node:fs';
import path from 'node:path';

const API_VERSION = process.env.GOOGLE_ADS_API_VERSION || 'v25';
const CUSTOMER_ID = (process.env.GOOGLE_ADS_CUSTOMER_ID || '').replace(/-/g, '');
const LOGIN_CUSTOMER_ID = (process.env.GOOGLE_ADS_LOGIN_CUSTOMER_ID || '').replace(/-/g, '');
const DEVELOPER_TOKEN = process.env.GOOGLE_ADS_DEVELOPER_TOKEN || '';
const CLIENT_ID = process.env.GOOGLE_ADS_CLIENT_ID || '';
const CLIENT_SECRET = process.env.GOOGLE_ADS_CLIENT_SECRET || '';
const REFRESH_TOKEN = process.env.GOOGLE_ADS_REFRESH_TOKEN || '';

const required = {
  GOOGLE_ADS_CUSTOMER_ID: CUSTOMER_ID,
  GOOGLE_ADS_DEVELOPER_TOKEN: DEVELOPER_TOKEN,
  GOOGLE_ADS_CLIENT_ID: CLIENT_ID,
  GOOGLE_ADS_CLIENT_SECRET: CLIENT_SECRET,
  GOOGLE_ADS_REFRESH_TOKEN: REFRESH_TOKEN,
};

const missing = Object.entries(required).filter(([, value]) => !value).map(([key]) => key);
if (missing.length) {
  console.error(`Missing required Google Ads configuration: ${missing.join(', ')}`);
  process.exit(2);
}

async function getAccessToken() {
  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    client_id: CLIENT_ID,
    client_secret: CLIENT_SECRET,
    refresh_token: REFRESH_TOKEN,
  });

  const response = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok || !payload.access_token) {
    throw new Error(`OAuth token refresh failed (${response.status}): ${payload.error_description || payload.error || 'unknown error'}`);
  }
  return payload.access_token;
}

async function searchStream(accessToken, query) {
  const headers = {
    authorization: `Bearer ${accessToken}`,
    'developer-token': DEVELOPER_TOKEN,
    'content-type': 'application/json',
  };
  if (LOGIN_CUSTOMER_ID) headers['login-customer-id'] = LOGIN_CUSTOMER_ID;

  const url = `https://googleads.googleapis.com/${API_VERSION}/customers/${CUSTOMER_ID}/googleAds:searchStream`;
  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({ query }),
  });

  const text = await response.text();
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    payload = text;
  }

  if (!response.ok) {
    const apiMessage = payload?.error?.message || payload?.[0]?.error?.message || String(payload).slice(0, 1000);
    throw new Error(`Google Ads API request failed (${response.status}): ${apiMessage}`);
  }

  const batches = Array.isArray(payload) ? payload : [payload];
  return batches.flatMap((batch) => batch?.results || []);
}

function number(value) {
  const n = Number(value || 0);
  return Number.isFinite(n) ? n : 0;
}

function campaignSummary(rows) {
  return rows.reduce((acc, row) => {
    const metrics = row.metrics || {};
    acc.impressions += number(metrics.impressions);
    acc.clicks += number(metrics.clicks);
    acc.costMicros += number(metrics.costMicros);
    acc.conversions += number(metrics.conversions);
    acc.conversionsValue += number(metrics.conversionsValue);
    return acc;
  }, { impressions: 0, clicks: 0, costMicros: 0, conversions: 0, conversionsValue: 0 });
}

const queries = {
  customer: `
    SELECT
      customer.id,
      customer.descriptive_name,
      customer.currency_code,
      customer.time_zone
    FROM customer
    LIMIT 1
  `,
  campaigns: `
    SELECT
      campaign.id,
      campaign.name,
      campaign.status,
      campaign.advertising_channel_type,
      metrics.impressions,
      metrics.clicks,
      metrics.cost_micros,
      metrics.conversions,
      metrics.conversions_value
    FROM campaign
    WHERE segments.date DURING LAST_30_DAYS
    ORDER BY metrics.cost_micros DESC
  `,
  ads: `
    SELECT
      campaign.name,
      ad_group.name,
      ad_group_ad.status,
      ad_group_ad.ad.id,
      ad_group_ad.ad.type,
      ad_group_ad.ad.final_urls,
      ad_group_ad.ad.responsive_search_ad.headlines,
      ad_group_ad.ad.responsive_search_ad.descriptions,
      metrics.impressions,
      metrics.clicks,
      metrics.cost_micros,
      metrics.conversions
    FROM ad_group_ad
    WHERE segments.date DURING LAST_30_DAYS
    ORDER BY metrics.cost_micros DESC
    LIMIT 200
  `,
  keywords: `
    SELECT
      campaign.name,
      ad_group.name,
      ad_group_criterion.status,
      ad_group_criterion.keyword.text,
      ad_group_criterion.keyword.match_type,
      metrics.impressions,
      metrics.clicks,
      metrics.cost_micros,
      metrics.conversions
    FROM keyword_view
    WHERE segments.date DURING LAST_30_DAYS
    ORDER BY metrics.cost_micros DESC
    LIMIT 300
  `,
  searchTerms: `
    SELECT
      campaign.name,
      ad_group.name,
      search_term_view.search_term,
      search_term_view.status,
      metrics.impressions,
      metrics.clicks,
      metrics.cost_micros,
      metrics.conversions
    FROM search_term_view
    WHERE segments.date DURING LAST_30_DAYS
      AND metrics.impressions > 0
    ORDER BY metrics.cost_micros DESC
    LIMIT 300
  `,
  conversionActions: `
    SELECT
      conversion_action.id,
      conversion_action.name,
      conversion_action.status,
      conversion_action.type,
      conversion_action.category,
      conversion_action.primary_for_goal
    FROM conversion_action
    WHERE conversion_action.status != 'REMOVED'
    ORDER BY conversion_action.name
  `,
};

async function main() {
  console.log(`Starting read-only Google Ads API audit with ${API_VERSION}.`);
  const accessToken = await getAccessToken();
  const results = {};
  const errors = {};

  for (const [name, query] of Object.entries(queries)) {
    try {
      results[name] = await searchStream(accessToken, query);
      console.log(`${name}: ${results[name].length} rows`);
    } catch (error) {
      errors[name] = error.message;
      console.error(`${name}: ${error.message}`);
    }
  }

  if (!results.customer?.length) {
    throw new Error(`Could not read the Google Ads customer. ${errors.customer || ''}`.trim());
  }

  const totals = campaignSummary(results.campaigns || []);
  const summary = {
    impressions: totals.impressions,
    clicks: totals.clicks,
    ctr: totals.impressions ? totals.clicks / totals.impressions : 0,
    cost: totals.costMicros / 1_000_000,
    conversions: totals.conversions,
    conversionRate: totals.clicks ? totals.conversions / totals.clicks : 0,
    cpa: totals.conversions ? (totals.costMicros / 1_000_000) / totals.conversions : null,
    conversionsValue: totals.conversionsValue,
  };

  const report = {
    generatedAt: new Date().toISOString(),
    apiVersion: API_VERSION,
    period: 'LAST_30_DAYS',
    customer: results.customer[0]?.customer || null,
    summary,
    errors,
    data: results,
  };

  const outputDir = path.resolve('output');
  fs.mkdirSync(outputDir, { recursive: true });
  const outputPath = path.join(outputDir, 'google-ads-audit.json');
  fs.writeFileSync(outputPath, JSON.stringify(report, null, 2));

  console.log('Audit complete.');
  console.log(JSON.stringify(summary, null, 2));
  console.log(`Report written to ${outputPath}`);
}

main().catch((error) => {
  console.error(`Google Ads audit failed: ${error.message}`);
  process.exit(1);
});
