'use client';

import { useState, useEffect } from 'react';

const DRIVE_FOLDER_URL = 'https://drive.google.com/drive/folders/1lqEobVpZEWROgu_NXUdg_j7xBup1YZMO';

type Player = {
  id: number;
  player_id: string;
  name: string;
  season_year: number;
  team_id?: string;
};

type Team = {
  id: number;
  team_id: string;
  name: string;
  abbrev?: string;
};

const AIR_FORCE_TEAM_ID = '730205440';

export default function PitchingPage() {
  // Report generator state
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
  const [players, setPlayers] = useState<Player[]>([]);
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [season, setSeason] = useState(2025);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [generating, setGenerating] = useState(false);
  const [reportMessage, setReportMessage] = useState<string | null>(null);
  const [pdfFilename, setPdfFilename] = useState<string | null>(null);

  // Fetch teams on mount
  useEffect(() => {
    async function fetchTeams() {
      try {
        const response = await fetch('/api/teams');
        const data = await response.json();
        const teamList = data.teams || [];
        // Sort teams with Air Force first
        const sortedTeams = [...teamList].sort((a, b) => {
          if (a.team_id === AIR_FORCE_TEAM_ID) return -1;
          if (b.team_id === AIR_FORCE_TEAM_ID) return 1;
          return a.name.localeCompare(b.name);
        });
        setTeams(sortedTeams);
        // Default to Air Force
        const airForce = sortedTeams.find((t: Team) => t.team_id === AIR_FORCE_TEAM_ID);
        if (airForce) setSelectedTeam(airForce);
      } catch (error) {
        console.error('Failed to fetch teams:', error);
      }
    }
    fetchTeams();
  }, []);

  // Fetch players when team changes
  useEffect(() => {
    async function fetchPlayers() {
      if (!selectedTeam) return;
      try {
        const response = await fetch(`/api/players?teamId=${selectedTeam.team_id}`);
        const data = await response.json();
        setPlayers(data.players || []);
        setSelectedPlayer(null);
      } catch (error) {
        console.error('Failed to fetch players:', error);
      }
    }
    fetchPlayers();
  }, [selectedTeam]);

  // Set end date to start date when start date changes
  useEffect(() => {
    if (startDate && !endDate) {
      setEndDate(startDate);
    }
  }, [startDate, endDate]);

  const handleGenerateReport = async () => {
    if (!selectedPlayer || !startDate || !endDate) {
      setReportMessage('Please select a player and date range');
      return;
    }

    setGenerating(true);
    setReportMessage(null);
    setPdfFilename(null);

    try {
      const response = await fetch('/api/generate-pitching-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          playerName: selectedPlayer.name,
          playerId: selectedPlayer.player_id,
          season,
          startDate,
          endDate,
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

  const handleOpenFolder = () => {
    window.open(DRIVE_FOLDER_URL, '_blank', 'noopener,noreferrer');
  };

  return (
    <main>
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '24px' }}>
        <button className="cta" onClick={handleOpenFolder} style={{ minWidth: '200px' }}>
          Go To Pitching Charts
        </button>
      </div>

      <section className="panel">
        <h2 style={{ textAlign: 'center' }}>Pitching Report Generator</h2>

        <div style={{ display: 'grid', gap: '14px', marginTop: '20px', maxWidth: '450px', margin: '20px auto 0' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>Team</label>
              <select
                value={String(selectedTeam?.id ?? '')}
                onChange={(e) => {
                  const team = teams.find(t => t.id === Number(e.target.value));
                  setSelectedTeam(team || null);
                }}
              >
                {teams.map((team) => (
                  <option key={team.id} value={String(team.id)}>
                    {team.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label>Player</label>
              <select
                value={selectedPlayer?.id || ''}
                onChange={(e) => {
                  const player = players.find(p => p.id === Number(e.target.value));
                  setSelectedPlayer(player || null);
                }}
                disabled={!selectedTeam}
              >
                <option value="">Select Player</option>
                {players.map((player) => (
                  <option key={player.id} value={player.id}>
                    {player.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
            <div>
              <label>Season</label>
              <select
                value={season}
                onChange={(e) => setSeason(Number(e.target.value))}
              >
                <option value="2025">2025</option>
                <option value="2024">2024</option>
                <option value="2023">2023</option>
              </select>
            </div>

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
            disabled={generating || !selectedPlayer || !startDate || !endDate}
            style={{ marginTop: '8px' }}
          >
            {generating ? 'Generating Report... Touch Grass' : 'Generate Report'}
          </button>

          {reportMessage && (
            <div className="note" style={{ marginTop: '8px', textAlign: 'center' }}>
              {reportMessage}
            </div>
          )}
        </div>

        {pdfFilename && (
          <div style={{ marginTop: '24px' }}>
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
              title="Pitching Report Preview"
              className="sheet-frame"
              style={{ height: '600px' }}
            />
          </div>
        )}
      </section>
    </main>
  );
}
