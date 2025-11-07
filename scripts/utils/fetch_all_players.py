#!/usr/bin/env python3
"""
TruMedia Baseball API - Fetch All Players
This script fetches all players with their stats for a given season.
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
SEASON_TYPE = "REG"  # REG for regular season, PLY for playoffs

# Optional: Set minimum plate appearances (PA) to filter players
# Set to 0 to get all players, or increase for qualified players only
MIN_PLATE_APPEARANCES = 0  # Change this value as needed


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


def fetch_all_players(season_year, season_type, temp_token, min_pa=0):
    """
    Fetch all players with their stats for a given season.
    
    Args:
        season_year: Year of the season (e.g., 2025)
        season_type: Type of season ("REG" or "PLY")
        temp_token: Temporary authentication token
        min_pa: Minimum plate appearances to qualify (0 for all players)
        
    Returns:
        pandas DataFrame with player data
    """
    # Define columns to fetch (basic player info and key stats)
    # You can add more columns based on your needs
    columns = "[PA],[AB],[H],[HR],[RBI],[BB],[K],[AVG],[OBP],[SLG],[OPS]"
    columns_encoded = urllib.parse.quote(columns)
    
    # Build the API URL
    api_url = (
        f"https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/PlayerTotals.csv"
        f"?seasonYear={season_year}&seasonType={season_type}&columns={columns_encoded}"
    )
    
    # Add qualification if minimum PA is specified
    if min_pa > 0:
        qualifications = f"&qualification=%5BPA%5D+%3E%3D+{min_pa}"
        api_url += qualifications
    
    # Add token
    api_url += f"&token={temp_token}"
    
    try:
        print(f"Fetching all players for {season_year} {season_type} season...")
        if min_pa > 0:
            print(f"Filtering for players with at least {min_pa} plate appearances...")
        data = pd.read_csv(api_url)
        
        # Convert numeric columns from strings to numbers
        numeric_columns = ['PA', 'AB', 'H', 'HR', 'RBI', 'BB', 'K', 'AVG', 'OBP', 'SLG', 'OPS']
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        print(f"Successfully fetched {len(data)} players")
        return data
    except Exception as e:
        print(f"Error fetching players: {e}")
        sys.exit(1)


def main():
    """Main execution function."""
    print("=" * 60)
    print("TruMedia Baseball API - Fetch All Players")
    print("=" * 60)
    
    # Get temporary token
    print("\n1. Authenticating...")
    temp_token = get_temp_token(USERNAME, SITENAME, MASTER_TOKEN)
    print("   ✓ Authentication successful")
    
    # Fetch players
    print(f"\n2. Fetching players for {SEASON_YEAR} {SEASON_TYPE} season...")
    players_df = fetch_all_players(
        SEASON_YEAR, 
        SEASON_TYPE, 
        temp_token,
        MIN_PLATE_APPEARANCES
    )
    
    # Display results
    print("\n3. Results:")
    print(f"   Total players: {len(players_df)}")
    print(f"   Columns: {list(players_df.columns)}")
    
    # Show first few rows
    print("\n4. Sample data (first 5 players):")
    print(players_df.head())
    
    # Show some statistics
    if 'AVG' in players_df.columns:
        print("\n5. Quick Statistics:")
        try:
            print(f"   Highest Batting Average: {players_df['AVG'].max():.3f}")
            print(f"   Most HRs: {int(players_df['HR'].max())}")
            print(f"   Most RBIs: {int(players_df['RBI'].max())}")
        except Exception as e:
            print(f"   Unable to calculate statistics: {e}")
    
    # Save to CSV
    output_file = f"all_players_{SEASON_YEAR}_{SEASON_TYPE}.csv"
    players_df.to_csv(output_file, index=False)
    print(f"\n6. Data saved to: {output_file}")
    
    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)
    
    return players_df


if __name__ == "__main__":
    players = main()
