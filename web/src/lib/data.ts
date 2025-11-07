import { getSupabaseClient } from './supabase';

export type SheetRow = {
  id: number | string;
  title: string | null;
  embed_url: string | null;
  game_type?: string | null;
  opponent?: string | null;
  updated_at: string | null;
};

type SheetFilters = {
  game_type?: string;
};

export async function fetchSheets(filters: SheetFilters = {}) {
  const client = getSupabaseClient();
  if (!client) {
    return {
      rows: [] as SheetRow[],
      message:
        'Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY to .env.local to stream sheet metadata.',
    };
  }

  let query = client
    .from('practice_sheets')
    .select('id,title,embed_url,game_type,opponent,updated_at')
    .order('updated_at', { ascending: false });

  if (filters.game_type) {
    query = query.eq('game_type', filters.game_type);
  }

  const { data, error } = await query;

  if (error) {
    return {
      rows: [] as SheetRow[],
      message: `Supabase error: ${error.message}. Ensure table practice_sheets exists with expected columns.`,
    };
  }

  return { rows: (data ?? []) as SheetRow[], message: null };
}

export type TeamRow = {
  id: number;
  team_id: string;
  name: string;
  abbrev: string | null;
};

export async function fetchTeams() {
  const client = getSupabaseClient();
  if (!client) {
    return {
      teams: [] as TeamRow[],
      message: 'Supabase not configured',
    };
  }

  const { data, error } = await client
    .from('teams')
    .select('id,team_id,name,abbrev')
    .order('name', { ascending: true });

  if (error) {
    return {
      teams: [] as TeamRow[],
      message: `Supabase error: ${error.message}`,
    };
  }

  return { teams: (data ?? []) as TeamRow[], message: null };
}
