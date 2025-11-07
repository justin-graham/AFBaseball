import { NextResponse } from 'next/server';
import { getSupabaseClient } from '../../../lib/supabase';

export async function GET(request: Request) {
  try {
    const supabase = getSupabaseClient();
    if (!supabase) {
      return NextResponse.json(
        { error: 'Supabase not configured' },
        { status: 500 }
      );
    }

    const { searchParams } = new URL(request.url);
    const teamId = searchParams.get('teamId');

    let query = supabase
      .from('players')
      .select('id, player_id, name, season_year, team_id')
      .order('name', { ascending: true });

    if (teamId) {
      query = query.eq('team_id', teamId);
    }

    const { data, error } = await query;

    if (error) {
      throw new Error(`Supabase error: ${error.message}`);
    }

    return NextResponse.json({ players: data || [] });
  } catch (error) {
    console.error('Players fetch error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch players' },
      { status: 500 }
    );
  }
}
