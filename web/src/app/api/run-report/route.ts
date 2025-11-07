import { NextResponse } from 'next/server';

const message =
  'Wire this endpoint to a Supabase Edge Function or hosted script that builds reports. Replace this stub when ready.';

export async function GET() {
  return NextResponse.json({ status: 'not-implemented', message }, { status: 501 });
}

export async function POST() {
  return GET();
}
