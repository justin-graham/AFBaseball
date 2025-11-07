# Pitching Report Generator - Deployment Guide

This guide covers both local testing and deploying the integrated pitching report generator to Google Cloud Run.

## Table of Contents

1. [Quick Start (Local Testing)](#quick-start-local-testing)
2. [Production Deployment (Cloud Run)](#production-deployment-cloud-run)
3. [Troubleshooting](#troubleshooting)

---

## Quick Start (Local Testing)

Before deploying to production, test the system locally in 3 steps:

### Step 1: Create Supabase Players Table

1. Go to your Supabase project dashboard
2. Open SQL Editor
3. Run the contents of `sql/create_players_table.sql`

### Step 2: Sync Air Force Roster

1. Start your Next.js dev server: `cd web && npm run dev`
2. Navigate to http://localhost:3000/settings
3. Click "Sync Air Force Roster"
4. Should see success message with player count (typically 30-40 players)

### Step 3: Test Report Generation

```bash
# Install Python dependencies
pip3 install -r scripts/requirements.txt

# Test report generation
python3 scripts/reports/pitching_report.py \
  --player-name "Player Name" \
  --player-id "1234567890" \
  --season 2025 \
  --start-date "2025-02-01" \
  --end-date "2025-03-31"
```

**Expected Result**: Creates `PlayerName_YYYY-MM-DD_to_YYYY-MM-DD_Pitching_Report.pdf`

---

## Production Deployment (Cloud Run)

### Prerequisites

1. **Google Cloud Project** with billing enabled
2. **Google Cloud CLI** installed (`gcloud`)
3. **Docker** installed
4. **Supabase** project configured
5. **Google Drive Service Account** with access to target folder

---

## Step 1: Sync Player Roster

1. Open your application at `http://localhost:3000/settings` (or deployed URL)
2. Click "Sync Roster from TruMedia"
3. Verify players are populated

Alternatively, use the API directly:
```bash
curl -X POST http://localhost:3000/api/sync-roster
```

---

## Step 2: Create Google Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to **IAM & Admin → Service Accounts**
3. Click **Create Service Account**
   - Name: `pitching-report-generator`
   - Role: None needed initially
4. Click **Create and Continue**, then **Done**
5. Click on the service account, go to **Keys** tab
6. Click **Add Key → Create New Key → JSON**
7. Download the JSON key file (save as `service-account-key.json`)

### Grant Drive Access

1. Open the JSON key file and copy the `client_email` value
2. Go to Google Drive folder: https://drive.google.com/drive/folders/100mGMWCQnwoi8Jg0PbJn03im2Ddj07K2
3. Click **Share**
4. Add the service account email with **Editor** permissions
5. Click **Send**

---

## Step 3: Build and Deploy to Cloud Run

### Build Docker Image

```bash
cd /Users/justin/AFBaseball

# Set your Google Cloud project ID
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"

# Build the Docker image
docker build -f Dockerfile.pitching-report -t gcr.io/${PROJECT_ID}/pitching-report:latest .

# Push to Google Container Registry
docker push gcr.io/${PROJECT_ID}/pitching-report:latest
```

### Deploy to Cloud Run

```bash
# Deploy with environment variables
gcloud run deploy pitching-report \
  --image gcr.io/${PROJECT_ID}/pitching-report:latest \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --timeout 600 \
  --concurrency 1 \
  --max-instances 3 \
  --set-env-vars "TRUMEDIA_USERNAME=Justin.Graham@afacademy.af.edu" \
  --set-env-vars "TRUMEDIA_SITENAME=airforce-ncaabaseball" \
  --set-env-vars "TRUMEDIA_MASTER_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiZjZlZWEwYzViZmUwZTY4ZmEwZDUyMGQyMDU2NTNmYzciLCJpYXQiOjE3NTc0MjE1NjF9.p940yyxhsJZp_gZFX-4Y4U48WqZrvbylDyY8Oj2u9q0" \
  --set-env-vars "TRUMEDIA_TEAM_ID=4806" \
  --set-env-vars "DRIVE_FOLDER_ID=100mGMWCQnwoi8Jg0PbJn03im2Ddj07K2"

# Add service account credentials as secret
gcloud secrets create pitching-report-sa-key --data-file=service-account-key.json
gcloud run services update pitching-report \
  --update-secrets=GOOGLE_APPLICATION_CREDENTIALS=pitching-report-sa-key:latest \
  --region ${REGION}
```

### Get Service URL

```bash
gcloud run services describe pitching-report --region ${REGION} --format='value(status.url)'
```

Save this URL for the next step.

---

## Step 4: Configure Web Application

Add the Cloud Run service URL to your Next.js environment variables:

### Local Development

Edit `web/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://tybccdauwatwaantghln.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR5YmNjZGF1d2F0d2FhbnRnaGxuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjAzNzM2MTUsImV4cCI6MjA3NTk0OTYxNX0.czT8nRLuyo0frR5lO65zpGOxhtNtFzyxGFvlkCHsHOA

# TruMedia credentials (for roster sync)
TRUMEDIA_USERNAME=Justin.Graham@afacademy.af.edu
TRUMEDIA_SITENAME=airforce-ncaabaseball
TRUMEDIA_MASTER_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiZjZlZWEwYzViZmUwZTY4ZmEwZDUyMGQyMDU2NTNmYzciLCJpYXQiOjE3NTc0MjE1NjF9.p940yyxhsJZp_gZFX-4Y4U48WqZrvbylDyY8Oj2u9q0
TRUMEDIA_TEAM_ID=4806

# Cloud Run service URL
PITCHING_REPORT_SERVICE_URL=https://pitching-report-xxxxx-uc.a.run.app

# Google OAuth (for sheet creation)
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-google-oauth-client-id.apps.googleusercontent.com
NEXT_PUBLIC_PITCHING_TEMPLATE_ID=your-template-sheet-id
NEXT_PUBLIC_PITCHING_FOLDER_ID=your-folder-id
```

### Production Deployment (Vercel)

Add the same environment variables in Vercel dashboard:
1. Go to your project → Settings → Environment Variables
2. Add each variable above
3. Redeploy

---

## Step 5: Test the Integration

### 1. Test Health Endpoint

```bash
curl https://your-service-url.run.app/health
```

Expected response:
```json
{"status": "healthy"}
```

### 2. Test Report Generation via API

```bash
curl -X POST https://your-service-url.run.app/generate \
  -H "Content-Type: application/json" \
  -d '{
    "playerName": "Smelcer",
    "playerId": "1469809434",
    "season": 2025,
    "startDate": "2025-04-26",
    "endDate": "2025-04-26"
  }'
```

### 3. Test via Web UI

1. Navigate to `/pitching`
2. Select a player from the dropdown
3. Choose a date range
4. Click "Generate Report"
5. Wait 1-2 minutes
6. PDF should display in the iframe

---

## Architecture Summary

```
┌─────────────────┐
│   Next.js Web   │
│  (Vercel/Local) │
└────────┬────────┘
         │
         │ POST /api/generate-pitching-report
         │
         ▼
┌─────────────────┐
│  Cloud Run      │
│  Flask Wrapper  │
└────────┬────────┘
         │
         │ Executes Python script
         │
         ▼
┌──────────────────────────┐
│ pitching_report_         │
│   integrated.py          │
│                          │
│ 1. Fetch TruMedia data   │
│ 2. Scrape charts (Chrome)│
│ 3. Generate PDF          │
│ 4. Upload to Drive       │
└──────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Google Drive   │
│  Folder         │
└─────────────────┘
```

---

## Troubleshooting

### Report Generation Times Out

- Increase Cloud Run timeout: `--timeout 900` (15 minutes max)
- Check Cloud Run logs: `gcloud run logs read --service pitching-report --region ${REGION}`

### Charts Not Scraping

- Check if Chrome is running in Cloud Run container
- View logs for Chrome errors
- Consider disabling scraping: `--disable-scraping` flag

### Drive Upload Fails

- Verify service account has Editor access to Drive folder
- Check `GOOGLE_APPLICATION_CREDENTIALS` secret is set correctly
- Test credentials locally:
  ```python
  from google.oauth2 import service_account
  credentials = service_account.Credentials.from_service_account_file('service-account-key.json')
  print("Credentials loaded successfully")
  ```

### Players Not Showing in Dropdown

- Ensure you ran the roster sync in `/settings`
- Check Supabase `players` table has data
- Verify API endpoint `/api/players` returns data

---

## Cost Estimates (Google Cloud)

- **Cloud Run**: ~$0.00002449 per vCPU-second
- **Cloud Storage**: $0.026 per GB/month
- **Network Egress**: $0.12 per GB

**Estimated monthly cost** for 100 reports/month: ~$5-10

---

## Security Notes

1. **Never commit** `service-account-key.json` to Git
2. **Rotate** TruMedia master token periodically
3. **Restrict** Cloud Run access to specific IPs if possible
4. **Review** Google Drive folder permissions regularly

---

## Next Steps

1. Set up Cloud Scheduler to warm up the service (reduce cold starts)
2. Add report history table to Supabase (optional)
3. Implement caching for frequently requested reports
4. Add player photos to reports (requires photo upload feature)

---

## Support

For issues or questions:
- Check Cloud Run logs
- Review Python script output
- Contact TruMedia support: ncaasupport@trumedianetworks.com
