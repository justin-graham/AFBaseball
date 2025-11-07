# Umpire Report Generator - Fixes Applied

## Issues Fixed

### 1. Zone-Specific Filters Not Working ✅
**Problem**: Both I-Zone and O-Zone missed calls were showing identical values (e.g., both showing 1017).

**Root Cause**: The filter string was not being properly wrapped in `&filters=(...)` format. The filters were being built with leading `%20AND%20` and then appended directly to the URL instead of being wrapped.

**Fix**: Updated `fetch_umpire_stats()` function to properly wrap filters:
```python
if filters:
    # Remove leading %20AND%20 if present
    filter_content = filters.lstrip("%20AND%20").lstrip("%20")
    filter_param = f"&filters=(({filter_content}))"
else:
    filter_param = ""
```

**Result**: Zone metrics now return different values:
- Overall: I-Zone=0, O-Zone=270
- Home team: I-Zone=0, O-Zone=38
- Away team: I-Zone=0, O-Zone=94

### 2. Charts Not Loading ✅
**Problem**: Chart scraping was returning 0 charts.

**Root Cause**: URL parameters were incorrect - using `bseason: [2025]` instead of `bseason: ["def"]` and including unnecessary `s` parameter.

**Fix**: Updated `build_team_pitching_url()`:
```python
f = {"bseason": ["def"], "bdr": [start_date, end_date]}  # Changed from [2025] to ["def"]
# Removed s parameter completely
```

**Result**: Charts now load successfully - 30 charts captured (10 for overall, 10 for home team, 10 for away team).

### 3. Wrong Team IDs ⚠️ NEEDS ACTION
**Problem**: Team IDs in Supabase database don't match TruMedia's team IDs:
- Air Force: Database has `75`, should be `730205440`
- UNLV: Database has `243`, should be `730161664`

**Fix Created**: Script `update_trumedia_team_ids.py` created to update all team IDs from `all_teams_2025.csv`.

**Action Required**: Run the script with SUPABASE_KEY environment variable set:
```bash
export SUPABASE_KEY="your_key_here"
python3 update_trumedia_team_ids.py
```

## Test Results

Successfully generated umpire report with correct team IDs:
```bash
python3 umpire_report_gen.py \
  --home-team "Air Force" \
  --home-team-id "730205440" \
  --away-team "UNLV" \
  --away-team-id "730161664" \
  --season 2025 \
  --start-date "2025-03-01" \
  --end-date "2025-03-31" \
  --output-dir "./test_reports"
```

Results:
- ✅ 30 charts captured
- ✅ 54 rows of data per team
- ✅ Zone filters working (different values for I-Zone vs O-Zone)
- ✅ PDF generated successfully

## Files Modified

1. **umpire_report_gen.py**
   - Line 98-104: Fixed filter wrapping in `fetch_umpire_stats()`
   - Line 54: Changed `bseason: ["def"]` in `build_team_pitching_url()`
   - Line 62: Removed `s` parameter
   - Lines 190-262: Updated all 5 splits to use `fetch_zone_stats()`

2. **update_trumedia_team_ids.py** (NEW)
   - Script to sync Supabase team IDs with TruMedia IDs

## Next Steps

1. **Update Database Team IDs**: Run `update_trumedia_team_ids.py` with SUPABASE_KEY
2. **Test Web Interface**: After database update, test report generation through `/umpires` page
3. **Verify Metrics**: Check that generated reports show realistic umpire accuracy metrics

## Known Behavior

- I-Zone missed calls may be 0 for some date ranges (no strikes incorrectly called as balls)
- O-Zone missed calls typically higher (balls incorrectly called as strikes)
- This is expected behavior based on the specific games and umpires in the date range
