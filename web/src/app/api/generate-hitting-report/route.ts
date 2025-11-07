import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execAsync = promisify(exec);
const CLOUD_RUN_URL = process.env.HITTING_REPORT_SERVICE_URL;

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { playerName, playerId, season, startDate, endDate } = body;

    // Validate inputs
    if (!playerName || !playerId || !season || !startDate || !endDate) {
      return NextResponse.json(
        { error: 'Missing required fields: playerName, playerId, season, startDate, endDate' },
        { status: 400 }
      );
    }

    // Validate dates
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    if (!dateRegex.test(startDate) || !dateRegex.test(endDate)) {
      return NextResponse.json(
        { error: 'Invalid date format. Use YYYY-MM-DD' },
        { status: 400 }
      );
    }

    if (new Date(startDate) > new Date(endDate)) {
      return NextResponse.json(
        { error: 'Start date must be before or equal to end date' },
        { status: 400 }
      );
    }

    // Choose execution mode: local Python or Cloud Run
    let result;
    if (CLOUD_RUN_URL) {
      // Production: Call Cloud Run service
      result = await callCloudRun({ playerName, playerId, season, startDate, endDate });
    } else {
      // Local: Execute Python script directly
      result = await callPythonScript({ playerName, playerId, season, startDate, endDate });
    }

    if (!result.success) {
      return NextResponse.json(
        { error: result.error || 'Report generation failed' },
        { status: 500 }
      );
    }

    // Return PDF path for download
    return NextResponse.json({
      success: true,
      pdfPath: result.pdfPath,
    });

  } catch (error) {
    console.error('Report generation error:', error);

    if (error instanceof Error) {
      if (error.name === 'AbortError') {
        return NextResponse.json(
          { error: 'Report generation timed out. This may take up to 5 minutes.' },
          { status: 504 }
        );
      }
      return NextResponse.json(
        { error: error.message },
        { status: 500 }
      );
    }

    return NextResponse.json(
      { error: 'Failed to generate report' },
      { status: 500 }
    );
  }
}

async function callCloudRun(params: any) {
  const { playerName, playerId, season, startDate, endDate } = params;
  const serviceUrl = `${CLOUD_RUN_URL}/generate`;
  console.log(`Calling Cloud Run service: ${serviceUrl}`);

  const response = await fetch(serviceUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      playerName,
      playerId,
      season: Number(season),
      startDate,
      endDate,
    }),
    signal: AbortSignal.timeout(300000),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error(errorData.error || `Service error: ${response.statusText}`);
  }

  return await response.json();
}

async function callPythonScript(params: any) {
  const { playerName, playerId, season, startDate, endDate } = params;

  // Path to Python script (from web/src/app/api/... go up to project root)
  const scriptPath = path.join(process.cwd(), '../../hitter_test.py');

  console.log(`Executing Python script locally: ${scriptPath}`);

  // Build command with environment variables
  const env = {
    ...process.env,
    TRUMEDIA_USERNAME: process.env.TRUMEDIA_USERNAME || 'Justin.Graham@afacademy.af.edu',
    TRUMEDIA_SITENAME: process.env.TRUMEDIA_SITENAME || 'airforce-ncaabaseball',
    TRUMEDIA_MASTER_TOKEN: process.env.TRUMEDIA_MASTER_TOKEN,
  };

  const cmd = `python3 "${scriptPath}" --player-name "${playerName}" --player-id "${playerId}" --season ${season} --start-date "${startDate}" --end-date "${endDate}" --output-dir "${process.cwd()}"`;

  try {
    const { stdout, stderr } = await execAsync(cmd, {
      env,
      cwd: path.join(process.cwd(), '../..'), // Run from project root
      maxBuffer: 10 * 1024 * 1024, // 10MB buffer
      timeout: 300000, // 5 minute timeout
    });

    if (stderr) {
      console.warn('Python stderr:', stderr);
    }

    // Extract JSON result from stdout
    if (stdout.includes('__RESULT_JSON__:')) {
      const jsonStr = stdout.split('__RESULT_JSON__:')[1].split(':__END_RESULT__')[0];
      return JSON.parse(jsonStr);
    } else {
      console.error('Python stdout:', stdout);
      throw new Error('No valid result returned from Python script');
    }
  } catch (error) {
    console.error('Python execution error:', error);
    throw error;
  }
}
