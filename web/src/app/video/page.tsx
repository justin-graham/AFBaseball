import Link from 'next/link';
import { getSupabaseClient } from '../../lib/supabase';

type ClipRow = {
  id: string | number;
  title?: string | null;
  share_url?: string | null;
  duration_ms?: number | null;
  tags?: string[] | null;
};

async function loadClips(): Promise<{ clips: ClipRow[]; message: string | null }> {
  const client = getSupabaseClient();
  if (!client) {
    return {
      clips: [],
      message: 'Add Supabase environment keys to stream clip metadata.',
    };
  }

  const { data, error } = await client
    .from('video_assets')
    .select('id,title,share_url,duration_ms,tags')
    .order('updated_at', { ascending: false })
    .limit(12);

  if (error) {
    return {
      clips: [],
      message:
        'Create Supabase table `video_assets` with columns title, share_url, duration_ms, tags, updated_at to populate this view.',
    };
  }

  return { clips: data ?? [], message: null };
}

const formatDuration = (ms?: number | null) => {
  if (!ms) return '';
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
};

export default async function VideoPage() {
  const { clips, message } = await loadClips();

  return (
    <main>
      <section className="panel">
        <div className="tag">Video</div>
        <h1>Video Hub</h1>
        <p>Drive or OneDrive links live here. Store clip metadata in Supabase, keep the files in the cloud you already trust.</p>
        <Link className="cta" href="https://drive.google.com" target="_blank" rel="noreferrer">
          Upload to Drive
        </Link>
      </section>

      {message ? <div className="note">{message}</div> : null}

      {clips.length ? (
        <section className="panel">
          <div className="tag">Recent Clips</div>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '12px' }}>
            {clips.map((clip) => (
              <li key={clip.id}>
                <strong>{clip.title ?? `Clip ${clip.id}`}</strong>
                <br />
                <small>
                  {formatDuration(clip.duration_ms)}
                  {clip.tags?.length ? ` · ${clip.tags.join(', ')}` : ''}
                </small>
                <br />
                {clip.share_url ? (
                  <Link href={clip.share_url} target="_blank" rel="noreferrer">
                    Open Clip
                  </Link>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </main>
  );
}
