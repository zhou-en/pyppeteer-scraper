CREATE TABLE IF NOT EXISTS scrapers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  is_active BOOLEAN DEFAULT true,
  cron_schedule TEXT DEFAULT '0 9 * * *',
  last_run_at TIMESTAMPTZ,
  last_run_duration_ms INTEGER,
  last_run_status TEXT,
  last_run_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ircc_state (
  id INTEGER PRIMARY KEY DEFAULT 1,
  estimated_time TEXT,
  people_ahead TEXT,
  total_waiting TEXT,
  last_updated TEXT,
  scraped_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scraper_runs (
  id SERIAL PRIMARY KEY,
  scraper_id TEXT REFERENCES scrapers(id),
  started_at TIMESTAMPTZ NOT NULL,
  duration_ms INTEGER,
  status TEXT NOT NULL,
  message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO scrapers (id, name, description, cron_schedule)
VALUES (
  'canada_ircc',
  'Canada IRCC',
  'Monitors IRCC processing times for Provincial Nominees via Express Entry',
  '0 15 * * 1-5'
) ON CONFLICT (id) DO NOTHING;

INSERT INTO scrapers (id, name, description, cron_schedule)
VALUES (
  'home_depo',
  'Home Depot Workshops',
  'Monitors Home Depot kids workshop registrations and auto-registers when seats open',
  '0 * * * *'
) ON CONFLICT (id) DO NOTHING;
