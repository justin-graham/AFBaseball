import { NextResponse } from 'next/server';
import { getSupabaseClient } from '../../../lib/supabase';

const TRUMEDIA_USERNAME = process.env.TRUMEDIA_USERNAME || 'Justin.Graham@afacademy.af.edu';
const TRUMEDIA_SITENAME = process.env.TRUMEDIA_SITENAME || 'airforce-ncaabaseball';
const TRUMEDIA_MASTER_TOKEN = process.env.TRUMEDIA_MASTER_TOKEN || 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiZjZlZWEwYzViZmUwZTY4ZmEwZDUyMGQyMDU2NTNmYzciLCJpYXQiOjE3NTc0MjE1NjF9.p940yyxhsJZp_gZFX-4Y4U48WqZrvbylDyY8Oj2u9q0';

async function getTruMediaToken() {
  const response = await fetch('https://api.trumedianetworks.com/v1/siteadmin/api/createTempPBToken', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: TRUMEDIA_USERNAME,
      sitename: TRUMEDIA_SITENAME,
      token: TRUMEDIA_MASTER_TOKEN,
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to get TruMedia token');
  }

  const data = await response.json();
  return data.pbTempToken;
}

export async function POST() {
  try {
    const supabase = getSupabaseClient();
    if (!supabase) {
      return NextResponse.json({ error: 'Supabase not configured' }, { status: 500 });
    }

    const token = await getTruMediaToken();
    const apiUrl = `https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/AllTeams.csv?seasonYear=2025&token=${token}`;

    const response = await fetch(apiUrl);
    if (!response.ok) {
      throw new Error(`TruMedia API error: ${response.status}`);
    }

    const csvText = await response.text();
    const lines = csvText.trim().split('\n');
    const headers = lines[0].split(',');

    console.log('CSV headers:', headers);

    const teamIdIndex = headers.findIndex(h => h.toLowerCase().includes('teamid'));
    const nameIndex = headers.findIndex(h => h.toLowerCase() === 'fullname' || h.toLowerCase() === 'teamname');
    const abbrevIndex = headers.findIndex(h => h.toLowerCase() === 'abbrevname');

    console.log('Column indices - teamId:', teamIdIndex, 'name:', nameIndex, 'abbrev:', abbrevIndex);

    const teams = [];
    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(',');
      const teamId = values[teamIdIndex]?.trim();
      const name = values[nameIndex]?.trim();
      const abbrev = values[abbrevIndex]?.trim();

      if (teamId && name) {
        teams.push({
          team_id: teamId,
          name: name,
          abbrev: abbrev,
          updated_at: new Date().toISOString(),
        });
      }
    }

    console.log(`Parsed ${teams.length} teams from CSV`);
    console.log('Sample team:', teams[0]);

    const { data, error } = await supabase.from('teams').upsert(teams, { onConflict: 'team_id' });

    if (error) {
      console.error('Supabase upsert error:', error);
      throw new Error(`Supabase error: ${error.message}`);
    }

    console.log(`✓ Successfully synced ${teams.length} teams to database`);
    return NextResponse.json({ count: teams.length });
  } catch (error) {
    console.error('Teams sync error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to sync teams' },
      { status: 500 }
    );
  }
}
