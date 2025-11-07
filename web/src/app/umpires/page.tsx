'use client';

import { useState, useEffect } from 'react';

type Team = {
  id: number;
  team_id: string;
  name: string;
  abbrev?: string;
};

type SheetRow = {
  id: number;
  title: string | null;
  embed_url: string | null;
  game_type: string | null;
  opponent: string | null;
  updated_at: string | null;
};

const AIR_FORCE_TEAM_ID = '730205440';

export default function UmpiresPage() {
  // Report generator state
  const [teams, setTeams] = useState<Team[]>([]);
  const [homeTeam, setHomeTeam] = useState<Team | null>(null);
  const [awayTeam, setAwayTeam] = useState<Team | null>(null);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [generating, setGenerating] = useState(false);
  const [reportMessage, setReportMessage] = useState<string | null>(null);
  const [pdfFilename, setPdfFilename] = useState<string | null>(null);

  // Sheet display state
  const [sheets, setSheets] = useState<SheetRow[]>([]);

  // Fetch teams on mount
  useEffect(() => {
    async function fetchTeams() {
      try {
        const response = await fetch('/api/teams');
        const data = await response.json();
        const teamList = data.teams || [];
        // Sort teams with Air Force first
        const sortedTeams = [...teamList].sort((a: Team, b: Team) => {
          if (a.team_id === AIR_FORCE_TEAM_ID) return -1;
          if (b.team_id === AIR_FORCE_TEAM_ID) return 1;
          return a.name.localeCompare(b.name);
        });
        setTeams(sortedTeams);
        // Default to Air Force as home team
        const airForce = sortedTeams.find((t: Team) => t.team_id === AIR_FORCE_TEAM_ID);
        if (airForce) setHomeTeam(airForce);
      } catch (error) {
        console.error('Failed to fetch teams:', error);
      }
    }
    fetchTeams();
  }, []);

  // Fetch sheets on mount
  useEffect(() => {
    async function fetchSheets() {
      try {
        const response = await fetch('/api/sheets?game_type=umpires');
        const data = await response.json();
        setSheets(data.rows || []);
      } catch (error) {
        console.error('Failed to fetch sheets:', error);
      }
    }
    fetchSheets();
  }, []);

  // Set end date to start date when start date changes
  useEffect(() => {
    if (startDate && !endDate) {
      setEndDate(startDate);
    }
  }, [startDate, endDate]);

  const handleGenerateReport = async () => {
    if (!homeTeam || !awayTeam || !startDate || !endDate) {
      setReportMessage('Please select both teams and date range');
      return;
    }

    setGenerating(true);
    setReportMessage(null);
    setPdfFilename(null);

    try {
      const response = await fetch('/api/generate-umpire-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          homeTeamName: homeTeam.name,
          homeTeamId: homeTeam.team_id,
          awayTeamName: awayTeam.name,
          awayTeamId: awayTeam.team_id,
          startDate,
          endDate,
          season: 2025,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to generate report');
      }

      setReportMessage('✓ Report generated!');
      setPdfFilename(data.pdfPath);
    } catch (error) {
      setReportMessage(error instanceof Error ? error.message : 'Failed to generate report');
    } finally {
      setGenerating(false);
    }
  };

  const liveSheet = sheets.find((sheet) => sheet.embed_url);

  return (
    <main>
      <section className="panel">
        <h2 style={{ textAlign: 'center' }}>Umpire Report Generator</h2>

        <div style={{ display: 'grid', gap: '14px', marginTop: '20px', maxWidth: '450px', margin: '20px auto 0' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>Home Team</label>
              <select
                value={String(homeTeam?.id ?? '')}
                onChange={(e) => {
                  const team = teams.find(t => t.id === Number(e.target.value));
                  setHomeTeam(team || null);
                }}
              >
                <option value="">Select home team...</option>
                {teams.map((team) => (
                  <option key={team.id} value={String(team.id)}>
                    {team.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label>Away Team</label>
              <select
                value={String(awayTeam?.id ?? '')}
                onChange={(e) => {
                  const team = teams.find(t => t.id === Number(e.target.value));
                  setAwayTeam(team || null);
                }}
              >
                <option value="">Select away team...</option>
                {teams.map((team) => (
                  <option key={team.id} value={String(team.id)}>
                    {team.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>Start Date</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div>
              <label>End Date</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>

          <button
            className="cta"
            onClick={handleGenerateReport}
            disabled={generating || !homeTeam || !awayTeam || !startDate || !endDate}
            style={{ marginTop: '8px' }}
          >
            {generating ? 'Generating Report... Touch Grass' : 'Generate Report'}
          </button>

          {reportMessage && (
            <div style={{
              padding: '12px',
              backgroundColor: reportMessage.startsWith('✓') ? '#d4edda' : '#f8d7da',
              color: reportMessage.startsWith('✓') ? '#155724' : '#721c24',
              borderRadius: '6px',
              textAlign: 'center',
            }}>
              {reportMessage}
            </div>
          )}

          {pdfFilename && (
            <div style={{ display: 'grid', gap: '12px', marginTop: '12px' }}>
              <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
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
                title="Umpire Report PDF"
                className="sheet-frame"
                style={{ width: '90%', maxWidth: '1200px', height: '600px', border: '1px solid #ddd', borderRadius: '6px', margin: '0 auto', display: 'block' }}
              />
            </div>
          )}
        </div>
      </section>

      {sheets.length > 0 && (
        <section className="panel">
          <div className="tag">Recent Games</div>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '12px' }}>
            {sheets.map((sheet) => (
              <li key={sheet.id}>
                <strong>{sheet.title ?? `Game ${sheet.id}`}</strong>
                <br />
                <small>{sheet.updated_at ? new Date(sheet.updated_at).toLocaleString() : '—'}</small>
              </li>
            ))}
          </ul>
        </section>
      )}

      {liveSheet?.embed_url && (
        <section className="panel">
          <div className="tag">Live Sheet</div>
          <iframe
            src={liveSheet.embed_url ?? undefined}
            title={liveSheet.title ?? 'Umpire Sheet'}
            className="sheet-frame"
          />
        </section>
      )}
    </main>
  );
}
