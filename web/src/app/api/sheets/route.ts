import { NextResponse } from 'next/server';
import { fetchSheets } from '../../../lib/data';

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const game_type = searchParams.get('game_type');

    const filters = game_type ? { game_type } : {};
    const result = await fetchSheets(filters);

    return NextResponse.json(result);
  } catch (error) {
    console.error('Failed to fetch sheets:', error);
    return NextResponse.json(
      { rows: [], message: 'Failed to fetch sheets' },
      { status: 500 }
    );
  }
}
