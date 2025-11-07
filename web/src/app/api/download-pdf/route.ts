import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const filename = searchParams.get('filename');

    if (!filename) {
      return NextResponse.json({ error: 'Missing filename parameter' }, { status: 400 });
    }

    // PDFs are generated in the current working directory (app/web)
    const fullPath = path.resolve(process.cwd(), filename);

    // Security: Only allow PDFs
    if (!fullPath.endsWith('.pdf')) {
      return NextResponse.json({ error: 'Only PDF files can be downloaded' }, { status: 400 });
    }

    // Check if file exists
    if (!fs.existsSync(fullPath)) {
      console.error('PDF not found:', fullPath);
      return NextResponse.json({ error: 'PDF file not found' }, { status: 404 });
    }

    // Read PDF file
    const pdfBuffer = fs.readFileSync(fullPath);

    // Return PDF for inline display (works in iframe and as download)
    return new NextResponse(pdfBuffer, {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': `inline; filename="${path.basename(fullPath)}"`,
        'Content-Length': pdfBuffer.length.toString(),
      },
    });

  } catch (error) {
    console.error('PDF download error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to download PDF' },
      { status: 500 }
    );
  }
}
