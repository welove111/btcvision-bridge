-- BTCVision Donation Bridge — Supabase Tables
-- شغّل هذا في Supabase SQL Editor مرة واحدة

-- جدول الموافقات
CREATE TABLE IF NOT EXISTS donation_consents (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  request_id    TEXT NOT NULL,
  session_id    TEXT NOT NULL,
  coin          TEXT NOT NULL DEFAULT 'BTC',
  address       TEXT NOT NULL,
  amount_sats   INTEGER NOT NULL DEFAULT 21000,
  consent_token TEXT,
  status        TEXT NOT NULL DEFAULT 'granted',
  granted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- جدول التنفيذات
CREATE TABLE IF NOT EXISTS donation_executions (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  request_id    TEXT NOT NULL,
  session_id    TEXT NOT NULL,
  coin          TEXT NOT NULL DEFAULT 'BTC',
  address       TEXT NOT NULL,
  amount_sats   INTEGER NOT NULL,
  tx_id         TEXT,
  executed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index للبحث السريع
CREATE INDEX IF NOT EXISTS idx_consents_session    ON donation_consents(session_id);
CREATE INDEX IF NOT EXISTS idx_consents_coin       ON donation_consents(coin);
CREATE INDEX IF NOT EXISTS idx_executions_session  ON donation_executions(session_id);
CREATE INDEX IF NOT EXISTS idx_executions_coin     ON donation_executions(coin);

-- RLS — السماح بالقراءة والكتابة عبر anon key
ALTER TABLE donation_consents   ENABLE ROW LEVEL SECURITY;
ALTER TABLE donation_executions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_insert_consents"   ON donation_consents   FOR INSERT WITH CHECK (true);
CREATE POLICY "allow_select_consents"   ON donation_consents   FOR SELECT USING (true);
CREATE POLICY "allow_insert_executions" ON donation_executions FOR INSERT WITH CHECK (true);
CREATE POLICY "allow_select_executions" ON donation_executions FOR SELECT USING (true);
