#!/usr/bin/env python3
"""
Update Supabase teams table with Division 1 teams only
This script deletes all existing teams and inserts only D1 teams from the CSV file
"""

import os
import sys
import pandas as pd
from supabase import create_client, Client
from pathlib import Path

# Load environment variables from .env.local if not already set
if not os.getenv("NEXT_PUBLIC_SUPABASE_URL"):
    env_file = Path(__file__).parent / "app" / "web" / ".env.local"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

# Supabase configuration
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")

# CSV file path
CSV_FILE = "all_teams_2025.csv"


def get_supabase_client():
    """Create and return Supabase client"""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("ERROR: Supabase credentials not found in environment variables")
        print("Please set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY")
        sys.exit(1)

    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def load_teams_from_csv(csv_file):
    """Load teams from CSV file"""
    if not os.path.exists(csv_file):
        print(f"ERROR: CSV file not found: {csv_file}")
        print("Please run fetch_all_teams.py first to generate the CSV file")
        sys.exit(1)

    try:
        df = pd.read_csv(csv_file)
        print(f"Loaded {len(df)} teams from {csv_file}")
        return df
    except Exception as e:
        print(f"ERROR loading CSV file: {e}")
        sys.exit(1)


def delete_all_teams(supabase):
    """Delete all existing teams from Supabase"""
    try:
        # Get count of existing teams
        response = supabase.table('teams').select('id', count='exact').execute()
        count = response.count

        if count == 0:
            print("No existing teams to delete")
            return

        print(f"Deleting {count} existing teams...")

        # Delete all teams (Supabase requires a filter, so we delete where id is not null)
        supabase.table('teams').delete().neq('id', 0).execute()
        print(f"✓ Deleted all existing teams")

    except Exception as e:
        print(f"ERROR deleting teams: {e}")
        sys.exit(1)


def insert_d1_teams(supabase, teams_df):
    """Insert D1 teams into Supabase"""
    try:
        # Prepare team records
        teams_records = []
        for _, row in teams_df.iterrows():
            record = {
                'team_id': str(row['teamId']),
                'name': row['fullName'],
                'abbrev': row['abbrevName']
            }
            teams_records.append(record)

        # Insert in batches of 100 to avoid API limits
        batch_size = 100
        total_inserted = 0

        for i in range(0, len(teams_records), batch_size):
            batch = teams_records[i:i+batch_size]
            supabase.table('teams').insert(batch).execute()
            total_inserted += len(batch)
            print(f"   Inserted {total_inserted}/{len(teams_records)} teams...")

        print(f"✓ Successfully inserted {total_inserted} Division 1 teams")

    except Exception as e:
        print(f"ERROR inserting teams: {e}")
        sys.exit(1)


def verify_update(supabase):
    """Verify the teams were updated correctly"""
    try:
        response = supabase.table('teams').select('id', count='exact').execute()
        count = response.count
        print(f"\n✓ Verification: {count} teams in database")

        # Show sample teams
        sample = supabase.table('teams').select('*').limit(5).execute()
        print("\nSample teams in database:")
        for team in sample.data:
            print(f"   - {team['name']} ({team['abbrev']}) - ID: {team['team_id']}")

    except Exception as e:
        print(f"WARNING: Could not verify update: {e}")


def main():
    """Main execution function"""
    print("=" * 60)
    print("Update Supabase Teams Table - Division 1 Teams Only")
    print("=" * 60)

    # Load teams from CSV
    print("\n1. Loading Division 1 teams from CSV...")
    teams_df = load_teams_from_csv(CSV_FILE)

    # Connect to Supabase
    print("\n2. Connecting to Supabase...")
    supabase = get_supabase_client()
    print("   ✓ Connected to Supabase")

    # Delete all existing teams
    print("\n3. Deleting existing teams...")
    delete_all_teams(supabase)

    # Insert D1 teams
    print("\n4. Inserting Division 1 teams...")
    insert_d1_teams(supabase, teams_df)

    # Verify
    print("\n5. Verifying update...")
    verify_update(supabase)

    print("\n" + "=" * 60)
    print("Complete! Teams table updated with D1 teams only")
    print("=" * 60)


if __name__ == "__main__":
    main()
