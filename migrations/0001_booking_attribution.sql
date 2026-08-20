CREATE TABLE IF NOT EXISTS booking_attribution (
  calendly_event_uri TEXT PRIMARY KEY,
  calendly_invitee_uri TEXT,
  browser_seen_at TEXT,
  webhook_seen_at TEXT,
  webhook_event_type TEXT,
  status TEXT NOT NULL DEFAULT 'browser_seen',
  service_type TEXT,
  booking_page_path TEXT,
  landing_page_type TEXT,
  variant_id TEXT,
  entry_page_path TEXT,
  utm_source TEXT,
  utm_medium TEXT,
  utm_campaign TEXT,
  utm_term TEXT,
  utm_content TEXT,
  google_click_id_present INTEGER NOT NULL DEFAULT 0 CHECK (google_click_id_present IN (0, 1)),
  rescheduled INTEGER NOT NULL DEFAULT 0 CHECK (rescheduled IN (0, 1)),
  old_invitee_uri TEXT,
  new_invitee_uri TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS booking_attribution_invitee_uri_idx
  ON booking_attribution(calendly_invitee_uri)
  WHERE calendly_invitee_uri IS NOT NULL;

CREATE INDEX IF NOT EXISTS booking_attribution_status_idx
  ON booking_attribution(status);

CREATE INDEX IF NOT EXISTS booking_attribution_campaign_idx
  ON booking_attribution(utm_campaign, utm_source, utm_medium);
