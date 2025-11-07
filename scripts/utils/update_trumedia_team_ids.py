#!/usr/bin/env python3
"""
Update Supabase teams table with correct TruMedia team IDs
"""

import os
import pandas as pd
from supabase import create_client, Client

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://tybccdauwatwaantghln.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_KEY environment variable not set")
    exit(1)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Read TruMedia teams data
print("Reading TruMedia teams from all_teams_2025.csv...")
teams_df = pd.read_csv('all_teams_2025.csv')
print(f"Found {len(teams_df)} teams")

# Get existing teams from Supabase
print("\nFetching existing teams from Supabase...")
response = supabase.table('teams').select('id, name').execute()
existing_teams = {team['name']: team['id'] for team in response.data}
print(f"Found {len(existing_teams)} teams in Supabase")

# Update team IDs
print("\nUpdating team IDs...")
updated_count = 0
not_found_count = 0
errors = []

for _, row in teams_df.iterrows():
    trumedia_id = str(row['teamId'])
    team_name = row['fullName']

    # Check if team exists in Supabase (by name match)
    if team_name in existing_teams:
        supabase_id = existing_teams[team_name]

        # Update the team_id field with correct TruMedia ID
        try:
            supabase.table('teams').update({
                'team_id': trumedia_id,
                'abbrev': row['abbrevName']
            }).eq('id', supabase_id).execute()

            updated_count += 1
            if updated_count <= 10:  # Show first 10 updates
                print(f"  ✓ Updated {team_name}: team_id={trumedia_id}")
        except Exception as e:
            error_msg = f"Error updating {team_name}: {e}"
            errors.append(error_msg)
            if len(errors) <= 5:
                print(f"  ✗ {error_msg}")
    else:
        not_found_count += 1
        if not_found_count <= 5:  # Show first 5 not found
            print(f"  ⚠️  Team not found in Supabase: {team_name}")

print(f"\nSummary:")
print(f"  Updated: {updated_count}")
print(f"  Not found in Supabase: {not_found_count}")
print("\n✓ Done!")
