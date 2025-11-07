#!/usr/bin/env python3
"""
Integrated Pitching Report Generator with TruMedia Chart Scraping
Combines API data fetching, chart scraping, and PDF generation into one workflow
"""

import requests
import pandas as pd
import urllib.parse
from io import StringIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from datetime import datetime
import os
import sys
import argparse
import json
from PIL import Image as PILImage

from trumedia_scraper import TruMediaScraper

# Increase PIL's decompression bomb limit for large charts
PILImage.MAX_IMAGE_PIXELS = None  # Disable limit

# SVG to PNG conversion (optional but recommended)
try:
    import cairosvg
    CAIROSVG_AVAILABLE = True
except ImportError:
    CAIROSVG_AVAILABLE = False
    print("⚠️  cairosvg not available - SVGs will be converted using Pillow")
    print("   For better quality, install: pip install cairosvg")

# ==================== CONFIGURATION ====================
# Parse command-line arguments
parser = argparse.ArgumentParser(description='Generate pitching report with TruMedia data')
parser.add_argument('--player-name', required=True, help='Player name')
parser.add_argument('--player-id', required=True, help='TruMedia player ID')
parser.add_argument('--season', type=int, required=True, help='Season year (e.g., 2025)')
parser.add_argument('--start-date', required=True, help='Start date (YYYY-MM-DD)')
parser.add_argument('--end-date', required=True, help='End date (YYYY-MM-DD)')
parser.add_argument('--output-dir', default='.', help='Output directory for PDF')
parser.add_argument('--disable-scraping', action='store_true', help='Disable chart scraping')
args = parser.parse_args()

# Set configuration from args
PLAYER_NAME = args.player_name
PLAYER_ID = args.player_id
SEASON_YEAR = args.season
START_DATE = args.start_date
END_DATE = args.end_date
OUTPUT_FILE = os.path.join(args.output_dir, f"{PLAYER_NAME}_{START_DATE}_to_{END_DATE}_Pitching_Report.pdf")

# API Configuration from environment variables
USERNAME = os.getenv("TRUMEDIA_USERNAME", "Justin.Graham@afacademy.af.edu")
SITENAME = os.getenv("TRUMEDIA_SITENAME", "airforce-ncaabaseball")
MASTER_TOKEN = os.getenv("TRUMEDIA_MASTER_TOKEN", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiZjZlZWEwYzViZmUwZTY4ZmEwZDUyMGQyMDU2NTNmYzciLCJpYXQiOjE3NTc0MjE1NjF9.p940yyxhsJZp_gZFX-4Y4U48WqZrvbylDyY8Oj2u9q0")
TEAM_ID = os.getenv("TRUMEDIA_TEAM_ID", "4806")

# Chrome debugging configuration
CHROME_DEBUG_PORT = int(os.getenv("CHROME_DEBUG_PORT", "9222"))
CHARTS_DIR = os.path.join(args.output_dir, "trumedia_charts")

# Feature flags
ENABLE_CHART_SCRAPING = not args.disable_scraping

# ==================== API FUNCTIONS ====================
def log(msg, level="INFO"):
    """Print log message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {level}: {msg}")

def normalize_columns(df):
    """Strip whitespace from API column names so downstream lookups succeed."""
    df.columns = [col.strip() for col in df.columns]
    return df

def build_pitch_filter(pitch_type_filter, start_date=None, end_date=None):
    """Return encoded filter string; for season omit date range per TruMedia requirements."""
    if start_date and end_date:
        date_filter = (
            f"(game.gameDate%20%3E%3D%20'{start_date}')%20AND%20"
            f"(game.gameDate%20%3C%3D%20'{end_date}%2023%3A59%3A59')"
        )
        return f"&filters=({date_filter}%20AND%20({pitch_type_filter}))"
    return f"&filters=({pitch_type_filter})"

def get_series(df, *names):
    """Return the first matching column Series from a DataFrame."""
    if df is None or df.empty:
        return None
    for name in names:
        if name in df.columns:
            return df[name]
    return None

def get_token():
    """Get temporary API token"""
    try:
        url = "https://api.trumedianetworks.com/v1/siteadmin/api/createTempPBToken"
        response = requests.post(url, json={"username": USERNAME, "sitename": SITENAME, "token": MASTER_TOKEN})
        response.raise_for_status()
        return response.json()["pbTempToken"]
    except Exception as e:
        log(f"Failed to get token: {e}", "ERROR")
        raise

def fetch_pitch_data_by_type(player_id, season_year, start_date, end_date, token, pitch_type_name, pitch_type_filter):
    """Fetch pitch metrics for a specific pitch type group"""
    columns = "[Vel],[VelMax],[Spin],[IndVertBrk],[HorzBrk],[RelX],[RelZ],[Extension],[Tilt]"
    format_type = "RAW"
    columns_encoded = urllib.parse.quote(columns)

    filters = build_pitch_filter(pitch_type_filter, start_date, end_date)

    api_url = (
        f"https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/PlayerGames.csv"
        f"?seasonYear={season_year}&playerId={player_id}&columns={columns_encoded}&token={token}"
        f"&format={format_type}{filters}"
    )

    try:
        response = requests.get(api_url)
        if response.status_code == 200 and response.text.strip():
            data = pd.read_csv(StringIO(response.text))
            data = normalize_columns(data)
            if not data.empty:
                data['pitch_type_name'] = pitch_type_name
                log(f"  ✓ {pitch_type_name} current: {len(data)} rows")
                return data
    except Exception as e:
        log(f"  ⚠️  {pitch_type_name} current: No data", "WARN")

    return pd.DataFrame()

def fetch_pitch_data(player_id, season_year, start_date, end_date, token):
    """Fetch pitch metrics for all pitch types (date range)"""
    log(f"Fetching pitch data for {start_date} to {end_date}...")

    pitch_types = {
        'Fastball': "(event.pitchType%20IN%20('FA'%2C'FF'))%20OR%20(event.pitchType%20IN%20('SI'%2C%20'FT'))",
        'Cutter': "(event.pitchType%20%3D%20'FC')",
        'Slider': "(event.pitchType%20IN%20('SL'))",
        'Curveball': "(event.pitchType%20IN%20('CU'%2C'CS'%2C'KC'))",
        'Changeup': "(event.pitchType%20%3D%20'CH')"
    }

    all_data = []
    for name, filter_str in pitch_types.items():
        data = fetch_pitch_data_by_type(player_id, season_year, start_date, end_date, token, name, filter_str)
        if not data.empty:
            all_data.append(data)

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        log(f"✓ Date range data: {len(combined)} total pitches")
        return combined

    log("⚠️  No pitch data found for date range", "WARN")
    return pd.DataFrame()

def fetch_season_data_by_type(player_id, season_year, token, pitch_type_name, pitch_type_filter):
    """Fetch season pitch metrics for a specific pitch type"""
    columns = "[Vel],[VelMax],[Spin],[IndVertBrk],[HorzBrk],[RelX],[RelZ],[Extension],[Tilt]"
    format_type = "RAW"
    columns_encoded = urllib.parse.quote(columns)
    filters = build_pitch_filter(pitch_type_filter)

    api_url = (
        f"https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/PlayerGames.csv"
        f"?seasonYear={season_year}&playerId={player_id}&columns={columns_encoded}&token={token}"
        f"&format={format_type}{filters}"
    )

    try:
        response = requests.get(api_url)
        if response.status_code == 200 and response.text.strip():
            data = pd.read_csv(StringIO(response.text))
            data = normalize_columns(data)
            if not data.empty:
                data['pitch_type_name'] = pitch_type_name
                log(f"  ✓ {pitch_type_name} season: {len(data)} rows")
                return data
    except Exception as e:
        log(f"  ⚠️  {pitch_type_name} season: No data", "WARN")

    return pd.DataFrame()

def fetch_season_data(player_id, season_year, token):
    """Fetch season pitch metrics for all pitch types"""
    log("Fetching season pitch data...")

    pitch_types = {
        'Fastball': "(event.pitchType%20IN%20('FA'%2C'FF'))%20OR%20(event.pitchType%20IN%20('SI'%2C%20'FT'))",
        'Cutter': "(event.pitchType%20%3D%20'FC')",
        'Slider': "(event.pitchType%20IN%20('SL'))",
        'Curveball': "(event.pitchType%20IN%20('CU'%2C'CS'%2C'KC'))",
        'Changeup': "(event.pitchType%20%3D%20'CH')"
    }

    all_data = []
    for name, filter_str in pitch_types.items():
        data = fetch_season_data_by_type(player_id, season_year, token, name, filter_str)
        if not data.empty:
            all_data.append(data)

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        log(f"✓ Season data: {len(combined)} total pitches")
        return combined

    log("⚠️  No season data found", "WARN")
    return pd.DataFrame()

def fetch_summary_stats(player_id, season_year, start_date, end_date, token):
    """Fetch summary statistics for the date range"""
    log("Fetching summary stats...")

    columns = "[IP],[BF],[P|PIT],[FPStk%|PIT],[Swing%|PIT],[SwStrk%|PIT],[K%|PIT],[BB%|PIT],[K/BB|PIT]"
    format_type = "RAW"
    columns_encoded = urllib.parse.quote(columns)
    filters = f"&filters=((game.gameDate%20%3E%3D%20'{start_date}')%20AND%20(game.gameDate%20%3C%3D%20'{end_date}%2023%3A59%3A59'))"

    api_url = (
        f"https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/PlayerGames.csv"
        f"?seasonYear={season_year}&playerId={player_id}&columns={columns_encoded}&token={token}"
        f"&format={format_type}{filters}"
    )

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = pd.read_csv(StringIO(response.text))
        data = normalize_columns(data)

        if not data.empty:
            log(f"✓ Summary stats fetched")
            return data
        else:
            log("⚠️  Summary stats empty", "WARN")
            return pd.DataFrame()
    except Exception as e:
        log(f"❌ Failed to fetch summary stats: {e}", "ERROR")
        return pd.DataFrame()

def fetch_attack_finish_stats(player_id, season_year, start_date, end_date, token):
    """Fetch attack and finish zone percentages"""
    log("Fetching attack/finish stats...")

    format_type = "RAW"

    # Attack zone: 0-0 or 0-1 counts
    attack_column = "[InZone%|PIT]"
    attack_filters = f"&filters=(((event.balls%20%3D%200%20AND%20event.strikes%20%3D%200)%20OR%20(event.balls%20%3D%200%20AND%20event.strikes%20%3D%201))%20AND%20(game.gameDate%20%3E%3D%20'{start_date}')%20AND%20(game.gameDate%20%3C%3D%20'{end_date}%2023%3A59%3A59'))"
    attack_url = (
        f"https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/PlayerGames.csv"
        f"?seasonYear={season_year}&playerId={player_id}&columns={urllib.parse.quote(attack_column)}&token={token}"
        f"&format={format_type}{attack_filters}"
    )

    # Finish zone: 0-2, 1-2, or 2-2 counts
    finish_column = "[Strike%|PIT]"
    finish_filters = f"&filters=(((event.balls%20%3D%200%20AND%20event.strikes%20%3D%202)%20OR%20(event.balls%20%3D%201%20AND%20event.strikes%20%3D%202)%20OR%20(event.balls%20%3D%202%20AND%20event.strikes%20%3D%202))%20AND%20(game.gameDate%20%3E%3D%20'{start_date}')%20AND%20(game.gameDate%20%3C%3D%20'{end_date}%2023%3A59%3A59'))"
    finish_url = (
        f"https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/PlayerGames.csv"
        f"?seasonYear={season_year}&playerId={player_id}&columns={urllib.parse.quote(finish_column)}&token={token}"
        f"&format={format_type}{finish_filters}"
    )

    attack_pct = 0
    finish_pct = 0

    try:
        attack_data = pd.read_csv(attack_url)
        attack_data = normalize_columns(attack_data)
        log(f"  Attack columns: {list(attack_data.columns)}")
        if attack_data.empty:
            log("  Attack data empty after fetch", "WARN")
        attack_series_raw = get_series(attack_data, "InZone%|PIT", "InZone%")
        if attack_series_raw is not None:
            log(f"  Attack sample: {attack_data.head().to_dict(orient='records')}")
            raw = attack_series_raw.astype(str).str.replace('%', '', regex=False)
            attack_series = pd.to_numeric(raw, errors='coerce').dropna()
            log(f"  Attack parsed series: {attack_series.tolist()}")
            if not attack_series.empty:
                attack_pct = attack_series.mean()
                log(f"  ✓ Attack%: {attack_pct:.1f}")
    except Exception as e:
        log(f"  ⚠️  Attack zone: No data", "WARN")

    try:
        finish_data = pd.read_csv(finish_url)
        finish_data = normalize_columns(finish_data)
        log(f"  Finish columns: {list(finish_data.columns)}")
        if finish_data.empty:
            log("  Finish data empty after fetch", "WARN")
        finish_series_raw = get_series(finish_data, "Strike%|PIT", "Strike%")
        if finish_series_raw is not None:
            log(f"  Finish sample: {finish_data.head().to_dict(orient='records')}")
            raw = finish_series_raw.astype(str).str.replace('%', '', regex=False)
            finish_series = pd.to_numeric(raw, errors='coerce').dropna()
            log(f"  Finish parsed series: {finish_series.tolist()}")
            if not finish_series.empty:
                finish_pct = finish_series.mean()
                log(f"  ✓ Finish%: {finish_pct:.1f}")
    except Exception as e:
        log(f"  ⚠️  Finish zone: No data", "WARN")

    return attack_pct, finish_pct

def fetch_page2_stats_by_type(player_id, season_year, start_date, end_date, token, pitch_type_name, pitch_type_filter, is_season=False):
    """Fetch page 2 statistics for a specific pitch type"""
    columns = "[P|PIT],[Strike%|PIT],[InZone%|PIT],[SwStrk%|PIT],[Chase%|PIT],[Miss%|PIT]"
    format_type = "RAW"
    columns_encoded = urllib.parse.quote(columns)

    filters = build_pitch_filter(pitch_type_filter, None if is_season else start_date, None if is_season else end_date)

    api_url = (
        f"https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/PlayerGames.csv"
        f"?seasonYear={season_year}&playerId={player_id}&columns={columns_encoded}&token={token}"
        f"&format={format_type}{filters}"
    )

    try:
        response = requests.get(api_url)
        if response.status_code == 200 and response.text.strip():
            data = pd.read_csv(StringIO(response.text))
            data = normalize_columns(data)
            if not data.empty:
                data['pitch_type_name'] = pitch_type_name
                return data
    except Exception as e:
        pass

    return pd.DataFrame()

def fetch_page2_stats(player_id, season_year, start_date, end_date, token):
    """Fetch page 2 statistics for all pitch types"""
    log("Fetching page 2 stats...")

    pitch_types = {
        'Fastball': "(event.pitchType%20IN%20('FA'%2C'FF'))%20OR%20(event.pitchType%20IN%20('SI'%2C%20'FT'))",
        'Cutter': "(event.pitchType%20%3D%20'FC')",
        'Slider': "(event.pitchType%20IN%20('SL'))",
        'Curveball': "(event.pitchType%20IN%20('CU'%2C'CS'%2C'KC'))",
        'Changeup': "(event.pitchType%20%3D%20'CH')"
    }

    current_data_all = []
    season_data_all = []

    for name, filter_str in pitch_types.items():
        current = fetch_page2_stats_by_type(player_id, season_year, start_date, end_date, token, name, filter_str, is_season=False)
        if not current.empty:
            current_data_all.append(current)

        season = fetch_page2_stats_by_type(player_id, season_year, start_date, end_date, token, name, filter_str, is_season=True)
        if not season.empty:
            season_data_all.append(season)

    current_df = pd.concat(current_data_all, ignore_index=True) if current_data_all else pd.DataFrame()
    season_df = pd.concat(season_data_all, ignore_index=True) if season_data_all else pd.DataFrame()

    if not current_df.empty:
        log(f"✓ Page 2 current data: {len(current_df)} rows")
    if not season_df.empty:
        log(f"✓ Page 2 season data: {len(season_df)} rows")

    return current_df, season_df

# ==================== DATA PROCESSING ====================
def calculate_pitch_stats(data):
    """Calculate aggregated stats by pitch type"""
    if data.empty or 'pitch_type_name' not in data.columns:
        return {}

    stats = {}
    for pitch_type in data['pitch_type_name'].dropna().unique():
        subset = data[data['pitch_type_name'] == pitch_type]

        stats[pitch_type] = {
            'Vel': subset['Vel'].mean() if 'Vel' in subset.columns else 0,
            'MxVel': subset['VelMax'].max() if 'VelMax' in subset.columns else 0,
            'Spin': subset['Spin'].mean() if 'Spin' in subset.columns else 0,
            'IndVertBrk': subset['IndVertBrk'].mean() if 'IndVertBrk' in subset.columns else 0,
            'HorzBrk': subset['HorzBrk'].mean() if 'HorzBrk' in subset.columns else 0,
            'RelX': subset['RelX'].mean() if 'RelX' in subset.columns else 0,
            'RelZ': subset['RelZ'].mean() if 'RelZ' in subset.columns else 0,
            'Extension': subset['Extension'].mean() if 'Extension' in subset.columns else 0,
            'Tilt': subset['Tilt'].iloc[0] if 'Tilt' in subset.columns and len(subset) > 0 else 'N/A',
        }

    return stats

def format_stat(value, decimals=1, blank_if_zero=False):
    """Format stat value, handling NaN, None, and zero"""
    if pd.isna(value) or value == 'nan' or value is None or value == 'N/A':
        return ''
    if isinstance(value, str):
        return value if value.lower() != 'nan' else ''
    if isinstance(value, (int, float)):
        if blank_if_zero and value == 0.0:
            return ''
        return f"{int(value)}" if decimals == 0 else f"{value:.{decimals}f}"
    return str(value)

def format_percentage(value, decimals=1):
    """Format percentage value, scaling ratios (0-1) up to 0-100."""
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except TypeError:
        pass
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ''
    if 0 <= number <= 1:
        number *= 100
    return f"{number:.{decimals}f}%"

# ==================== IMAGE CONVERSION ====================
def svg_to_image(svg_path, output_path=None, target_width_inches=None, target_height_inches=None):
    """Convert SVG to PNG for PDF embedding with reasonable dimensions"""
    if output_path is None:
        output_path = svg_path.replace('.svg', '.png')

    # Use 150 DPI for good quality without excessive file size
    DPI = 150

    # Calculate pixel dimensions (cap at reasonable maximums)
    max_width_px = 1200  # Max width in pixels
    max_height_px = 1200  # Max height in pixels

    if target_width_inches and target_height_inches:
        width_px = min(int(target_width_inches * DPI), max_width_px)
        height_px = min(int(target_height_inches * DPI), max_height_px)
    else:
        width_px = 800
        height_px = 800

    try:
        if CAIROSVG_AVAILABLE:
            # Use cairosvg for high-quality conversion
            cairosvg.svg2png(
                url=svg_path,
                write_to=output_path,
                output_width=width_px,
                output_height=height_px,
                dpi=DPI
            )

            # Optimize the PNG file size
            try:
                img = PILImage.open(output_path)
                # Convert to RGB if needed and optimize
                if img.mode == 'RGBA':
                    # Create white background
                    bg = PILImage.new('RGB', img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                    img = bg
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # Save optimized version
                img.save(output_path, 'PNG', optimize=True)
                img.close()
            except Exception as opt_error:
                log(f"  ⚠️  Could not optimize PNG: {opt_error}", "WARN")
        else:
            # Without cairosvg, we can't convert SVG properly
            # Try using svglib as a fallback
            try:
                from svglib.svglib import svg2rlg
                from reportlab.graphics import renderPM

                drawing = svg2rlg(svg_path)
                renderPM.drawToFile(drawing, output_path, fmt='PNG', dpi=DPI)
            except ImportError:
                log(f"⚠️  Neither cairosvg nor svglib available for SVG conversion", "WARN")
                return None

        return output_path
    except Exception as e:
        log(f"Failed to convert {svg_path}: {e}", "ERROR")
        return None

# ==================== PDF GENERATION ====================
def create_placeholder(w, h, label, color=colors.HexColor('#E8F4F8')):
    """Create a placeholder box for visualizations"""
    t = Table([[label]], colWidths=[w], rowHeights=[h])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), color),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#666666')),
    ]))
    return t

def create_chart_element(chart_name, chart_path, width, height):
    """Create a chart element for PDF (either image or placeholder)"""
    log(f"Loading chart '{chart_name}': path={chart_path}")
    if chart_path and os.path.exists(chart_path):
        log(f"  ✓ Chart file found: {chart_name}")
        try:
            # Convert SVG to PNG if needed
            if chart_path.endswith('.svg'):
                # Clean up old PNG if it exists
                png_path = chart_path.replace('.svg', '.png')
                if os.path.exists(png_path):
                    os.remove(png_path)
                    log(f"  Removed old PNG: {os.path.basename(png_path)}")

                # Convert with optimized settings
                png_path = svg_to_image(chart_path,
                                       target_width_inches=width/inch,
                                       target_height_inches=height/inch)
                if png_path:
                    file_size = os.path.getsize(png_path) / 1024
                    log(f"  ✓ Converted {os.path.basename(chart_path)} -> {file_size:.1f} KB")
                    chart_path = png_path
                else:
                    log(f"  ⚠️  Conversion failed for {chart_name}", "WARN")
                    return create_placeholder(width, height, f"{chart_name}\n(Conversion Failed)")

            # Load and resize image
            img = Image(chart_path, width=width, height=height)
            return img
        except Exception as e:
            log(f"  ❌ Failed to load chart {chart_name}: {e}", "ERROR")
            return create_placeholder(width, height, f"{chart_name}\n(Load Failed)")
    else:
        log(f"  ⚠️  Chart not found: {chart_name} (path: {chart_path})", "WARN")
        return create_placeholder(width, height, f"{chart_name}\n(Not Found)")

def generate_report(scraped_charts=None):
    """Generate complete PDF report with optional scraped charts"""
    log(f"=" * 60)
    log(f"PITCHING REPORT GENERATOR")
    log(f"=" * 60)
    log(f"Player: {PLAYER_NAME} (ID: {PLAYER_ID})")
    log(f"Date Range: {START_DATE} to {END_DATE}")
    log(f"Season: {SEASON_YEAR}")
    log(f"=" * 60)

    # Get API token
    token = get_token()
    log("✓ API token obtained")

    # Fetch all data
    current_data = fetch_pitch_data(PLAYER_ID, SEASON_YEAR, START_DATE, END_DATE, token)
    season_data = fetch_season_data(PLAYER_ID, SEASON_YEAR, token)
    summary_data = fetch_summary_stats(PLAYER_ID, SEASON_YEAR, START_DATE, END_DATE, token)
    attack_pct, finish_pct = fetch_attack_finish_stats(PLAYER_ID, SEASON_YEAR, START_DATE, END_DATE, token)
    page2_current, page2_season = fetch_page2_stats(PLAYER_ID, SEASON_YEAR, START_DATE, END_DATE, token)

    # Debug logging
    if not summary_data.empty:
        log(f"DEBUG Summary: {summary_data.iloc[0].to_dict()}")
    if not page2_current.empty:
        log(f"DEBUG Page2 Sample:\n{page2_current.head()}")

    # Calculate pitch statistics
    current_stats = calculate_pitch_stats(current_data)
    season_stats = calculate_pitch_stats(season_data)

    log(f"\n" + "=" * 60)
    log(f"DATA SUMMARY")
    log(f"=" * 60)
    log(f"Current game pitches: {len(current_data)}")
    log(f"Season pitches: {len(season_data)}")
    log(f"Pitch types (current): {list(current_stats.keys())}")
    log(f"Pitch types (season): {list(season_stats.keys())}")
    log(f"=" * 60 + "\n")

    # Map scraped charts
    chart_map = {}
    if scraped_charts:
        log(f"✓ Scraped {len(scraped_charts)} charts:")
        for chart_name, chart_path in scraped_charts:
            exists = os.path.exists(chart_path)
            log(f"  - {chart_name}: {chart_path}")
            log(f"    File exists: {exists}")
            chart_map[chart_name] = chart_path
        log(f"Chart map keys: {list(chart_map.keys())}")
    else:
        log("⚠️ No charts were scraped", "WARN")

    # Create PDF
    log("Building PDF...")
    pdf = SimpleDocTemplate(OUTPUT_FILE, pagesize=letter,
                           rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    # ==================== PAGE 1 ====================

    # Header: Logo | Title+Date | Photo (all same row)
    title_style = ParagraphStyle('Title', parent=styles['Heading1'],
                                fontSize=24, textColor=colors.HexColor('#003366'),
                                alignment=TA_CENTER, spaceAfter=6)
    date_style = ParagraphStyle('Date', parent=styles['Normal'],
                               alignment=TA_CENTER, fontSize=12)
    start_formatted = datetime.strptime(START_DATE, '%Y-%m-%d').strftime('%B %d, %Y')
    end_formatted = datetime.strptime(END_DATE, '%Y-%m-%d').strftime('%B %d, %Y')
    formatted_date = f"{start_formatted} - {end_formatted}" if START_DATE != END_DATE else start_formatted

    # Create title and date as nested table
    title_content = Table([
        [Paragraph(f"{PLAYER_NAME} Pitching Report", title_style)],
        [Paragraph(formatted_date, date_style)]
    ])
    title_content.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'),
                                       ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))

    # Load AF logo
    logo_path = "/Users/justin/AFBaseball/AF_logo.png"
    logo_size = 0.96 * inch
    logo = Image(logo_path, width=logo_size, height=logo_size) if os.path.exists(logo_path) else create_placeholder(logo_size, logo_size, "Logo")

    header = [[logo, title_content, create_placeholder(logo_size, logo_size, "Player Photo")]]
    header_table = Table(header, colWidths=[1.4*inch, 4.8*inch, 1.4*inch])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*inch))

    # ==================== PITCH STATS TABLE ====================
    stats_header = ['Pitch', 'Time', 'Vel', 'MxVel', 'Spin', 'IndVertBrk', 'HorzBrk', 'RelX', 'RelZ', 'Extension', 'Tilt']
    stats_data = [stats_header]

    all_pitch_types = sorted(set(list(current_stats.keys()) + list(season_stats.keys())))

    for pitch_type in all_pitch_types:
        if pitch_type in current_stats:
            s = current_stats[pitch_type]
            stats_data.append([
                pitch_type, 'Current',
                format_stat(s['Vel'], 1), format_stat(s['MxVel'], 1),
                format_stat(s['Spin'], 0), format_stat(s['IndVertBrk'], 1),
                format_stat(s['HorzBrk'], 1), format_stat(s['RelX'], 1, blank_if_zero=True),
                format_stat(s['RelZ'], 1, blank_if_zero=True), format_stat(s['Extension'], 2),
                format_stat(s['Tilt'])
            ])

        if pitch_type in season_stats:
            s = season_stats[pitch_type]
            stats_data.append([
                pitch_type, 'Season',
                format_stat(s['Vel'], 1), format_stat(s['MxVel'], 1),
                format_stat(s['Spin'], 0), format_stat(s['IndVertBrk'], 1),
                format_stat(s['HorzBrk'], 1), format_stat(s['RelX'], 1, blank_if_zero=True),
                format_stat(s['RelZ'], 1, blank_if_zero=True), format_stat(s['Extension'], 2),
                format_stat(s['Tilt'])
            ])

    if len(stats_data) == 1:
        stats_data.append(['No data available'] + [''] * 10)

    stats_table = Table(stats_data, repeatRows=1)
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F5F5F5')]),
    ]))
    elements.append(stats_table)
    elements.append(Spacer(1, 0.3*inch))

    # ==================== VISUALIZATIONS ====================
    viz = [[
        create_chart_element("Pitch Movement", chart_map.get('pitch-break-chart'), 2.2*inch, 2.2*inch),
        create_chart_element("Tilt by Type", chart_map.get('radial-histogram-chart'), 2.2*inch, 2.2*inch),
        create_chart_element("Heat Map", chart_map.get('heat-map'), 2.2*inch, 2.2*inch)
    ]]
    viz_table = Table(viz, colWidths=[2.3*inch]*3, hAlign='CENTER')
    elements.append(viz_table)
    elements.append(Spacer(1, 0.2*inch))

    # ==================== ZONE CHARTS ====================
    zones = [[
        create_chart_element("All Pitches", chart_map.get('pitch-chart_0'), 1.6*inch, 1.6*inch),
        create_chart_element("Attack Zone", chart_map.get('pitch-chart_1'), 1.6*inch, 1.6*inch),
        create_chart_element("Finish Zone", chart_map.get('pitch-chart_2'), 1.6*inch, 1.6*inch),
        create_chart_element("Swing & Miss", chart_map.get('pitch-chart_3'), 1.6*inch, 1.6*inch)
    ]]
    zone_title_style = ParagraphStyle('ZoneTitle', parent=styles['Normal'], alignment=TA_CENTER, fontName='Helvetica-Bold', fontSize=10)
    zone_titles = Table([[Paragraph("All Pitches", zone_title_style),
                          Paragraph("Attack", zone_title_style),
                          Paragraph("Finish", zone_title_style),
                          Paragraph("Swing and Miss", zone_title_style)]],
                        colWidths=[1.85*inch]*4, hAlign='CENTER')
    zone_titles.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    zones_table = Table(zones, colWidths=[1.85*inch]*4, hAlign='CENTER')
    elements.append(zone_titles)
    elements.append(zones_table)
    elements.append(Spacer(1, 0.3*inch))

    # ==================== SUMMARY STATS TABLE ====================
    summary_header = ['IP', 'BF', 'Pitches', 'FPS%', 'Swing%', 'SwStk%', 'Attack%', 'Finish%', 'K%', 'BB%', 'K-BB']

    if not summary_data.empty:
        ip_series = get_series(summary_data, "IP")
        bf_series = get_series(summary_data, "BF")
        pitches_series = get_series(summary_data, "P|PIT", "P")
        fps_series = get_series(summary_data, "FPStk%|PIT", "FPStk%")
        swing_series = get_series(summary_data, "Swing%|PIT", "Swing%")
        swstk_series = get_series(summary_data, "SwStrk%|PIT", "SwStrk%")
        k_series = get_series(summary_data, "K%|PIT", "K%")
        bb_series = get_series(summary_data, "BB%|PIT", "BB%")
        kbb_series = get_series(summary_data, "K/BB|PIT", "K/BB")

        ip = ip_series.sum() if ip_series is not None else 0
        bf = bf_series.sum() if bf_series is not None else 0
        pitches = pitches_series.sum() if pitches_series is not None else len(current_data)
        fps = fps_series.mean() if fps_series is not None else 0
        swing = swing_series.mean() if swing_series is not None else 0
        swstk = swstk_series.mean() if swstk_series is not None else 0
        k_pct = k_series.mean() if k_series is not None else 0
        bb_pct = bb_series.mean() if bb_series is not None else 0
        k_bb = kbb_series.mean() if kbb_series is not None else 0
    else:
        ip = bf = pitches = fps = swing = swstk = k_pct = bb_pct = k_bb = 0
        pitches = len(current_data)

    log(f"Summary attack before format: {attack_pct}")
    log(f"Summary finish before format: {finish_pct}")

    summary_values = [
        format_stat(ip, 1),
        format_stat(bf, 0),
        format_stat(pitches, 0),
        format_percentage(fps, 0),
        format_percentage(swing, 0),
        format_percentage(swstk, 0),
        format_percentage(attack_pct, 0),
        format_percentage(finish_pct, 0),
        format_percentage(k_pct, 1),
        format_percentage(bb_pct, 1),
        format_stat(k_bb, 1)
    ]

    goals = ['Goals', '', '', '70%', '50%', '15%', '60%', '75%', '25%', '10%', '5']

    summary_table_data = [summary_header, summary_values, goals]
    summary_table = Table(summary_table_data)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BACKGROUND', (0,1), (-1,1), colors.lightblue),
        ('BACKGROUND', (0,2), (-1,2), colors.lightgreen),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
    ]))
    elements.append(summary_table)

    # ==================== PAGE 2 ====================
    elements.append(PageBreak())

    elements.append(Paragraph(f"{PLAYER_NAME} Pitching Report", title_style))
    elements.append(Paragraph(formatted_date, date_style))
    elements.append(Spacer(1, 0.3*inch))

    # ==================== PAGE 2 STATS TABLE ====================
    page2_header = ['Pitch', 'Time', 'P', 'Strike%', 'InZone%', 'SwStrk%', 'Chase%', 'Miss%']
    page2_data = [page2_header]

    pitch_types_p2 = set()
    if not page2_current.empty and 'pitch_type_name' in page2_current.columns:
        pitch_types_p2.update(page2_current['pitch_type_name'].unique())
    if not page2_season.empty and 'pitch_type_name' in page2_season.columns:
        pitch_types_p2.update(page2_season['pitch_type_name'].unique())

    for pitch_type in sorted(pitch_types_p2):
        if not page2_current.empty and 'pitch_type_name' in page2_current.columns:
            curr_subset = page2_current[page2_current['pitch_type_name'] == pitch_type]
            if not curr_subset.empty:
                # Aggregate current game data (sum pitches, mean percentages)
                p_series = get_series(curr_subset, "P|PIT", "P")
                strike_series = get_series(curr_subset, "Strike%|PIT", "Strike%")
                inzone_series = get_series(curr_subset, "InZone%|PIT", "InZone%")
                swstrk_series = get_series(curr_subset, "SwStrk%|PIT", "SwStrk%")
                chase_series = get_series(curr_subset, "Chase%|PIT", "Chase%")
                miss_series = get_series(curr_subset, "Miss%|PIT", "Miss%")

                p_val = p_series.sum() if p_series is not None else None
                strike_val = strike_series.mean() if strike_series is not None else None
                inzone_val = inzone_series.mean() if inzone_series is not None else None
                swstrk_val = swstrk_series.mean() if swstrk_series is not None else None
                chase_val = chase_series.mean() if chase_series is not None else None
                miss_val = miss_series.mean() if miss_series is not None else None

                page2_data.append([
                    pitch_type, 'Current',
                    format_stat(p_val, 0),
                    format_percentage(strike_val, 0),
                    format_percentage(inzone_val, 0),
                    format_percentage(swstrk_val, 0),
                    format_percentage(chase_val, 0),
                    format_percentage(miss_val, 0),
                ])

        if not page2_season.empty and 'pitch_type_name' in page2_season.columns:
            season_subset = page2_season[page2_season['pitch_type_name'] == pitch_type]
            if not season_subset.empty:
                # Average across all season games
                p_series = get_series(season_subset, "P|PIT", "P")
                strike_series = get_series(season_subset, "Strike%|PIT", "Strike%")
                inzone_series = get_series(season_subset, "InZone%|PIT", "InZone%")
                swstrk_series = get_series(season_subset, "SwStrk%|PIT", "SwStrk%")
                chase_series = get_series(season_subset, "Chase%|PIT", "Chase%")
                miss_series = get_series(season_subset, "Miss%|PIT", "Miss%")

                p_val = p_series.sum() if p_series is not None else None
                strike_val = strike_series.mean() if strike_series is not None else None
                inzone_val = inzone_series.mean() if inzone_series is not None else None
                swstrk_val = swstrk_series.mean() if swstrk_series is not None else None
                chase_val = chase_series.mean() if chase_series is not None else None
                miss_val = miss_series.mean() if miss_series is not None else None

                page2_data.append([
                    pitch_type, 'Season',
                    format_stat(p_val, 0),
                    format_percentage(strike_val, 0),
                    format_percentage(inzone_val, 0),
                    format_percentage(swstrk_val, 0),
                    format_percentage(chase_val, 0),
                    format_percentage(miss_val, 0),
                ])

    if len(page2_data) == 1:
        page2_data.append(['No data available'] + [''] * 7)

    page2_table = Table(page2_data, repeatRows=1)
    page2_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F5F5F5')]),
    ]))
    elements.append(page2_table)
    elements.append(Spacer(1, 0.3*inch))

    # ==================== PAGE 2 VISUALIZATIONS ====================
    viz2 = [[
        create_chart_element("Pitch Release", chart_map.get('release-point-chart'), 2.2*inch, 2.2*inch),
        create_chart_element("Pitch Usage", chart_map.get('pie-chart'), 2.2*inch, 2.2*inch),
        create_chart_element("Extension View", chart_map.get('extension-point-chart'), 2.2*inch, 2.2*inch)
    ]]
    viz2_table = Table(viz2, colWidths=[2.3*inch]*3, hAlign='CENTER')
    elements.append(viz2_table)

    # Build PDF
    pdf.build(elements)

    log(f"\n" + "=" * 60)
    log(f"✅ REPORT GENERATED SUCCESSFULLY")
    log(f"=" * 60)
    log(f"Output file: {OUTPUT_FILE}")
    log(f"File size: {os.path.getsize(OUTPUT_FILE) / 1024:.1f} KB")
    log(f"=" * 60 + "\n")

def scrape_charts():
    """Capture TruMedia charts via the shared scraper module."""
    scraper = TruMediaScraper(debug_port=CHROME_DEBUG_PORT)
    try:
        scraper.connect()
        _, captured = scraper.scrape_player(
            player_name=PLAYER_NAME,
            player_id=PLAYER_ID,
            start_date=START_DATE,
            end_date=END_DATE,
            output_dir=CHARTS_DIR,
        )
        captured = captured or []
        return [
            (os.path.splitext(os.path.basename(path))[0], path)
            for path in captured
        ]
    finally:
        scraper.close()

# ==================== MAIN WORKFLOW ====================
def main():
    """Main workflow: optional chart scrape + PDF generation."""
    try:
        log(f"\n{'='*60}")
        log("INTEGRATED PITCHING REPORT GENERATOR")
        log(f"{'='*60}\n")

        scraped_charts = None
        if ENABLE_CHART_SCRAPING:
            try:
                scraped_charts = scrape_charts()
            except Exception as exc:  # pylint: disable=broad-except
                log(f"Chart scraping failed: {exc}", "ERROR")

        generate_report(scraped_charts)
        log("\n✅ Complete! Your pitching report is ready.")

        # Output JSON result for API consumption
        result = {
            'success': True,
            'pdfPath': OUTPUT_FILE
        }
        print(f"\n__RESULT_JSON__:{json.dumps(result)}:__END_RESULT__")

        return 0

    except Exception as exc:  # pylint: disable=broad-except
        log(f"\n❌ ERROR: {exc}", "ERROR")
        import traceback  # Local import keeps top simple
        traceback.print_exc()

        error_result = {
            'success': False,
            'error': str(exc)
        }
        print(f"\n__RESULT_JSON__:{json.dumps(error_result)}:__END_RESULT__")
        return 1

if __name__ == "__main__":
    sys.exit(main())
