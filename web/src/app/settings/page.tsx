'use client';

import { useState } from 'react';

export default function SettingsPage() {
  const [message, setMessage] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncingTeams, setSyncingTeams] = useState(false);

  const handleSyncTeams = async () => {
    setSyncingTeams(true);
    setMessage(null);

    try {
      const response = await fetch('/api/sync-teams', { method: 'POST' });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to sync teams');
      }

      setMessage(`✓ Successfully synced ${data.count} teams from TruMedia`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Failed to sync teams');
    } finally {
      setSyncingTeams(false);
    }
  };

  const handleSyncRoster = async () => {
    setSyncing(true);
    setMessage(null);

    try {
      const response = await fetch('/api/sync-roster', { method: 'POST' });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to sync roster');
      }

      setMessage(`✓ Successfully synced ${data.count} players from TruMedia`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Failed to sync roster');
    } finally {
      setSyncing(false);
    }
  };

  return (
    <main>
      <section className="panel">
        <div className="tag">Settings</div>
        <h1>Settings</h1>
        <p>Manage system configuration and data synchronization.</p>
      </section>

      <section className="panel">
        <div className="tag">Teams</div>
        <h2>TruMedia Teams Sync</h2>
        <p>Sync all NCAA baseball teams from TruMedia to enable team filtering.</p>
        <button className="cta" onClick={handleSyncTeams} disabled={syncingTeams}>
          {syncingTeams ? 'Syncing...' : 'Sync Teams'}
        </button>
      </section>

      <section className="panel">
        <div className="tag">Player Roster</div>
        <h2>TruMedia Player Sync</h2>
        <p>Sync all D1 NCAA baseball players from TruMedia 2025 regular season to populate the player database for pitching reports.</p>
        <p style={{ fontSize: '14px', color: '#666', marginTop: '8px' }}>
          Uses <code>PlayerTotals.csv</code> endpoint filtered for D1 baseball only
        </p>
        <button className="cta" onClick={handleSyncRoster} disabled={syncing}>
          {syncing ? 'Syncing...' : 'Sync D1 Players'}
        </button>
        {message && (
          <div className="note" style={{ marginTop: '12px' }}>
            {message}
          </div>
        )}
      </section>
    </main>
  );
}
