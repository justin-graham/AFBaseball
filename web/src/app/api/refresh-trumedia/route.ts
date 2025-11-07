import { NextResponse } from 'next/server';

const message =
  'Connect this endpoint to a Supabase Function that refreshes TruMedia data. This stub exists to keep the UI working.';

export async function GET() {
  return NextResponse.json({ status: 'not-implemented', message }, { status: 501 });
}

export async function POST() {
  return GET();
}
