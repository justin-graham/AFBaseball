#!/usr/bin/env python3
"""
TruMedia Umpire Report Generator
Generates a 3-page PDF umpire report with accuracy metrics and pitch location diagrams

Prerequisites:
    - Chrome browser running with remote debugging: chrome --remote-debugging-port=9222
    - Python packages: selenium, reportlab, requests, pandas, pillow

Usage:
    python umpire_report_gen.py --home-team "Air Force" --home-team-id "730205440"
        --away-team "Nevada" --away-team-id "730205432"
        --start-date "2025-04-17" --end-date "2025-04-17" --output-dir "./reports"
"""

import os
import sys
import json
import time
import argparse
import urllib.parse
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg
from trumedia_scraper import TruMediaScraper

# TruMedia API Configuration
USERNAME = os.getenv("TRUMEDIA_USERNAME", "Justin.Graham@afacademy.af.edu")
SITENAME = os.getenv("TRUMEDIA_SITENAME", "airforce-ncaabaseball")
MASTER_TOKEN = os.getenv("TRUMEDIA_MASTER_TOKEN", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiZjZlZWEwYzViZmUwZTY4ZmEwZDUyMGQyMDU2NTNmYzciLCJpYXQiOjE3NTc0MjE1NjF9.p940yyxhsJZp_gZFX-4Y4U48WqZrvbylDyY8Oj2u9q0")
CHROME_DEBUG_PORT = int(os.getenv("CHROME_DEBUG_PORT", "9222"))


def get_trumedia_token():
    """Get temporary token from TruMedia API"""
    url = "https://api.trumedianetworks.com/v1/siteadmin/api/createTempPBToken"
    response = requests.post(url, json={"username": USERNAME, "sitename": SITENAME, "token": MASTER_TOKEN})
    return response.json()["pbTempToken"]


def build_team_pitching_url(team_name, team_id, season, start_date, end_date, side=None):
    """Build TruMedia team pitching page URL

    Args:
        side: 't' for top (away team), 'b' for bottom (home team), None for all
    """
    cp = {"filterSelections": ["anyone"], "sortSelections": ["alpha"], "selectedReportId": 114}
    f = {"bseason": ["def"], "bdr": [start_date, end_date]}  # Use "def" for default season

    # Add side filter if specified
    if side:
        f["bside"] = [side]

    base = "https://airforce-ncaabaseball.trumedianetworks.com"
    return (f"{base}/baseball/team-custom-pages-pitching/{team_name}/{team_id}"
            f"?cp={urllib.parse.quote(json.dumps(cp))}&f={urllib.parse.quote(json.dumps(f))}")


def fetch_games(token, team_ids, season, start_date, end_date):
    """Fetch games for the given teams and date range"""
    try:
        # Try to get all games
        team_id_list = "','".join(team_ids)
        team_filter = f"(team.game.teamId%20IN%20('{team_id_list}'))"
        date_filter = f"%20AND%20(game.gameDate%20%3E%3D%20'{start_date}')%20AND%20(game.gameDate%20%3C%3D%20'{end_date}%2023%3A59%3A59')"

        columns = "[game.gameId],[game.gameDate],[team.game.teamId]"
        columns_encoded = urllib.parse.quote(columns)

        api_url = (
            f"https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/AllGames.csv"
            f"?seasonYear={season}&columns={columns_encoded}&token={token}"
            f"&format=RAW&filters=({team_filter}{date_filter})"
        )

        print(f"   Fetching games...")
        data = pd.read_csv(api_url)
        print(f"   Found {len(data)} games")
        return data
    except Exception as e:
        print(f"   Warning: Could not fetch games: {e}")
        return pd.DataFrame()


def fetch_umpire_stats(token, team_id, season, filters=""):
    """Fetch umpire/catcher statistics from TruMedia API using TeamGames endpoint"""
    # Columns for umpire accuracy calculations (verified working from umpire_test.py)
    columns = "[G],[PA],[MC#],[MC%],[CC#],[CC%],[FrmRAA]"
    columns_encoded = urllib.parse.quote(columns)
    format_param = "RAW"

    # Build proper filter string - wrap in &filters=(...) if filters provided
    if filters:
        # Remove leading %20AND%20 if present (it's a continuation, not a start)
        filter_content = filters.lstrip("%20AND%20").lstrip("%20")
        filter_param = f"&filters=(({filter_content}))"
    else:
        filter_param = ""

    # Use teamId as direct parameter (not in filters)
    api_url = (
        f"https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/TeamGames.csv"
        f"?seasonYear={season}&teamId={team_id}&columns={columns_encoded}&token={token}"
        f"&format={format_param}{filter_param}"
    )

    try:
        print(f"      Fetching data for team {team_id}...")
        data = pd.read_csv(api_url)
        print(f"      Retrieved {len(data)} rows")
        return data
    except Exception as e:
        print(f"      Warning: API call failed - {e}")
        return pd.DataFrame()


def calculate_accuracy(stats_df):
    """Calculate accuracy percentage from stats dataframe"""
    if stats_df.empty or 'CC#' not in stats_df.columns or 'MC#' not in stats_df.columns:
        return 0.0, 0, 0

    correct = stats_df['CC#'].sum() if 'CC#' in stats_df.columns else 0
    missed = stats_df['MC#'].sum() if 'MC#' in stats_df.columns else 0
    total = correct + missed

    if total == 0:
        return 0.0, 0, 0

    accuracy = (correct / total) * 100
    return accuracy, int(correct), int(total)


def fetch_zone_stats(token, team_ids, season, base_filter, zone_type):
    """Fetch missed calls for specific zone

    Args:
        token: TruMedia API token
        team_ids: List of team IDs
        season: Season year
        base_filter: Base filter string (date + side + hand filters)
        zone_type: 'in' for I-Zone (strikes called as balls), 'out' for O-Zone (balls called as strikes)

    Returns:
        Number of missed calls in the specified zone
    """
    if zone_type == 'in':
        # I-Zone miss = strike called as ball (event.inOfZone AND event.pitchResult = 'BL')
        zone_filter = base_filter + "%20AND%20((event.inOfZone))%20AND%20((event.pitchResult%20%3D%20'BL'))"
    else:
        # O-Zone miss = ball called as strike (event.outOfZone AND event.pitchResult = 'SL')
        zone_filter = base_filter + "%20AND%20((event.outOfZone))%20AND%20((event.pitchResult%20%3D%20'SL'))"

    combined = pd.DataFrame()
    for team_id in team_ids:
        data = fetch_umpire_stats(token, team_id, season, zone_filter)
        if not data.empty:
            combined = pd.concat([combined, data], ignore_index=True)

    return int(combined['MC#'].sum()) if not combined.empty and 'MC#' in combined.columns else 0


def build_stats_dict(token, team_ids, season, date_filter, side=None):
    """Build stats dictionary from real API data for all splits

    Args:
        side: 'top' for away team (event.top), 'bottom' for home team (event.bottom), None for overall
    """
    stats = {}

    # Add side filter if specified
    if side == "top":
        side_filter = "%20AND%20((event.top))"
    elif side == "bottom":
        side_filter = "%20AND%20((event.bottom))"
    else:
        side_filter = ""

    # Helper function to fetch and combine data from multiple teams
    def fetch_combined(team_ids, filter_str):
        """Fetch data for multiple teams and combine"""
        combined = pd.DataFrame()
        for team_id in team_ids:
            data = fetch_umpire_stats(token, team_id, season, filter_str)
            if not data.empty:
                combined = pd.concat([combined, data], ignore_index=True)
        return combined

    # Overall stats (no hand filters)
    print("      Overall...")
    overall_data = fetch_combined(team_ids, date_filter + side_filter)
    acc, correct, total = calculate_accuracy(overall_data)
    i_zone_miss = fetch_zone_stats(token, team_ids, season, date_filter + side_filter, 'in')
    o_zone_miss = fetch_zone_stats(token, team_ids, season, date_filter + side_filter, 'out')
    stats['overall'] = {
        'accuracy': acc,
        'correct': correct,
        'total': total,
        'i_zone_miss': i_zone_miss,
        'o_zone_miss': o_zone_miss,
        'avg_side_miss': 0.0  # Not available in API
    }

    # vs LHP (left-handed pitchers)
    print("      vs LHP...")
    lhp_filter = date_filter + side_filter + "%20AND%20((event.pitcherHand%20%3D%20'L'))"
    lhp_data = fetch_combined(team_ids, lhp_filter)
    acc, correct, total = calculate_accuracy(lhp_data)
    i_zone_miss_lhp = fetch_zone_stats(token, team_ids, season, lhp_filter, 'in')
    o_zone_miss_lhp = fetch_zone_stats(token, team_ids, season, lhp_filter, 'out')
    stats['vs_lhp'] = {
        'accuracy': acc,
        'correct': correct,
        'total': total,
        'i_zone_miss': i_zone_miss_lhp,
        'o_zone_miss': o_zone_miss_lhp,
        'avg_side_miss': 0.0
    }

    # vs RHP (right-handed pitchers)
    print("      vs RHP...")
    rhp_filter = date_filter + side_filter + "%20AND%20((event.pitcherHand%20%3D%20'R'))"
    rhp_data = fetch_combined(team_ids, rhp_filter)
    acc, correct, total = calculate_accuracy(rhp_data)
    i_zone_miss_rhp = fetch_zone_stats(token, team_ids, season, rhp_filter, 'in')
    o_zone_miss_rhp = fetch_zone_stats(token, team_ids, season, rhp_filter, 'out')
    stats['vs_rhp'] = {
        'accuracy': acc,
        'correct': correct,
        'total': total,
        'i_zone_miss': i_zone_miss_rhp,
        'o_zone_miss': o_zone_miss_rhp,
        'avg_side_miss': 0.0
    }

    # vs LHH (left-handed hitters)
    print("      vs LHH...")
    lhh_filter = date_filter + side_filter + "%20AND%20((event.batterHand%20%3D%20'L'))"
    lhh_data = fetch_combined(team_ids, lhh_filter)
    acc, correct, total = calculate_accuracy(lhh_data)
    i_zone_miss_lhh = fetch_zone_stats(token, team_ids, season, lhh_filter, 'in')
    o_zone_miss_lhh = fetch_zone_stats(token, team_ids, season, lhh_filter, 'out')
    stats['vs_lhh'] = {
        'accuracy': acc,
        'correct': correct,
        'total': total,
        'i_zone_miss': i_zone_miss_lhh,
        'o_zone_miss': o_zone_miss_lhh,
        'avg_side_miss': 0.0
    }

    # vs RHH (right-handed hitters)
    print("      vs RHH...")
    rhh_filter = date_filter + side_filter + "%20AND%20((event.batterHand%20%3D%20'R'))"
    rhh_data = fetch_combined(team_ids, rhh_filter)
    acc, correct, total = calculate_accuracy(rhh_data)
    i_zone_miss_rhh = fetch_zone_stats(token, team_ids, season, rhh_filter, 'in')
    o_zone_miss_rhh = fetch_zone_stats(token, team_ids, season, rhh_filter, 'out')
    stats['vs_rhh'] = {
        'accuracy': acc,
        'correct': correct,
        'total': total,
        'i_zone_miss': i_zone_miss_rhh,
        'o_zone_miss': o_zone_miss_rhh,
        'avg_side_miss': 0.0
    }

    return stats


def draw_chart(c, chart_path, x, y, width, height):
    """Draw an SVG chart at the specified position, removing legend elements"""
    import xml.etree.ElementTree as ET
    import tempfile

    try:
        if not os.path.exists(chart_path):
            return False

        # Parse SVG and remove legend elements
        ET.register_namespace('', 'http://www.w3.org/2000/svg')
        tree = ET.parse(chart_path)
        root = tree.getroot()

        # Remove all elements with class containing 'legend'
        for elem in list(root.iter()):
            class_attr = elem.get('class', '')
            if 'legend' in class_attr or 'leg' in class_attr:
                parent = None
                for p in root.iter():
                    if elem in list(p):
                        parent = p
                        break
                if parent is not None:
                    parent.remove(elem)

        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.svg', delete=False) as tmp:
            tree.write(tmp, encoding='utf-8', xml_declaration=True)
            tmp_path = tmp.name

        # Load and render cleaned SVG
        drawing = svg2rlg(tmp_path)
        os.unlink(tmp_path)  # Clean up temporary file

        if drawing:
            # Scale drawing to fit the box
            scale_x = width / drawing.width
            scale_y = height / drawing.height
            scale = min(scale_x, scale_y) * 0.9  # 90% to leave margin

            drawing.width = drawing.width * scale
            drawing.height = drawing.height * scale
            drawing.scale(scale, scale)

            # Center the drawing in the box
            x_offset = x + (width - drawing.width) / 2
            y_offset = y + (height - drawing.height) / 2

            renderPDF.draw(drawing, c, x_offset, y_offset)
            return True
    except Exception as e:
        print(f"      Warning: Could not render chart {chart_path}: {e}")
        # Clean up temp file if it exists
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return False


def draw_page(c, page_title, stats_dict, date_str, width, height, page_num, charts_dir=None, overlay_charts_dir=None):
    """Draw a single page of the umpire report

    Args:
        overlay_charts_dir: Optional second chart directory to overlay on top of first (for overall page)
    """
    navy = colors.HexColor('#002F6C')
    light_gray = colors.HexColor('#E0E0E0')

    # Check if charts directory exists and has images
    has_charts = charts_dir and os.path.exists(charts_dir) and len(os.listdir(charts_dir)) > 0
    has_overlay = overlay_charts_dir and os.path.exists(overlay_charts_dir) and len(os.listdir(overlay_charts_dir)) > 0

    # Header with logo and title
    if os.path.exists('AF_logo.png'):
        c.drawImage('AF_logo.png', 0.5*inch, height - 1.2*inch,
                   width=0.8*inch, height=0.8*inch, preserveAspectRatio=True, mask='auto')

    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(colors.black)
    c.drawString(1.5*inch, height - 1.0*inch, f"Umpires: {page_title}")

    # Date in top right
    c.setFillColor(colors.blue)
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(width - 0.5*inch, height - 1.0*inch, f"Date: {date_str}")
    c.setFillColor(colors.black)

    # Top section: Accuracy percentages
    y_pos = height - 2.0*inch

    # Headers for accuracy boxes
    headers = ["Overall Accuracy", "Accuracy vs LHP", "Accuracy vs RHP",
               "Accuracy vs LHH", "Accuracy vs RHH"]
    box_width = (width - 1.5*inch) / 5

    for i, header in enumerate(headers):
        x = 0.75*inch + i * box_width

        # Draw box outline
        c.setStrokeColor(light_gray)
        c.setLineWidth(2)
        c.rect(x, y_pos - 1.0*inch, box_width - 0.1*inch, 1.5*inch)

        # Header
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.black)
        c.drawCentredString(x + (box_width - 0.1*inch)/2, y_pos + 0.3*inch, header)

        # Correct/Total
        key = ['overall', 'vs_lhp', 'vs_rhp', 'vs_lhh', 'vs_rhh'][i]
        correct = stats_dict[key]['correct']
        total = stats_dict[key]['total']
        c.setFont("Helvetica", 8)
        c.drawCentredString(x + (box_width - 0.1*inch)/2, y_pos + 0.1*inch,
                           f"Correct: {correct}/{total}")

        # Percentage
        pct = stats_dict[key]['accuracy']
        c.setFont("Helvetica-Bold", 32)
        c.setFillColor(navy)
        c.drawCentredString(x + (box_width - 0.1*inch)/2, y_pos - 0.5*inch, f"{pct:.1f}%")

    # Middle section: I-Zone Calls
    y_pos = height - 3.5*inch
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)

    i_zone_headers = ["Overall I-Zone Calls", "I-Zone Calls vs LHP", "I-Zone Calls vs RHP",
                      "I-Zone Calls vs LHH", "I-Zone Calls vs RHH"]

    for i, header in enumerate(i_zone_headers):
        x = 0.75*inch + i * box_width
        key = ['overall', 'vs_lhp', 'vs_rhp', 'vs_lhh', 'vs_rhh'][i]
        missed = stats_dict[key].get('i_zone_miss', 0)

        c.drawCentredString(x + (box_width - 0.1*inch)/2, y_pos + 0.3*inch,
                           f"{header} – Miss: {missed}")

        # Insert I-Zone chart (even indices: 0, 2, 4, 6, 8)
        chart_index = i * 2
        chart_drawn = False
        if has_charts:
            chart_path = os.path.join(charts_dir, f"pitch-chart_{chart_index}.svg")
            chart_drawn = draw_chart(c, chart_path, x - 0.5*inch, y_pos - 2.0*inch,
                                    (box_width - 0.3*inch) * 2, 1.3*inch * 2)

        # Overlay second chart if provided (for overall page)
        if has_overlay:
            overlay_path = os.path.join(overlay_charts_dir, f"pitch-chart_{chart_index}.svg")
            if draw_chart(c, overlay_path, x - 0.5*inch, y_pos - 2.0*inch,
                         (box_width - 0.3*inch) * 2, 1.3*inch * 2):
                chart_drawn = True

        # Draw placeholder if no charts were rendered
        if not chart_drawn:
            c.setStrokeColor(colors.grey)
            c.rect(x - 0.5*inch, y_pos - 2.0*inch, (box_width - 0.3*inch) * 2, 1.3*inch * 2)

    # Bottom section: O-Zone Calls
    y_pos = height - 5.5*inch

    o_zone_headers = ["Overall O-Zone Calls", "O-Zone Calls vs LHP", "O-Zone Calls vs RHP",
                      "O-Zone Calls vs LHH", "O-Zone Calls vs RHH"]

    for i, header in enumerate(o_zone_headers):
        x = 0.75*inch + i * box_width
        key = ['overall', 'vs_lhp', 'vs_rhp', 'vs_lhh', 'vs_rhh'][i]
        missed = stats_dict[key].get('o_zone_miss', 0)
        avg_miss = stats_dict[key].get('avg_side_miss', 0.0)

        c.drawCentredString(x + (box_width - 0.1*inch)/2, y_pos + 0.3*inch,
                           f"{header} – Miss: {missed}")

        # Insert O-Zone chart (odd indices: 1, 3, 5, 7, 9)
        chart_index = i * 2 + 1
        chart_drawn = False
        if has_charts:
            chart_path = os.path.join(charts_dir, f"pitch-chart_{chart_index}.svg")
            chart_drawn = draw_chart(c, chart_path, x - 0.5*inch, y_pos - 2.0*inch,
                                    (box_width - 0.3*inch) * 2, 1.3*inch * 2)

        # Overlay second chart if provided (for overall page)
        if has_overlay:
            overlay_path = os.path.join(overlay_charts_dir, f"pitch-chart_{chart_index}.svg")
            if draw_chart(c, overlay_path, x - 0.5*inch, y_pos - 2.0*inch,
                         (box_width - 0.3*inch) * 2, 1.3*inch * 2):
                chart_drawn = True

        # Draw placeholder if no charts were rendered
        if not chart_drawn:
            c.setStrokeColor(colors.grey)
            c.rect(x - 0.5*inch, y_pos - 2.0*inch, (box_width - 0.3*inch) * 2, 1.3*inch * 2)


def generate_pdf(home_team, away_team, overall_stats, home_stats, away_stats,
                output_path, date_str, image_dir):
    """Generate the 3-page umpire report PDF"""
    c = canvas.Canvas(output_path, pagesize=landscape(letter))
    width, height = landscape(letter)

    # Page 1: Overall - overlay home and away team charts
    home_charts_dir = os.path.join(image_dir, "home")
    away_charts_dir = os.path.join(image_dir, "away")
    draw_page(c, "Overall", overall_stats, date_str, width, height, 1,
             charts_dir=home_charts_dir, overlay_charts_dir=away_charts_dir)
    c.showPage()

    # Page 2: Home team pitchers
    draw_page(c, f"{home_team} Pitchers", home_stats, date_str, width, height, 2, home_charts_dir)
    c.showPage()

    # Page 3: Away team pitchers
    draw_page(c, f"{away_team} Pitchers", away_stats, date_str, width, height, 3, away_charts_dir)

    c.save()
    print(f"\n✓ PDF generated: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate TruMedia umpire report")
    parser.add_argument('--home-team', required=True, help='Home team name')
    parser.add_argument('--home-team-id', required=True, help='Home team TruMedia ID')
    parser.add_argument('--away-team', required=True, help='Away team name')
    parser.add_argument('--away-team-id', required=True, help='Away team TruMedia ID')
    parser.add_argument('--start-date', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--season', type=int, default=2025, help='Season year')
    parser.add_argument('--output-dir', default='./reports', help='Output directory')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print("="*60)
    print("TruMedia Umpire Report Generator")
    print("="*60)
    print(f"Home Team: {args.home_team} ({args.home_team_id})")
    print(f"Away Team: {args.away_team} ({args.away_team_id})")
    print(f"Date Range: {args.start_date} to {args.end_date}")
    print("="*60)

    try:
        # Get token
        print("\n1. Getting TruMedia API token...")
        token = get_trumedia_token()
        print("   ✓ Token obtained")

        # Scrape visual charts
        print("\n2. Scraping visual charts from TruMedia...")
        image_dir = os.path.join(args.output_dir, "umpire_charts")
        os.makedirs(image_dir, exist_ok=True)

        scraper = TruMediaScraper(debug_port=CHROME_DEBUG_PORT, heat_map_png=True)
        try:
            scraper.connect()

            # Scrape home team charts (event.top) - will be used for both home page and overall overlay
            print("   - Home team charts (event.top)...")
            home_url = build_team_pitching_url(args.home_team, args.home_team_id,
                                              args.season, args.start_date, args.end_date, side="t")
            scraper.driver.get(home_url)
            time.sleep(3)
            home_charts = scraper.scrape_current_page(os.path.join(image_dir, "home"))
            print(f"      Captured {len(home_charts)} charts")

            # Scrape away team charts (event.bottom)
            print("   - Away team charts (event.bottom)...")
            away_url = build_team_pitching_url(args.away_team, args.away_team_id,
                                              args.season, args.start_date, args.end_date, side="b")
            scraper.driver.get(away_url)
            time.sleep(3)
            away_charts = scraper.scrape_current_page(os.path.join(image_dir, "away"))
            print(f"      Captured {len(away_charts)} charts")

            total_charts = len(home_charts) + len(away_charts)
            print(f"   ✓ Total charts captured: {total_charts}")
            print(f"      (Overall page will overlay home and away charts)")

        except Exception as e:
            print(f"   ⚠ Chart scraping failed: {e}")
            print("   Continuing without charts...")
        finally:
            scraper.close()

        # Fetch statistics
        print("\n3. Fetching umpire statistics from TruMedia API...")

        # Date filter
        date_filter = f"%20AND%20(game.gameDate%20%3E%3D%20'{args.start_date}')%20AND%20(game.gameDate%20%3C%3D%20'{args.end_date}%2023%3A59%3A59')"

        # Fetch stats for all three pages
        print("   - Overall (both teams, no side filter)...")
        overall_stats = build_stats_dict(token, [args.home_team_id, args.away_team_id], args.season, date_filter, side=None)

        print("   - Home team pitchers (event.bottom)...")
        home_stats = build_stats_dict(token, [args.home_team_id], args.season, date_filter, side="bottom")

        print("   - Away team pitchers (event.top)...")
        away_stats = build_stats_dict(token, [args.away_team_id], args.season, date_filter, side="top")

        print("   ✓ Statistics fetched successfully")

        # Generate PDF
        print("\n4. Generating PDF...")
        output_filename = f"Umpire_Report_{args.home_team}_{args.away_team}_{args.start_date}_to_{args.end_date}.pdf"
        output_filename = output_filename.replace(" ", "_")
        output_path = os.path.join(args.output_dir, output_filename)

        # Format date for display
        date_dt = datetime.strptime(args.start_date, "%Y-%m-%d")
        date_str = date_dt.strftime("%m/%d/%y")

        # Check chart files before generating PDF
        home_charts_dir = os.path.join(image_dir, "home")
        away_charts_dir = os.path.join(image_dir, "away")
        home_chart_count = len(os.listdir(home_charts_dir)) if os.path.exists(home_charts_dir) else 0
        away_chart_count = len(os.listdir(away_charts_dir)) if os.path.exists(away_charts_dir) else 0
        print(f"   Using {home_chart_count} home team charts, {away_chart_count} away team charts")

        generate_pdf(args.home_team, args.away_team, overall_stats, home_stats,
                    away_stats, output_path, date_str, image_dir)

        print("\n" + "="*60)
        print("✓ Complete!")
        print(f"📄 Report: {output_path}")
        print("="*60)

        # Output JSON result
        result = {
            "success": True,
            "pdfPath": output_filename,
            "homeTeam": args.home_team,
            "awayTeam": args.away_team,
            "dateRange": f"{args.start_date} to {args.end_date}"
        }
        print(f"\n__RESULT_JSON__:{json.dumps(result)}:__END_RESULT__")

    except Exception as e:
        error_msg = str(e)
        print(f"\nERROR: {error_msg}")
        result = {"success": False, "error": error_msg}
        print(f"\n__RESULT_JSON__:{json.dumps(result)}:__END_RESULT__")
        sys.exit(1)


if __name__ == "__main__":
    main()
