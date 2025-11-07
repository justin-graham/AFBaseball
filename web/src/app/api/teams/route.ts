import { NextResponse } from 'next/server';
import { getSupabaseClient } from '../../../lib/supabase';

export async function GET() {
  try {
    const supabase = getSupabaseClient();
    if (!supabase) {
      return NextResponse.json({ error: 'Supabase not configured' }, { status: 500 });
    }

    const { data, error } = await supabase
      .from('teams')
      .select('id, team_id, name, abbrev')
      .order('name', { ascending: true });

    if (error) {
      throw new Error(error.message);
    }

    return NextResponse.json({ teams: data || [] });
  } catch (error) {
    console.error('Failed to fetch teams:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch teams' },
      { status: 500 }
    );
  }
}
