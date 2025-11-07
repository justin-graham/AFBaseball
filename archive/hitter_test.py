# import requests
# import pandas as pd
# import urllib.parse
# USERNAME = "Justin.Graham@afacademy.af.edu"
# SITENAME = "airforce-ncaabaseball"
# MASTER_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiZjZlZWEwYzViZmUwZTY4ZmEwZDUyMGQyMDU2NTNmYzciLCJpYXQiOjE3NTc0MjE1NjF9.p940yyxhsJZp_gZFX-4Y4U48WqZrvbylDyY8Oj2u9q0"
# TEAM_ID = "4806"
# url = "https://api.trumedianetworks.com/v1/siteadmin/api/createTempPBToken"
# response = requests.post(url, json={"username": USERNAME, "sitename": SITENAME, "token": MASTER_TOKEN})
# token = response.json()["pbTempToken"]
# player_name = "Zapp"
# season_year = 2025
# player_id = "1110077952" 
# columns = "[G],[PA],[BA],[OBP],[SLG],[K/BB],[Take%],[Swing%],[InZoneSwing%],[InZoneWhiff%],[Chase%],[Hard%],[ExitVel],[MxExitVel],[LaunchAng]"

# format = "RAW"
# filters = "&filters=((game.gameDate%20%3E%3D%20'2025-02-15')%20AND%20(game.gameDate%20%3C%3D%20'2025-02-19%2023%3A59%3A59'))"
# columns_encoded = urllib.parse.quote(columns)
# api_url = (
# f"https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/PlayerGames.csv"
# f"?seasonYear={season_year}&playerId={player_id}&columns={columns_encoded}&token={token}"
# f"&format={format}{filters}"
# )
# data = pd.read_csv(api_url)
# print(data.head())
# right_filters = "&filters=((game.gameDate%20%3E%3D%20'2025-04-05')%20AND%20(game.gameDate%20%3C%3D%20'2025-04-05%2023%3A59%3A59')%20AND%20((event.pitcherHand%20%3D%20'R')))"
# left_filters = "&filters=((game.gameDate%20%3E%3D%20'2025-02-14')%20AND%20(game.gameDate%20%3C%3D%20'2025-02-19%2023%3A59%3A59')%20AND%20((event.pitcherHand%20%3D%20'L')))"

#!/usr/bin/env python3
"""
TruMedia Hitting Report Generator
Generates a PDF hitting report by scraping visuals from TruMedia and fetching stats via API

Prerequisites:
    - Chrome browser running with remote debugging:
      chrome --remote-debugging-port=9222
    - Python packages: selenium, reportlab, requests, pandas, pillow

Usage:
    python hitter_test.py --player-name "Walker Zapp" --player-id "1110077952" --season 2025 --start-date "2025-02-15" --end-date "2025-02-19" --output-dir "./reports"
"""

import os
import sys
import json
import time
import argparse
import urllib.parse
import urllib.request
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg
from PIL import Image
from trumedia_scraper import TruMediaScraper

# TruMedia API Configuration (from environment or defaults)
USERNAME = os.getenv("TRUMEDIA_USERNAME", "Justin.Graham@afacademy.af.edu")
SITENAME = os.getenv("TRUMEDIA_SITENAME", "airforce-ncaabaseball")
MASTER_TOKEN = os.getenv("TRUMEDIA_MASTER_TOKEN", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiZjZlZWEwYzViZmUwZTY4ZmEwZDUyMGQyMDU2NTNmYzciLCJpYXQiOjE3NTc0MjE1NjF9.p940yyxhsJZp_gZFX-4Y4U48WqZrvbylDyY8Oj2u9q0")
CHROME_DEBUG_PORT = int(os.getenv("CHROME_DEBUG_PORT", "9222"))


def build_hitting_url(player_name, player_id, season):
    """Build TruMedia batting page URL"""
    cp = {"filterSelections": ["anyone"], "sortSelections": ["alpha"],
          "playerIds": [player_id], "selectedReportId": 108}
    f = {"bseason": [season]}
    s = {"combinedSplits": ["filterBaseballPitcherHand"], "combinedSplitsSubtotals": {}}
    base = "https://airforce-ncaabaseball.trumedianetworks.com"
    return (f"{base}/baseball/player-custom-pages-batting/{player_name}/{player_id}"
            f"?cp={urllib.parse.quote(json.dumps(cp))}&f={urllib.parse.quote(json.dumps(f))}"
            f"&sh={urllib.parse.quote(json.dumps({}))}&s={urllib.parse.quote(json.dumps(s))}")


def get_trumedia_token():
    """Get temporary token from TruMedia API"""
    url = "https://api.trumedianetworks.com/v1/siteadmin/api/createTempPBToken"
    response = requests.post(url, json={"username": USERNAME, "sitename": SITENAME, "token": MASTER_TOKEN})
    return response.json()["pbTempToken"]


def fetch_player_stats(token, player_id, season, filters=""):
    """Fetch player statistics from TruMedia API"""
    columns = "[G],[PA],[BA],[OBP],[SLG],[K/BB],[Take%],[Swing%],[InZoneSwing%],[InZoneWhiff%],[Chase%],[Hard%],[ExitVel],[MxExitVel],[LaunchAng]"
    columns_encoded = urllib.parse.quote(columns)
    format_param = "RAW"
    
    api_url = (
        f"https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/PlayerGames.csv"
        f"?seasonYear={season}&playerId={player_id}&columns={columns_encoded}&token={token}"
        f"&format={format_param}{filters}"
    )
    
    try:
        data = pd.read_csv(api_url)
        return data
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return None


def generate_pdf(player_name, stats_dict, image_dir, output_path, date_range):
    """Generate the hitting report PDF"""
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    
    # Colors
    navy = colors.HexColor('#002F6C')
    light_gray = colors.HexColor('#E0E0E0')
    
    # Split player name
    first_name, last_name = player_name.split()
    
    # Header - Player Name (larger, left side)
    c.setFont("Helvetica-Bold", 45)
    c.setFillColor(colors.black)
    c.drawString(0.75*inch, height - 1.3*inch, first_name)
    c.drawString(0.75*inch, height - 1.9*inch, last_name)

    # Circular placeholder for headshot
    c.setStrokeColor(light_gray)
    c.setFillColor(colors.white)
    c.setLineWidth(2)
    c.circle(3.2*inch, height - 1.5*inch, 0.6*inch, stroke=1, fill=1)

    # Header - Stats (right side, aligned with underlines)
    c.setFont("Helvetica", 14)
    c.setFillColor(colors.black)
    y_start = height - 1.1*inch

    # Games
    c.drawString(4.5*inch, y_start, f"Games: {stats_dict['games']}")
    c.line(4.5*inch, y_start - 0.1*inch, 6.2*inch, y_start - 0.1*inch)

    # Plate Appearances
    c.drawString(4.5*inch, y_start - 0.45*inch, f"Plate Appearances: {stats_dict['pa']}")
    c.line(4.5*inch, y_start - 0.55*inch, 6.8*inch, y_start - 0.55*inch)

    # Slashline
    c.drawString(4.5*inch, y_start - 0.90*inch, f"Slashline: {stats_dict['slashline']}")
    c.line(4.5*inch, y_start - 1.0*inch, 7.0*inch, y_start - 1.0*inch)

    # Team Logo (AF logo image)
    if os.path.exists('AF_logo.png'):
        c.drawImage('AF_logo.png', 7.2*inch, height - 1.8*inch, width=1*inch, height=1*inch, preserveAspectRatio=True, mask='auto')
    else:
        # Fallback to text if image not found
        c.setFont("Helvetica-Bold", 90)
        c.setFillColor(navy)
        c.drawString(7*inch, height - 1.8*inch, "AF")
    
    # Heat Maps Section (no labels)
    y_pos = height - 2.8*inch

    # SLG Heat Map (centered)
    if os.path.exists(os.path.join(image_dir, 'slg_heatmap.png')):
        c.drawImage(os.path.join(image_dir, 'slg_heatmap.png'),
                   0.6*inch, y_pos - 3.0*inch, width=3.36*inch, height=3.36*inch, preserveAspectRatio=True, mask='auto')
    else:
        # Draw placeholder
        c.setStrokeColor(colors.grey)
        c.rect(0.6*inch, y_pos - 3.0*inch, 3.36*inch, 3.36*inch)

    # BA Heat Map (centered)
    if os.path.exists(os.path.join(image_dir, 'ba_heatmap.png')):
        c.drawImage(os.path.join(image_dir, 'ba_heatmap.png'),
                   4.55*inch, y_pos - 3.0*inch, width=3.36*inch, height=3.36*inch, preserveAspectRatio=True, mask='auto')
    else:
        # Draw placeholder
        c.setStrokeColor(colors.grey)
        c.rect(4.55*inch, y_pos - 3.0*inch, 3.36*inch, 3.36*inch)
    
    # Stats Table
    y_pos = height - 7.2*inch
    
    # Table headers
    headers = ["Pitcher Hand", "Take%", "Swing%", "ZSwing%", "ZWhiff%", "Chase%", "Hard%", "Exit Velo", "Max EV", "LA"]
    
    # Create table data
    table_data = [
        headers,
        ["Left"] + [f"{stats_dict['left'][k]}" for k in ['take', 'swing', 'zswing', 'zwhiff', 'chase', 'hard', 'exit_velo', 'max_ev', 'la']],
        ["Right"] + [f"{stats_dict['right'][k]}" for k in ['take', 'swing', 'zswing', 'zwhiff', 'chase', 'hard', 'exit_velo', 'max_ev', 'la']]
    ]
    
    table = Table(table_data, colWidths=[1.0*inch] + [0.65*inch]*9)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), navy),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOX', (0, 0), (-1, -1), 2.5, navy),
        ('ROUNDEDCORNERS', [8, 8, 8, 8]),
    ]))
    
    table.wrapOn(c, width, height)
    # Center the table horizontally
    table_width = 1.0*inch + 9*0.65*inch
    table.drawOn(c, (width - table_width) / 2, y_pos)
    
    # Bottom Section: Metrics Circles and Pitch Chart
    # Position pitch chart 0.1" from bottom
    pitch_chart_y = 0.1*inch

    def draw_metric_circle(x, y, percentage, label):
        # Gray circle outline only
        c.setStrokeColor(light_gray)
        c.setLineWidth(12)
        c.circle(x, y, 0.5*inch, stroke=1, fill=0)

        # Percentage text
        c.setFont("Helvetica-Bold", 24)
        c.setFillColor(navy)
        c.drawCentredString(x, y - 0.12*inch, f"{int(percentage)}%")

        # Label
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.black)
        c.drawCentredString(x, y - 0.85*inch, label)

    # Left side: Swing Rate (top) and Chase Rate (bottom)
    draw_metric_circle(1.8*inch, 3.0*inch, stats_dict['swing_rate'], "Swing Rate")
    draw_metric_circle(1.8*inch, 1.5*inch, stats_dict['chase_rate'], "Chase Rate")

    # Center: Pitch Chart (centered on page, near bottom)
    svg_path = os.path.join(image_dir, 'swing_miss.svg')
    if os.path.exists(svg_path):
        drawing = svg2rlg(svg_path)
        if drawing:
            # Scale the drawing to fit
            scale = min(3.5*inch / drawing.width, 3.5*inch / drawing.height)
            drawing.width *= scale
            drawing.height *= scale
            drawing.scale(scale, scale)
            renderPDF.draw(drawing, c, 2.5*inch, pitch_chart_y)
    else:
        # Placeholder for pitch chart
        c.setStrokeColor(colors.grey)
        c.rect(2.5*inch, pitch_chart_y, 3.5*inch, 3.5*inch)

    # Right side: Zone Swing Rate (top) and Zone Whiff Rate (bottom)
    draw_metric_circle(6.7*inch, 3.0*inch, stats_dict['zone_swing'], "Zone Swing Rate")
    draw_metric_circle(6.7*inch, 1.5*inch, stats_dict['zone_whiff'], "Zone Whiff Rate")
    
    # Footer
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(navy)
    c.drawCentredString(width/2, 0.3*inch, date_range)
    
    c.save()
    print(f"\n✓ PDF generated: {output_path}")


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Generate TruMedia hitting report")
    parser.add_argument('--player-name', required=True, help='Player name (e.g., "Walker Zapp")')
    parser.add_argument('--player-id', required=True, help='TruMedia player ID')
    parser.add_argument('--season', type=int, required=True, help='Season year')
    parser.add_argument('--start-date', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--output-dir', default='./reports', help='Output directory for PDF')
    parser.add_argument('--disable-scraping', action='store_true', help='Disable chart scraping')
    args = parser.parse_args()

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Parse player name
    name_parts = args.player_name.split()
    if len(name_parts) < 2:
        print(f"ERROR: Player name must include first and last name: {args.player_name}")
        sys.exit(1)
    player_first_name = name_parts[0]
    player_last_name = " ".join(name_parts[1:])

    print("="*60)
    print("TruMedia Hitting Report Generator")
    print("="*60)
    print(f"Player: {args.player_name}")
    print(f"Season: {args.season}")
    print(f"Date Range: {args.start_date} to {args.end_date}")
    print("="*60)

    try:
        # Get token
        print("\n1. Getting TruMedia API token...")
        token = get_trumedia_token()
        print("   ✓ Token obtained")

        # Fetch statistics
        print("\n2. Fetching player statistics...")

        # Full season stats (no date filter) for header and metric circles
        print("   - Fetching full season stats...")
        full_season = fetch_player_stats(token, args.player_id, args.season, "")

        # Date range stats for table and charts
        print(f"   - Fetching date range stats ({args.start_date} to {args.end_date})...")
        date_filter = f"&filters=((game.gameDate%20%3E%3D%20'{args.start_date}')%20AND%20(game.gameDate%20%3C%3D%20'{args.end_date}%2023%3A59%3A59'))"

        # Overall stats with date filter
        overall = fetch_player_stats(token, args.player_id, args.season, date_filter)

        # Left-handed pitcher stats with date filter
        left_filters = f"&filters=((game.gameDate%20%3E%3D%20'{args.start_date}')%20AND%20(game.gameDate%20%3C%3D%20'{args.end_date}%2023%3A59%3A59')%20AND%20((event.pitcherHand%20%3D%20'L')))"
        left_stats = fetch_player_stats(token, args.player_id, args.season, left_filters)

        # Right-handed pitcher stats with date filter
        right_filters = f"&filters=((game.gameDate%20%3E%3D%20'{args.start_date}')%20AND%20(game.gameDate%20%3C%3D%20'{args.end_date}%2023%3A59%3A59')%20AND%20((event.pitcherHand%20%3D%20'R')))"
        right_stats = fetch_player_stats(token, args.player_id, args.season, right_filters)

        if full_season is None or full_season.empty:
            raise Exception("Failed to fetch full season statistics")

        if overall is None or overall.empty:
            raise Exception(f"No data found for date range {args.start_date} to {args.end_date}")
    
        print("   ✓ Statistics fetched")

        # Process stats
        def safe_mean(series, decimals=1, is_pct=True):
            """Safely calculate mean with proper formatting"""
            try:
                val = series.mean()
                if pd.isna(val):
                    return "0.0%" if is_pct else "0.0"
                # If value is already in percentage form (> 1), use as is
                # If value is decimal form (< 1), convert to percentage
                if is_pct:
                    if val > 1:
                        return f"{val:.{decimals}f}%"
                    else:
                        return f"{val * 100:.{decimals}f}%"
                return f"{val:.{decimals}f}"
            except:
                return "0.0%" if is_pct else "0.0"

        def safe_sum(series):
            """Safely sum values"""
            try:
                return int(series.sum())
            except:
                return 0

        def safe_max(series, decimals=1):
            """Safely get max value"""
            try:
                val = series.max()
                return f"{val:.{decimals}f}" if not pd.isna(val) else "0.0"
            except:
                return "0.0"

        # Build stats dictionary
        # Header stats: Use FULL SEASON data
        # Metric circles: Use FULL SEASON data
        # Table data: Use DATE RANGE data
        stats_dict = {
            # Header: Full season stats
            'games': safe_sum(full_season['G']),
            'pa': safe_sum(full_season['PA']),
            'slashline': f"{safe_mean(full_season['BA'], 3, False)} / {safe_mean(full_season['OBP'], 3, False)} / {safe_mean(full_season['SLG'], 3, False)}",
            # Table: Date range stats
            'left': {
                'take': safe_mean(left_stats['Take%'], 1, True),
                'swing': safe_mean(left_stats['Swing%'], 1, True),
                'zswing': safe_mean(left_stats['InZoneSwing%'], 1, True),
                'zwhiff': safe_mean(left_stats['InZoneWhiff%'], 1, True),
                'chase': safe_mean(left_stats['Chase%'], 1, True),
                'hard': safe_mean(left_stats['Hard%'], 1, True),
                'exit_velo': safe_mean(left_stats['ExitVel'], 1, False),
                'max_ev': safe_max(left_stats['MxExitVel'], 1),
                'la': safe_mean(left_stats['LaunchAng'], 1, False)
            },
            'right': {
                'take': safe_mean(right_stats['Take%'], 1, True),
                'swing': safe_mean(right_stats['Swing%'], 1, True),
                'zswing': safe_mean(right_stats['InZoneSwing%'], 1, True),
                'zwhiff': safe_mean(right_stats['InZoneWhiff%'], 1, True),
                'chase': safe_mean(right_stats['Chase%'], 1, True),
                'hard': safe_mean(right_stats['Hard%'], 1, True),
                'exit_velo': safe_mean(right_stats['ExitVel'], 1, False),
                'max_ev': safe_max(right_stats['MxExitVel'], 1),
                'la': safe_mean(right_stats['LaunchAng'], 1, False)
            },
            # Metric circles: Full season stats
            'swing_rate': full_season['Swing%'].mean() if not full_season['Swing%'].empty else 0,
            'chase_rate': full_season['Chase%'].mean() if not full_season['Chase%'].empty else 0,
            'zone_swing': full_season['InZoneSwing%'].mean() if not full_season['InZoneSwing%'].empty else 0,
            'zone_whiff': full_season['InZoneWhiff%'].mean() if not full_season['InZoneWhiff%'].empty else 0
        }

        # Convert percentages to proper format (if they're in decimal form, multiply by 100)
        for key in ['swing_rate', 'chase_rate', 'zone_swing', 'zone_whiff']:
            if stats_dict[key] < 1:
                stats_dict[key] = stats_dict[key] * 100
    
        # Scrape visuals
        image_dir = os.path.join(args.output_dir, "trumedia_charts")

        if args.disable_scraping:
            print("\n3. Chart scraping disabled (--disable-scraping flag)")
        else:
            print("\n3. Scraping visual charts...")
            scraper = TruMediaScraper(debug_port=CHROME_DEBUG_PORT, heat_map_png=True)

            try:
                # Connect to Chrome (auto-launches if needed, handles all scenarios)
                scraper.connect()

                # Build hitting page URL and navigate
                url = build_hitting_url(player_last_name, args.player_id, args.season)
                print(f"   ✓ Navigating to TruMedia batting page...")
                scraper.driver.get(url)

                # Scrape charts from the current page
                captured = scraper.scrape_current_page(image_dir)
                print(f"   ✓ Captured {len(captured)} chart(s)")

                # DEBUG: Show what chart files were actually captured
                if captured:
                    print(f"\n   DEBUG: Chart files found:")
                    for chart_path in captured:
                        print(f"     - {Path(chart_path).name}")
                    print()
                else:
                    print(f"   WARNING: No charts were captured from the batting page!")
                    print(f"   This may mean the report view doesn't have visual charts.")

                # Rename charts to match expected names for PDF generation
                # TruMediaScraper names: heat-map_0.png, heat-map_1.png, pitch-chart.svg
                # Expected names: slg_heatmap.png, ba_heatmap.png, swing_miss.svg
                if captured:
                    for chart_path in captured:
                        chart_file = Path(chart_path)
                        if 'heat-map_0' in chart_file.name:
                            new_path = chart_file.parent / 'slg_heatmap.png'
                            chart_file.rename(new_path)
                            print(f"   ✓ Renamed to slg_heatmap.png")
                        elif 'heat-map_1' in chart_file.name:
                            new_path = chart_file.parent / 'ba_heatmap.png'
                            chart_file.rename(new_path)
                            print(f"   ✓ Renamed to ba_heatmap.png")
                        elif 'pitch-chart' in chart_file.name:
                            new_path = chart_file.parent / 'swing_miss.svg'
                            chart_file.rename(new_path)
                            print(f"   ✓ Renamed to swing_miss.svg")

            except Exception as e:
                print(f"   ⚠ Chart scraping failed: {e}")
                print("   Continuing without charts...")
            finally:
                scraper.close()

        # Generate PDF
        print("\n4. Generating PDF...")
        output_filename = f"{player_last_name.replace(' ', '_')}_{args.start_date}_to_{args.end_date}_Hitting_Report.pdf"
        output_path = os.path.join(args.output_dir, output_filename)

        # Format date range for footer
        start_dt = datetime.strptime(args.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(args.end_date, "%Y-%m-%d")
        date_range = f"{start_dt.strftime('%m/%d/%Y')} - {end_dt.strftime('%m/%d/%Y')}"

        generate_pdf(args.player_name, stats_dict, image_dir, output_path, date_range)

        print("\n" + "="*60)
        print("✓ Complete!")
        print(f"📄 Report: {output_path}")
        print("="*60)

        # Output JSON result for API consumption
        result = {
            "success": True,
            "pdfPath": output_path,
            "playerName": args.player_name,
            "season": args.season,
            "dateRange": f"{args.start_date} to {args.end_date}"
        }
        print(f"\n__RESULT_JSON__:{json.dumps(result)}:__END_RESULT__")

    except Exception as e:
        error_msg = str(e)
        print(f"\nERROR: {error_msg}")
        result = {
            "success": False,
            "error": error_msg
        }
        print(f"\n__RESULT_JSON__:{json.dumps(result)}:__END_RESULT__")
        sys.exit(1)


if __name__ == "__main__":
    main()