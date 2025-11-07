# AF Baseball Analytics

A single Next.js 14 App Router surface styled with Cera and the Air Force palette. Supabase stores light metadata; Google Sheets keeps the workflow familiar.

## Stack Snapshot

- `web/`: Next.js + TypeScript, no UI frameworks, custom CSS (soft brutalist grid).
- `scripts/`: Python report generators and utilities
- `docs/`: Comprehensive documentation
- Fonts: Local Cera Regular/Bold in `web/public/fonts`.
- Data:
  - `leaderboard_summary` view (category, label, value, detail, rank).
  - `practice_sheets` table (id, title, embed_url, game_type, opponent, updated_at).
  - `video_assets` table (id, title, share_url, duration_ms, tags, updated_at).
- Supabase creds exposed on the home page for quick wiring:
  - Project `tybccdauwatwaantghln`
  - Anon key `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR5YmNjZGF1d2F0d2FhbnRnaGxuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjAzNzM2MTUsImV4cCI6MjA3NTk0OTYxNX0.czT8nRLuyo0frR5lO65zpGOxhtNtFzyxGFvlkCHsHOA`
  - Connection string `postgresql://postgres:AmericasTeam2018!@db.tybccdauwatwaantghln.supabase.co:5432/postgres`

## Run It

```bash
cd web
npm install
npm run dev
```

Create `web/.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=https://tybccdauwatwaantghln.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR5YmNjZGF1d2F0d2FhbnRnaGxuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjAzNzM2MTUsImV4cCI6MjA3NTk0OTYxNX0.czT8nRLuyo0frR5lO65zpGOxhtNtFzyxGFvlkCHsHOA
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-google-oauth-client-id.apps.googleusercontent.com
NEXT_PUBLIC_PITCHING_TEMPLATE_ID=drive-template-id
NEXT_PUBLIC_PITCHING_FOLDER_ID=drive-folder-id (optional)
NEXT_PUBLIC_PITCHING_DEFAULT_EMBED=https://docs.google.com/.../edit?rm=embedded (optional)
```

Grant your Google OAuth client access to the Drive API, then share the template (and optional destination folder) with the same account you authenticate with in the browser. The Pitching page requests a user token, copies the template, and swaps the iframe to the new sheet.

Seed Supabase tables/views with CSV imports or SQL, then drop sheet embed URLs into `practice_sheets`. The newest row with an `embed_url` renders inline on each section page.

## Pages

| Page      | Purpose                                                |
|-----------|--------------------------------------------------------|
| `/`       | Leaderboards (Supabase view) + templates + TruMedia refs |
| `/pitching` | Pitching charts workbook + latest bullpen sheet         |
| `/hitting`  | Cage plans / spray charts (practice sheets)             |
| `/catching` | Framing + recovery logs                                 |
| `/scouting` | UNLV scouting template + opponent reports               |
| `/umpires`  | Zone accountability sheets                              |
| `/video`    | Video assets table (Drive/OneDrive links)               |

`/api/run-report` and `/api/refresh-trumedia` remain stubs. Point them at Supabase Edge Functions or hosted scripts when automation is ready.

## Philosophy

1. Minimize files and lines—only keep what earns a spot on the roster.
2. Supabase is the source of truth; Google Sheets stays the editing canvas.
3. Build features vertically: one table, one page, one automation at a time.
