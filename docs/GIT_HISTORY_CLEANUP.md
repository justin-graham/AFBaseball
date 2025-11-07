# Git History Cleanup Guide

## Warning

This operation is **DESTRUCTIVE** and will:
- Rewrite ALL commit history
- Change ALL commit hashes
- Require force-pushing to remote
- Require all team members to re-clone the repository
- Break any open pull requests or branches

**Only proceed if you understand the implications and have backups.**

---

## Prerequisites

1. **Backup**: You already have a `backup-before-cleanup` branch
2. **Clean working directory**: All changes are committed
3. **Notify team**: Warn anyone with clones that they'll need to re-clone

---

## Step 1: Create a Mirror Clone

```bash
cd /Users/justin
git clone --mirror AFBaseball AFBaseball-clean.git
cd AFBaseball-clean.git
```

---

## Step 2: Remove Sensitive Data from History

### Identify Sensitive Data Patterns

Based on the codebase review, the following sensitive data exists in history:

**Files to remove completely:**
- `google-sa.json` - Service account credentials
- `*.pem` - Private keys
- `*.key` - Key files

**Strings to replace:**
- Database password: `AmericasTeam2018!`
- TruMedia master token: `eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...`
- Supabase anon key: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

### Remove Files

```bash
git filter-repo --invert-paths \
  --path google-sa.json \
  --path '*.pem' \
  --path '*.key' \
  --force
```

### Replace Sensitive Strings

Create a file `replacements.txt`:

```
AmericasTeam2018!==>***REDACTED***
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiZjZlZWEwYzViZmUwZTY4ZmEwZDUyMGQyMDU2NTNmYzciLCJpYXQiOjE3NTc0MjE1NjF9.p940yyxhsJZp_gZFX-4Y4U48WqZrvbylDyY8Oj2u9q0==>***REDACTED_TRUMEDIA_TOKEN***
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR5YmNjZGF1d2F0d2FhbnRnaGxuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjAzNzM2MTUsImV4cCI6MjA3NTk0OTYxNX0.czT8nRLuyo0frR5lO65zpGOxhtNtFzyxGFvlkCHsHOA==>***REDACTED_SUPABASE_KEY***
Justin.Graham@afacademy.af.edu==>***REDACTED_EMAIL***
```

```bash
git filter-repo --replace-text replacements.txt --force
```

---

## Step 3: Remove Large Files from History

### Identify Large Files

```bash
git rev-list --all --objects | \
  git cat-file --batch-check | \
  sort -k3nr | \
  head -20
```

### Remove Specific Large Files

If you find large files that shouldn't be in history (Excel files, binaries, etc.):

```bash
git filter-repo --invert-paths \
  --path "AIR FORCE CHARTS.xlsx" \
  --path "UNLV Scouting Report 2025.xlsx" \
  --path-glob "*.xlsx" \
  --force
```

**Note**: Be careful with this - make sure these files aren't needed in history.

---

## Step 4: Remove Generated Directories from History

Remove directories that were tracked but shouldn't have been:

```bash
git filter-repo --invert-paths \
  --path reports/ \
  --path test_reports/ \
  --path trumedia_charts/ \
  --path app/web/scouting_charts/ \
  --path chromedriver/ \
  --path __pycache__/ \
  --force
```

---

## Step 5: Garbage Collection

Clean up unreferenced objects:

```bash
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

---

## Step 6: Verify Cleaned Repository

Check the size reduction:

```bash
du -sh .
```

Verify no sensitive data remains:

```bash
git log --all -p | grep -i "AmericasTeam2018" && echo "WARNING: Password still in history!"
git log --all -p | grep "eyJ0eXAiOiJKV1Q" && echo "WARNING: Token still in history!"
```

---

## Step 7: Replace Original Repository

**DANGER ZONE**: This will replace your original repository.

```bash
cd /Users/justin
mv AFBaseball AFBaseball-old
git clone AFBaseball-clean.git AFBaseball
cd AFBaseball
git remote add origin <your-remote-url>
```

---

## Step 8: Force Push to Remote

**WARNING**: This will overwrite remote history. All team members will need to re-clone.

```bash
git push origin --force --all
git push origin --force --tags
```

---

## Step 9: Notify Team

Send this message to all team members:

```
🚨 IMPORTANT: Git History Has Been Rewritten 🚨

The AFBaseball repository history has been cleaned to remove sensitive data
and reduce size. You MUST re-clone the repository:

1. Delete your local clone
2. Clone fresh: git clone <repo-url>
3. Recreate any local branches from remote

All commit hashes have changed. Any open PRs or branches based on old commits
are now invalid and must be recreated.

Backup branch available: backup-before-cleanup
```

---

## Rollback (If Needed)

If something goes wrong:

```bash
cd /Users/justin/AFBaseball
git checkout backup-before-cleanup
git branch -D master
git checkout -b master
git push origin master --force
```

---

## Alternative: Start Fresh

If history cleanup is too risky, consider starting a fresh repository:

```bash
cd /Users/justin/AFBaseball
git checkout --orphan fresh-start
git add -A
git commit -m "Initial commit with cleaned structure"
git branch -D master
git branch -m master
git push origin master --force
```

This creates a brand new history with a single commit.

---

## Size Reduction Estimate

**Before cleanup**:
- Large files in history: ~100MB+ (scouting charts, Excel files, ChromeDriver)
- Total repository size: ~150-200MB

**After cleanup**:
- Estimated size reduction: 60-80%
- Final repository size: ~30-60MB

---

## Important Notes

1. **Rotate all exposed credentials** after cleanup:
   - Change database password
   - Regenerate TruMedia token
   - Rotate Supabase keys
   - Update service account keys

2. **Update documentation** to remove/redact sensitive information

3. **Consider using environment variables** for all sensitive data going forward

---

## Questions?

- Git filter-repo docs: https://github.com/newren/git-filter-repo
- If unsure, ask before proceeding
- Keep the backup branch until you're certain everything works
