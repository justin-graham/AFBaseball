#!/usr/bin/env python3
"""
TruMedia Baseball API - Fetch All Teams
This script fetches all teams for a given season year.
"""

import requests
import json
import pandas as pd
from io import StringIO
import urllib.parse
import sys

# Configuration
USERNAME = "Justin.Graham@afacademy.af.edu"
SITENAME = "airforce-ncaabaseball"
MASTER_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiZjZlZWEwYzViZmUwZTY4ZmEwZDUyMGQyMDU2NTNmYzciLCJpYXQiOjE3NTc0MjE1NjF9.p940yyxhsJZp_gZFX-4Y4U48WqZrvbylDyY8Oj2u9q0"
SEASON_YEAR = 2025  # Change this to the desired season year


def get_temp_token(username, sitename, master_token):
    """
    Create a temporary authentication token for API access.
    
    Args:
        username: TruMedia account email
        sitename: TruMedia site name
        master_token: Master authentication token
        
    Returns:
        Temporary token string
    """
    headers = {"Content-Type": "application/json"}
    data = {
        "username": username,
        "sitename": sitename,
        "token": master_token
    }
    
    url = "https://api.trumedianetworks.com/v1/siteadmin/api/createTempPBToken"
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        token = response.json()
        return token.get("pbTempToken")
    except requests.exceptions.RequestException as e:
        print(f"Error getting temporary token: {e}")
        sys.exit(1)


def fetch_all_teams(season_year, temp_token):
    """
    Fetch all Division 1 teams for a given season.

    Args:
        season_year: Year of the season (e.g., 2025)
        temp_token: Temporary authentication token

    Returns:
        pandas DataFrame with team data (D1 teams only)
    """
    # Filter for Division 1 teams only
    filters = "&filters=(((season.seasonLevel%20IN%20('BBC'%2C'SFT')%20AND%20team.game.gameLeague%20%3D%20'D1')))"

    api_url = (
        f"https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/AllTeams.csv"
        f"?seasonYear={season_year}&token={temp_token}{filters}"
    )

    try:
        print(f"Fetching all Division 1 teams for {season_year} season...")
        data = pd.read_csv(api_url)
        print(f"Successfully fetched {len(data)} Division 1 teams")
        return data
    except Exception as e:
        print(f"Error fetching teams: {e}")
        sys.exit(1)


def main():
    """Main execution function."""
    print("=" * 60)
    print("TruMedia Baseball API - Fetch Division 1 Teams")
    print("=" * 60)

    # Get temporary token
    print("\n1. Authenticating...")
    temp_token = get_temp_token(USERNAME, SITENAME, MASTER_TOKEN)
    print("   ✓ Authentication successful")

    # Fetch teams
    print(f"\n2. Fetching Division 1 teams for {SEASON_YEAR} season...")
    teams_df = fetch_all_teams(SEASON_YEAR, temp_token)

    # Display results
    print("\n3. Results:")
    print(f"   Total D1 teams: {len(teams_df)}")
    print(f"   Columns: {list(teams_df.columns)}")

    # Show first few rows
    print("\n4. Sample data (first 5 teams):")
    print(teams_df.head())

    # Save to CSV
    output_file = f"all_teams_{SEASON_YEAR}.csv"
    teams_df.to_csv(output_file, index=False)
    print(f"\n5. Data saved to: {output_file}")
    print(f"\n   NOTE: This file now contains ONLY Division 1 teams")

    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)

    return teams_df


if __name__ == "__main__":
    teams = main()
