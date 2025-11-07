'use client';

import { useState } from 'react';
import type { TeamRow } from '../../lib/data';

type ScoutingReportFormProps = {
  teams: TeamRow[];
};

export default function ScoutingReportForm({ teams }: ScoutingReportFormProps) {
  const [selectedTeam, setSelectedTeam] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [pdfFilename, setPdfFilename] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedTeam) {
      setError('Please select a team');
      return;
    }

    const team = teams.find(t => t.team_id === selectedTeam);
    if (!team) {
      setError('Invalid team selection');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch('/api/generate-scouting-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          teamName: team.name,
          teamId: team.team_id,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to generate report');
      }

      setSuccess(`Report generated successfully! ${data.pitcherCount || 0} pitcher(s) included.`);

      // Store PDF filename for preview
      if (data.pdfPath) {
        setPdfFilename(data.pdfPath);
      }

    } catch (err) {
      console.error('Report generation error:', err);
      setError(err instanceof Error ? err.message : 'Failed to generate report');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <h2 style={{ textAlign: 'center', marginBottom: '24px' }}>Opponent Pitching Analysis</h2>

      <form onSubmit={handleSubmit} style={{ maxWidth: '500px', width: '100%', marginTop: '20px' }}>
        <div style={{ marginBottom: '16px' }}>
          <label htmlFor="team-select" style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
            Select Opponent Team:
          </label>
          <select
            id="team-select"
            value={selectedTeam}
            onChange={(e) => setSelectedTeam(e.target.value)}
            disabled={loading}
            style={{
              width: '100%',
              padding: '10px',
              fontSize: '14px',
              borderRadius: '4px',
              border: '1px solid #ccc',
              backgroundColor: loading ? '#f5f5f5' : 'white',
            }}
          >
            <option value="">-- Select a team --</option>
            {teams.map((team) => (
              <option key={team.team_id} value={team.team_id}>
                {team.name}
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '8px' }}>
          <button
            type="submit"
            disabled={loading || !selectedTeam}
            className="cta"
            style={{
              opacity: loading || !selectedTeam ? 0.5 : 1,
              cursor: loading || !selectedTeam ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Generating Report...' : 'Generate Report'}
          </button>
        </div>

        {loading && (
          <div style={{ marginTop: '16px', color: '#666', fontSize: '14px', textAlign: 'center' }}>
            ⏳ This may take 2-5 minutes. Please wait...
          </div>
        )}

        {error && (
          <div style={{ marginTop: '16px', padding: '12px', backgroundColor: '#fee', border: '1px solid #fcc', borderRadius: '4px', color: '#c00', textAlign: 'center' }}>
            ❌ {error}
          </div>
        )}

        {success && (
          <div style={{ marginTop: '16px', padding: '12px', backgroundColor: '#efe', border: '1px solid #cfc', borderRadius: '4px', color: '#070', textAlign: 'center' }}>
            ✅ {success}
          </div>
        )}
      </form>

      {pdfFilename && (
        <div style={{ marginTop: '32px', width: '100%', alignSelf: 'stretch' }}>
          <h3 style={{ marginBottom: '16px' }}>Report Preview</h3>
          <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap', justifyContent: 'center' }}>
            <a
              href={`/api/download-pdf?filename=${encodeURIComponent(pdfFilename)}`}
              download
              className="cta"
            >
              Download PDF
            </a>
            <a
              href={`/api/download-pdf?filename=${encodeURIComponent(pdfFilename)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="cta"
              style={{ background: 'var(--blue)' }}
            >
              Open in New Tab
            </a>
          </div>

          <iframe
            src={`/api/download-pdf?filename=${encodeURIComponent(pdfFilename)}`}
            title="Scouting Report Preview"
            className="sheet-frame"
            style={{
              width: '98%',
              maxWidth: '1200px',
              height: '600px',
              border: '1px solid #ddd',
              borderRadius: '6px',
              margin: '0 auto',
              display: 'block'
            }}
          />
        </div>
      )}
    </section>
  );
}
