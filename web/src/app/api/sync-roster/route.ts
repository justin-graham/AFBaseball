import { NextResponse } from 'next/server';
import { getSupabaseClient } from '../../../lib/supabase';

const TRUMEDIA_USERNAME = process.env.TRUMEDIA_USERNAME || 'Justin.Graham@afacademy.af.edu';
const TRUMEDIA_SITENAME = process.env.TRUMEDIA_SITENAME || 'airforce-ncaabaseball';
const TRUMEDIA_MASTER_TOKEN = process.env.TRUMEDIA_MASTER_TOKEN || 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiZjZlZWEwYzViZmUwZTY4ZmEwZDUyMGQyMDU2NTNmYzciLCJpYXQiOjE3NTc0MjE1NjF9.p940yyxhsJZp_gZFX-4Y4U48WqZrvbylDyY8Oj2u9q0';
const TEAM_ID = process.env.TRUMEDIA_TEAM_ID || '4806';
const SEASON_YEAR = 2025;

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
      return NextResponse.json(
        { error: 'Supabase not configured. Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY to .env.local' },
        { status: 500 }
      );
    }

    // Get TruMedia token
    const token = await getTruMediaToken();

    // Fetch D1 baseball players from TruMedia using PlayerTotals endpoint
    const columns = encodeURIComponent('[PA]'); // Request minimal stats just to get player list
    // Filter for D1 baseball only
    const filters = encodeURIComponent("(((season.seasonLevel IN ('BBC','SFT') AND team.game.gameLeague = 'D1')))");
    const apiUrl = `https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/PlayerTotals.csv?seasonYear=${SEASON_YEAR}&seasonType=REG&columns=${columns}&filters=${filters}&token=${token}`;

    console.log('Fetching D1 baseball players from TruMedia for season:', SEASON_YEAR);

    const rosterResponse = await fetch(apiUrl);
    if (!rosterResponse.ok) {
      const errorText = await rosterResponse.text();
      console.error('TruMedia API error response:', errorText);
      throw new Error(`TruMedia API error: ${rosterResponse.status} ${rosterResponse.statusText}`);
    }

    const csvText = await rosterResponse.text();
    const lines = csvText.trim().split('\n');

    if (lines.length < 2) {
      console.error('No player data returned from TruMedia');
      return NextResponse.json({ error: 'No players found in roster' }, { status: 404 });
    }

    // Parse CSV - PlayerTotals returns playerId, fullName, etc.
    const headers = lines[0].split(',');
    console.log('CSV headers:', headers);

    // Find column indices
    // TruMedia returns either 'playerId' or 'player.playerId'
    const playerIdIndex = headers.findIndex((h: string) =>
      h.toLowerCase().includes('playerid') && !h.toLowerCase().includes('trackman')
    );
    // TruMedia returns either 'fullName', 'playerName', or 'player.playerName'
    const playerNameIndex = headers.findIndex((h: string) => {
      const lower = h.toLowerCase();
      return lower.includes('playername') || lower.includes('fullname');
    });
    // TruMedia returns 'mostRecentTeamId' or 'team.teamId'
    const teamIdIndex = headers.findIndex((h: string) =>
      h.toLowerCase().includes('teamid') && !h.toLowerCase().includes('trackman')
    );

    if (playerIdIndex === -1 || playerNameIndex === -1) {
      console.error('Missing required columns. Headers:', headers);
      console.error('Looking for playerId at index:', playerIdIndex);
      console.error('Looking for playerName at index:', playerNameIndex);
      console.error('Looking for teamId at index:', teamIdIndex);
      throw new Error('Could not find player ID or name columns in response');
    }

    const players = [];
    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(',');
      const playerId = values[playerIdIndex]?.trim();
      const playerName = values[playerNameIndex]?.trim();
      const teamId = teamIdIndex !== -1 ? values[teamIdIndex]?.trim() : null;

      if (playerId && playerName) {
        players.push({
          player_id: playerId,
          name: playerName,
          team_id: teamId,
          season_year: SEASON_YEAR,
          updated_at: new Date().toISOString(),
        });
      }
    }

    console.log(`Parsed ${players.length} players from TruMedia CSV`);

    // Upsert to Supabase in batches (to handle large datasets)
    const BATCH_SIZE = 1000;
    let successCount = 0;

    for (let i = 0; i < players.length; i += BATCH_SIZE) {
      const batch = players.slice(i, i + BATCH_SIZE);
      console.log(`Upserting batch ${Math.floor(i / BATCH_SIZE) + 1}/${Math.ceil(players.length / BATCH_SIZE)} (${batch.length} players)...`);

      const { error } = await supabase
        .from('players')
        .upsert(batch, { onConflict: 'player_id' });

      if (error) {
        console.error('Supabase upsert error:', error);
        throw new Error(`Supabase error: ${error.message}`);
      }

      successCount += batch.length;
    }

    console.log(`✓ Successfully synced ${successCount} players to database`);
    return NextResponse.json({ count: successCount });
  } catch (error) {
    console.error('Roster sync error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to sync roster' },
      { status: 500 }
    );
  }
}
