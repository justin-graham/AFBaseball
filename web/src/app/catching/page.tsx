import { fetchSheets } from '../../lib/data';

export default async function CatchingPage() {
  const { rows, message } = await fetchSheets({ game_type: 'catching' });
  const live = rows.find((row) => row.embed_url);

  return (
    <main>
      <section className="panel">
        <div className="tag">Catching</div>
        <h1>Catcher Command Center</h1>
        <p>Framing grades, block recovery metrics, and throwing charts all stay inside one rolling sheet.</p>
      </section>

      {message ? <div className="note">{message}</div> : null}

      {rows.length ? (
        <section className="panel">
          <div className="tag">Recent Logs</div>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '12px' }}>
            {rows.map((sheet) => (
              <li key={sheet.id}>
                <strong>{sheet.title ?? `Sheet ${sheet.id}`}</strong>
                <br />
                <small>{sheet.updated_at ? new Date(sheet.updated_at).toLocaleString() : '—'}</small>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {live?.embed_url ? (
        <section className="panel">
          <div className="tag">Live Sheet</div>
          <iframe
            src={live.embed_url ?? undefined}
            title={live.title ?? 'Catching Sheet'}
            className="sheet-frame"
          />
        </section>
      ) : null}
    </main>
  );
}
