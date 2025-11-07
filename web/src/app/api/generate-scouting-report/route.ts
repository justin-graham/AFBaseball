import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execAsync = promisify(exec);
const CLOUD_RUN_URL = process.env.SCOUTING_REPORT_SERVICE_URL;

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { teamName, teamId } = body;

    // Validate inputs
    if (!teamName || !teamId) {
      return NextResponse.json(
        { error: 'Missing required fields: teamName, teamId' },
        { status: 400 }
      );
    }

    // Choose execution mode: local Python or Cloud Run
    let result;
    if (CLOUD_RUN_URL) {
      // Production: Call Cloud Run service
      result = await callCloudRun({ teamName, teamId });
    } else {
      // Local: Execute Python script directly
      result = await callPythonScript({ teamName, teamId });
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
      pitcherCount: result.pitcherCount || 0,
    });

  } catch (error) {
    console.error('Scouting report generation error:', error);

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
      { error: 'Failed to generate scouting report' },
      { status: 500 }
    );
  }
}

async function callCloudRun(params: any) {
  const { teamName, teamId } = params;
  const serviceUrl = `${CLOUD_RUN_URL}/generate`;
  console.log(`Calling Cloud Run service: ${serviceUrl}`);

  const response = await fetch(serviceUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ teamName, teamId }),
    signal: AbortSignal.timeout(300000), // 5 minute timeout
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error(errorData.error || `Service error: ${response.statusText}`);
  }

  return await response.json();
}

async function callPythonScript(params: any) {
  const { teamName, teamId } = params;

  // Path to Python script (from web/src/app/api/... go up to project root)
  const scriptPath = path.join(process.cwd(), '../../scouting_report_gen.py');

  console.log(`Executing Python script locally: ${scriptPath}`);

  // Build command with environment variables
  const env = {
    ...process.env,
    TRUMEDIA_USERNAME: process.env.TRUMEDIA_USERNAME || 'Justin.Graham@afacademy.af.edu',
    TRUMEDIA_SITENAME: process.env.TRUMEDIA_SITENAME || 'airforce-ncaabaseball',
    TRUMEDIA_MASTER_TOKEN: process.env.TRUMEDIA_MASTER_TOKEN,
  };

  const cmd = `python3 "${scriptPath}" --team-name "${teamName}" --team-id "${teamId}" --output-dir "${process.cwd()}"`;

  try {
    const { stdout, stderr } = await execAsync(cmd, {
      env,
      cwd: path.join(process.cwd(), '../..'), // Run from project root
      maxBuffer: 10 * 1024 * 1024, // 10MB buffer
      timeout: 300000, // 5 minute timeout
    });

    // Always log Python output for debugging
    console.log('=== Python Script Output ===');
    console.log(stdout);
    console.log('=== End Python Output ===');

    if (stderr) {
      console.warn('Python stderr:', stderr);
    }

    // Extract JSON result from stdout
    if (stdout.includes('__RESULT_JSON__:')) {
      const jsonStr = stdout.split('__RESULT_JSON__:')[1].split(':__END_RESULT__')[0];
      return JSON.parse(jsonStr);
    } else {
      console.error('ERROR: No valid result returned from Python script');
      throw new Error('No valid result returned from Python script');
    }
  } catch (error) {
    console.error('Python execution error:', error);
    throw error;
  }
}
