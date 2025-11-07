-- Create teams table
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS teams (
  id SERIAL PRIMARY KEY,
  team_id TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  abbrev TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_teams_team_id ON teams(team_id);
CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(name);

ALTER TABLE teams ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access" ON teams
  FOR SELECT USING (true);

CREATE POLICY "Allow public insert" ON teams
  FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow public update" ON teams
  FOR UPDATE USING (true);
