-- Create players table for pitching report generator
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS players (
  id SERIAL PRIMARY KEY,
  player_id TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  team_id TEXT,
  season_year INT,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_players_name ON players(name);
CREATE INDEX IF NOT EXISTS idx_players_player_id ON players(player_id);

-- Enable Row Level Security (optional, adjust as needed)
ALTER TABLE players ENABLE ROW LEVEL SECURITY;

-- Allow public read access (adjust based on your security requirements)
CREATE POLICY "Allow public read access" ON players
  FOR SELECT USING (true);

-- Allow service role to insert/update
CREATE POLICY "Allow service role full access" ON players
  FOR ALL USING (auth.role() = 'service_role');
