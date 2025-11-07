#!/usr/bin/env python3
"""
Scouting Report Generator
Generates a multi-page landscape PDF scouting report for all pitchers on an opponent team.
Each page shows:
- Header: Team logo (placeholder) | Pitcher name/number | AF logo
- Left column (80%): 18 heat maps (3 rows × 6 columns) - pitch location by type/hand/situation
- Right column (20%): Headshot + movement chart
"""

import os
import sys
import json
import time
import argparse
import urllib.parse
import requests
from pathlib import Path
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle, Image as ReportLabImage
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from trumedia_scraper import TruMediaScraper

# Configuration
USERNAME = os.getenv("TRUMEDIA_USERNAME", "Justin.Graham@afacademy.af.edu")
SITENAME = os.getenv("TRUMEDIA_SITENAME", "airforce-ncaabaseball")
MASTER_TOKEN = os.getenv("TRUMEDIA_MASTER_TOKEN", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiZjZlZWEwYzViZmUwZTY4ZmEwZDUyMGQyMDU2NTNmYzciLCJpYXQiOjE3NTc0MjE1NjF9.p940yyxhsJZp_gZFX-4Y4U48WqZrvbylDyY8Oj2u9q0")
CHROME_DEBUG_PORT = int(os.getenv("CHROME_DEBUG_PORT", "9222"))
SEASON = 2025


def debug_dom_structure(scraper):
    """Debug helper to inspect TruMedia DOM structure and find pitcher elements"""
    print("\n" + "="*60)
    print("DEBUG: Inspecting TruMedia DOM Structure")
    print("="*60)

    js = """
    const app = document.querySelector('tmn-ferp-app');
    if (!app || !app.shadowRoot) {
        return {error: 'No tmn-ferp-app or shadow root found'};
    }

    const info = {
        hasApp: true,
        entityContainers: 0,
        entityDescriptions: 0,
        entityItems: 0,
        sampleText: [],
        allElementTypes: new Set(),
        shadowRoots: 0
    };

    // Search recursively through shadow DOM
    function searchShadowDOM(root, depth = 0) {
        if (depth > 10) return;

        root.querySelectorAll('*').forEach(el => {
            info.allElementTypes.add(el.tagName.toLowerCase());

            // Look for entity-container divs
            if (el.classList && (el.classList.contains('entity-container') || el.className.includes('entity-container'))) {
                info.entityContainers++;
            }

            // Look for tmn-entity-description-baseball
            if (el.tagName.toLowerCase() === 'tmn-entity-description-baseball') {
                info.entityDescriptions++;
            }

            // Look for entity-item divs (these are the pitcher cards)
            if (el.classList && (el.classList.contains('entity-item') || el.className.includes('entity-item'))) {
                info.entityItems++;
                if (info.sampleText.length < 3) {
                    info.sampleText.push(el.textContent.substring(0, 50));
                }
            }

            // Count shadow roots
            if (el.shadowRoot) {
                info.shadowRoots++;
                searchShadowDOM(el.shadowRoot, depth + 1);
            }
        });
    }

    searchShadowDOM(app.shadowRoot);
    info.allElementTypes = Array.from(info.allElementTypes);

    return info;
    """

    result = scraper.driver.execute_script(js)
    print(f"DOM Structure Info:")
    print(f"  - Has tmn-ferp-app: {result.get('hasApp', False)}")
    print(f"  - Shadow roots found: {result.get('shadowRoots', 0)}")
    print(f"  - Entity containers found: {result.get('entityContainers', 0)}")
    print(f"  - Entity descriptions found: {result.get('entityDescriptions', 0)}")
    print(f"  - Entity items (pitcher cards) found: {result.get('entityItems', 0)}")
    print(f"  - Sample text from entity items: {result.get('sampleText', [])}")
    print(f"  - All element types: {result.get('allElementTypes', [])[:20]}...")
    print("="*60 + "\n")

    return result


def build_team_pitching_url(team_name, team_id):
    """Build TruMedia team custom pitching page URL"""
    base = "https://airforce-ncaabaseball.trumedianetworks.com"
    cp = {
        "teamIds": [int(team_id)],
        "selectedReportId": 83,
        "sortSelections": ["alpha"],
        "filterSelections": ["anyone"]
    }
    f = {"bseason": [SEASON]}
    s = {"combinedSplits": ["filterBaseballBatterHand"], "combinedSplitsSubtotals": {}}

    return (f"{base}/baseball/team-custom-pages-pitching/{team_name}/{team_id}"
            f"?cp={urllib.parse.quote(json.dumps(cp))}"
            f"&f={urllib.parse.quote(json.dumps(f))}"
            f"&s={urllib.parse.quote(json.dumps(s))}")


def extract_pitcher_info(scraper):
    """Extract pitcher list with names, numbers, and headshot URLs from the page"""
    pitchers = []

    try:
        # Wait for page to load
        time.sleep(5)

        # JavaScript to extract pitcher roster information from shadow DOM
        js = """
        function findPitchers() {
            const app = document.querySelector('tmn-ferp-app');
            if (!app || !app.shadowRoot) return [];

            const rosterElements = [];

            function searchShadowDOM(root) {
                if (!root) return;

                // Look for entity-container divs (from screenshot)
                const entityContainers = root.querySelectorAll('div.entity-container, [class*="entity-container"]');

                entityContainers.forEach(container => {
                    // Look for tmn-entity-description-baseball elements within the container
                    const entityDescriptions = container.querySelectorAll('tmn-entity-description-baseball');

                    entityDescriptions.forEach(entityDesc => {
                        if (entityDesc.shadowRoot) {
                            // Inside the shadow root, find entity-item divs
                            const entityItems = entityDesc.shadowRoot.querySelectorAll('div.entity-item, [class*="entity-item"]');

                            entityItems.forEach(card => {
                                // Extract name from cell div
                                const cells = card.querySelectorAll('div.cell, [class*="cell"]');
                                let name = '';
                                let number = '';
                                let handedness = '';

                                // Collect all name parts from multiple cells
                                let nameParts = [];

                                cells.forEach(cell => {
                                    const text = cell.textContent.trim();
                                    if (!text) return;

                                    // Jersey number - extract from any content (even mixed like "#38 Ethan")
                                    const numberMatch = text.match(/#*(\\d+)/);
                                    if (numberMatch && !number) {
                                        number = numberMatch[1];  // Extract just the digits
                                    }

                                    // Handedness - match L or R (standalone or in parentheses)
                                    if (text.match(/^[LR]$/i) || text.match(/^\\([LR]\\)$/i)) {
                                        const handMatch = text.match(/\\(?([LR])\\)?/i);
                                        if (handMatch) handedness = handMatch[1].toUpperCase();
                                        return;
                                    }

                                    // Collect name text from this cell
                                    let cleanText = text;
                                    // Remove number prefixes like "#38"
                                    cleanText = cleanText.replace(/^#*\\d+\\s*/, '');
                                    // Remove handedness markers like (R) or (L)
                                    cleanText = cleanText.replace(/\\s*\\([LR]\\)\\s*/gi, ' ');
                                    // Remove extra words after name (like team names)
                                    cleanText = cleanText.replace(/\\s+(Falcons|Academy).*$/gi, '');
                                    cleanText = cleanText.trim();
                                    if (cleanText) {
                                        nameParts.push(cleanText);
                                    }
                                });

                                // Combine all name parts and extract first + last name
                                if (nameParts.length > 0) {
                                    const fullName = nameParts.join(' ');
                                    const words = fullName.split(/\\s+/);
                                    if (words.length >= 2) {
                                        name = words[0] + ' ' + words[1];
                                    } else if (words.length === 1) {
                                        name = words[0];
                                    }
                                }

                                // Extract headshot - try multiple selectors
                                let headshotUrl = '';

                                // Try 1: Look for titleDiv.headshot
                                let headshotDiv = card.querySelector('div.titleDiv.headshot, [class*="titleDiv"][class*="headshot"]');
                                if (!headshotDiv) {
                                    // Try 2: Look for any headshot class
                                    headshotDiv = card.querySelector('[class*="headshot"]');
                                }

                                if (headshotDiv) {
                                    const imgEl = headshotDiv.querySelector('img');
                                    if (imgEl) {
                                        // Try multiple attributes
                                        headshotUrl = imgEl.src || imgEl.currentSrc || imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || '';
                                        // Ensure absolute URL
                                        if (headshotUrl && !headshotUrl.startsWith('http')) {
                                            headshotUrl = new URL(headshotUrl, window.location.origin).href;
                                        }
                                    }
                                }

                                // Try 3: If still no headshot, look for any img in the card
                                if (!headshotUrl) {
                                    const anyImg = card.querySelector('img');
                                    if (anyImg) {
                                        headshotUrl = anyImg.src || anyImg.currentSrc || anyImg.getAttribute('src') || anyImg.getAttribute('data-src') || '';
                                        if (headshotUrl && !headshotUrl.startsWith('http')) {
                                            headshotUrl = new URL(headshotUrl, window.location.origin).href;
                                        }
                                    }
                                }

                                // Try 4: Check for background-image on headshot div or child elements
                                if (!headshotUrl && headshotDiv) {
                                    const checkBgImage = (element) => {
                                        const style = window.getComputedStyle(element);
                                        const bgImage = style.backgroundImage;
                                        if (bgImage && bgImage !== 'none') {
                                            // Improved regex to handle whitespace and quotes
                                            const match = bgImage.match(/url\\s*\\(\\s*['"]?([^'")]+)['"]?\\s*\\)/i);
                                            return match ? match[1].trim() : null;
                                        }
                                        return null;
                                    };

                                    // Check headshot div itself
                                    headshotUrl = checkBgImage(headshotDiv);

                                    // Check all child elements (div.cell, span, etc.)
                                    if (!headshotUrl) {
                                        const children = headshotDiv.querySelectorAll('*');
                                        for (let child of children) {
                                            headshotUrl = checkBgImage(child);
                                            if (headshotUrl) break;
                                        }
                                    }

                                    // Ensure absolute URL
                                    if (headshotUrl && !headshotUrl.startsWith('http')) {
                                        headshotUrl = new URL(headshotUrl, window.location.origin).href;
                                    }
                                }

                                if (name) {
                                    // Avoid duplicates
                                    if (!rosterElements.some(p => p.name === name)) {
                                        rosterElements.push({
                                            name: name,
                                            number: number || '',
                                            handedness: handedness || 'R',
                                            headshot: headshotUrl,
                                            elementIndex: rosterElements.length
                                        });
                                    }
                                }
                            });
                        }
                    });
                });

                // Recursively search shadow roots
                root.querySelectorAll('*').forEach(el => {
                    if (el.shadowRoot) {
                        searchShadowDOM(el.shadowRoot);
                    }
                });
            }

            searchShadowDOM(app.shadowRoot);
            return rosterElements;
        }

        return findPitchers();
        """

        result = scraper.driver.execute_script(js)

        # Debug logging
        print(f"\n   DEBUG: JavaScript extraction result type: {type(result)}")
        print(f"   DEBUG: Result length: {len(result) if result else 0}")
        if result and len(result) > 0:
            print(f"   DEBUG: First pitcher sample: {result[0]}")
        else:
            print("   DEBUG: Result is empty or None")
            # Call debug function to inspect DOM structure
            debug_dom_structure(scraper)

        if result and len(result) > 0:
            pitchers = result
            print(f"   ✓ Found {len(pitchers)} pitchers via JavaScript")
        else:
            # Fail fast - don't use placeholder data
            raise RuntimeError(
                "Could not extract pitcher information from TruMedia page. "
                "The JavaScript extraction returned no results. "
                "Please check the debug output above to see the actual DOM structure. "
                "The selectors may need to be updated to match TruMedia's current DOM."
            )

    except RuntimeError:
        # Re-raise RuntimeError to fail fast
        raise
    except Exception as e:
        # Unexpected error - also fail fast with detailed info
        print(f"\n   ❌ ERROR: Exception during pitcher extraction: {e}")
        import traceback
        traceback.print_exc()
        raise RuntimeError(f"Failed to extract pitcher info due to exception: {e}")

    return pitchers


def scrape_pitcher_charts(scraper, pitcher_info, pitcher_index, output_dir):
    """Scrape heat maps and movement chart for one pitcher

    Args:
        pitcher_info: dict with 'name', 'number', 'headshot', 'playerId', 'elementIndex' keys

    Returns dict with chart paths:
    - 'heatmaps': list of 18 heat map paths (ordered by situation/pitch/hand)
    - 'movement': movement chart path
    - 'headshot': headshot image path
    """
    charts = {
        'heatmaps': [],
        'movement': None,
        'headshot': None
    }

    pitcher_name = pitcher_info['name']
    pitcher_dir = os.path.join(output_dir, f"pitcher_{pitcher_index}")
    os.makedirs(pitcher_dir, exist_ok=True)

    print(f"   Scraping charts for {pitcher_name}...")

    try:
        # Find all heat maps
        heat_maps = scraper.find_charts_in_shadow_dom()
        heat_map_charts = [c for c in heat_maps if c['tag'] == 'tmn-heat-map-baseball']

        print(f"      Found {len(heat_map_charts)} heat map(s)")

        # Calculate chart offset for this pitcher (18 heatmaps per pitcher, movement handled separately)
        charts_per_pitcher = 18
        chart_offset = pitcher_index * charts_per_pitcher

        # Capture up to 18 heat maps for this specific pitcher
        for idx in range(min(18, len(heat_map_charts) - chart_offset)):
            filename = os.path.join(pitcher_dir, f"heatmap_{idx}.png")
            path = scraper.capture_chart_by_tag('tmn-heat-map-baseball', chart_offset + idx, filename)
            if path:
                charts['heatmaps'].append(path)

        # Find movement chart for this specific pitcher
        movement_charts = [c for c in heat_maps if c['tag'] == 'tmn-pitch-break-chart-baseball']
        if len(movement_charts) > pitcher_index:
            filename = os.path.join(pitcher_dir, "movement.svg")
            path = scraper.capture_chart_by_tag('tmn-pitch-break-chart-baseball', pitcher_index, filename)
            if path:
                charts['movement'] = path
                print(f"      ✓ Movement chart captured")

        # Capture headshot image
        headshot_url = pitcher_info.get('headshot', '').strip()
        if headshot_url:
            print(f"      Headshot URL: {headshot_url[:100]}...")

            # Download headshot using Python requests
            try:
                response = requests.get(headshot_url, timeout=10)
                if response.status_code == 200:
                    filename = os.path.join(pitcher_dir, "headshot.png")
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    charts['headshot'] = filename
                    print(f"      ✓ Headshot captured and saved to: {filename}")
                    print(f"      ✓ File size: {len(response.content)} bytes")
                else:
                    print(f"      ⚠ Headshot download failed with status {response.status_code}")
            except Exception as e:
                print(f"      ⚠ Could not download headshot: {e}")

    except Exception as e:
        print(f"      ⚠ Error scraping charts: {e}")

    return charts


def draw_svg_chart(c, svg_path, x, y, width, height):
    """Draw an SVG chart at the specified position"""
    try:
        if not svg_path or not os.path.exists(svg_path):
            return False

        drawing = svg2rlg(svg_path)
        if not drawing:
            return False

        # Scale to fit
        scale_x = width / drawing.width
        scale_y = height / drawing.height
        scale = min(scale_x, scale_y) * 0.95

        drawing.width *= scale
        drawing.height *= scale
        drawing.scale(scale, scale)

        # Center in box
        x_offset = x + (width - drawing.width) / 2
        y_offset = y + (height - drawing.height) / 2

        renderPDF.draw(drawing, c, x_offset, y_offset)
        return True
    except Exception as e:
        print(f"      Warning: Could not render SVG {svg_path}: {e}")
        return False


def draw_image(c, img_path, x, y, width, height):
    """Draw an image (PNG/JPG) at the specified position"""
    try:
        if not img_path or not os.path.exists(img_path):
            return False

        c.drawImage(img_path, x, y, width=width, height=height,
                   preserveAspectRatio=True, mask='auto')
        return True
    except Exception as e:
        print(f"      Warning: Could not draw image {img_path}: {e}")
        return False


def generate_pitcher_page(c, pitcher_name, pitcher_number, pitcher_handedness, charts, team_name, page_width, page_height):
    """Generate one page of the scouting report for a single pitcher"""
    navy = colors.HexColor('#003366')
    gray = colors.HexColor('#CCCCCC')

    # Header section (full width)
    header_height = 1.0 * inch
    header_y = page_height - header_height

    # Draw header background
    c.setFillColor(colors.white)
    c.rect(0, header_y, page_width, header_height, fill=True, stroke=False)

    # Team logo (placeholder) - left
    logo_size = 0.7 * inch
    logo_x = 0.5 * inch
    logo_y = header_y + (header_height - logo_size) / 2
    # Removed border for cleaner look
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 8)
    c.drawCentredString(logo_x + logo_size/2, logo_y + logo_size/2, "TEAM")

    # Pitcher name and number - center
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 20)
    # Ensure clean number format (extract only digits)
    clean_number = ''.join(c for c in str(pitcher_number) if c.isdigit())
    if clean_number:
        title_text = f"#{clean_number} {pitcher_name} ({pitcher_handedness})"
    else:
        # No number found, omit the # prefix
        title_text = f"{pitcher_name} ({pitcher_handedness})"
    c.drawCentredString(page_width / 2, header_y + header_height / 2 + 0.1*inch, title_text)
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 12)
    c.drawCentredString(page_width / 2, header_y + header_height / 2 - 0.2*inch, team_name)

    # AF logo - right
    af_logo_path = "/Users/justin/AFBaseball/AF_logo.png"
    af_logo_x = page_width - logo_size - 0.5*inch
    if os.path.exists(af_logo_path):
        c.drawImage(af_logo_path, af_logo_x, logo_y, width=logo_size, height=logo_size,
                   preserveAspectRatio=True, mask='auto')
    else:
        # Removed border for placeholder
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 8)
        c.drawCentredString(af_logo_x + logo_size/2, logo_y + logo_size/2, "AF")

    # Content area
    content_y = header_y - 0.3*inch
    content_height = content_y - 0.5*inch

    # Column layout: 80% left, 20% right
    left_width = page_width * 0.78
    right_width = page_width * 0.20
    left_x = 0.3*inch
    right_x = left_x + left_width + 0.2*inch

    # Left column: 3 rows × 6 heat maps
    # Row labels: <2K, 2K, RISP
    # Column order: FB vs L, CH vs L, Breaking vs L, FB vs R, CH vs R, Breaking vs R

    heatmap_cols = 6
    heatmap_rows = 3
    heatmap_width = left_width / heatmap_cols
    heatmap_height = content_height / heatmap_rows

    row_labels = ["< 2K", "2K", "RISP"]

    # Heat map index mapping to ensure consistent ordering across all rows
    # The user reported that row 2 (RISP) has the correct order: Lefty first, then Righty
    # We need to reorder rows 0 and 1 to match row 2's pattern
    #
    # TruMedia provides 18 heat maps (indices 0-17):
    # - Rows are: <2K (0-5), 2K (6-11), RISP (12-17)
    # - Within each row, order should be: FB vs L, CH vs L, Breaking vs L, FB vs R, CH vs R, Breaking vs R
    #
    # If row 2 (RISP, indices 12-17) is correct as-is, we use it as the reference.
    # Adjust the mapping below if needed based on actual TruMedia output order.

    # Heat map index mapping to ensure consistent ordering (lefty first, righty second)
    # Rows 0-1 need to swap lefty/righty order to match row 2
    HEATMAP_INDEX_MAP = [
        # Row 0 (<2K): swap to put lefty first
        3, 4, 5, 0, 1, 2,    # Swap first half with second half
        # Row 1 (2K): swap to put lefty first
        9, 10, 11, 6, 7, 8,  # Swap first half with second half
        # Row 2 (RISP): keep as-is
        12, 13, 14, 15, 16, 17
    ]

    for row in range(heatmap_rows):
        for col in range(heatmap_cols):
            grid_position = row * heatmap_cols + col  # Position in the 3x6 grid (0-17)
            source_idx = HEATMAP_INDEX_MAP[grid_position]  # Which heat map to use from scraped data

            x = left_x + col * heatmap_width
            y = content_y - (row + 1) * heatmap_height

            # Draw heat map using mapped index (no border)
            if source_idx < len(charts['heatmaps']):
                heatmap_path = charts['heatmaps'][source_idx]
                if not draw_image(c, heatmap_path, x, y, heatmap_width, heatmap_height):
                    # Placeholder if image fails
                    c.setFillColor(colors.lightgrey)
                    c.setFont("Helvetica", 7)
                    c.drawCentredString(x + heatmap_width/2, y + heatmap_height/2, f"Map {source_idx}")

    # Right column: Headshot (top, reduced by 20%) + Movement chart (bottom, remaining space)
    headshot_height = (content_height / 3) * 0.8  # Reduced by 20%
    movement_height = content_height - headshot_height

    # Headshot (no border) - moved 0.1 inches to the left
    headshot_y = content_y - headshot_height
    headshot_x = right_x - 0.1 * inch

    headshot_path = charts.get('headshot')
    if headshot_path:
        print(f"      DEBUG: Headshot path: {headshot_path}")
        print(f"      DEBUG: File exists: {os.path.exists(headshot_path)}")
        if draw_image(c, headshot_path, headshot_x, headshot_y, right_width, headshot_height):
            print(f"      DEBUG: Headshot drawn successfully")
        else:
            print(f"      DEBUG: Failed to draw headshot")
            # Placeholder
            c.setFillColor(colors.lightgrey)
            c.setFont("Helvetica", 10)
            c.drawCentredString(headshot_x + right_width/2, headshot_y + headshot_height/2, "Photo")
    else:
        print(f"      DEBUG: No headshot path in charts")
        # Placeholder
        c.setFillColor(colors.lightgrey)
        c.setFont("Helvetica", 10)
        c.drawCentredString(headshot_x + right_width/2, headshot_y + headshot_height/2, "Photo")

    # Movement chart (no border) - moved 0.1 inches to the left
    movement_y = content_y - headshot_height - movement_height
    movement_x = right_x - 0.1 * inch

    if charts.get('movement'):
        if not draw_svg_chart(c, charts['movement'], movement_x, movement_y,
                             right_width, movement_height):
            c.setFillColor(colors.lightgrey)
            c.setFont("Helvetica", 10)
            c.drawCentredString(movement_x + right_width/2, movement_y + movement_height/2, "Movement")
    else:
        c.setFillColor(colors.lightgrey)
        c.setFont("Helvetica", 10)
        c.drawCentredString(movement_x + right_width/2, movement_y + movement_height/2, "Movement")


def generate_pdf(team_name, pitchers_data, output_path):
    """Generate multi-page PDF scouting report"""
    c = canvas.Canvas(output_path, pagesize=landscape(letter))
    page_width, page_height = landscape(letter)

    print(f"\n   Generating PDF with {len(pitchers_data)} page(s)...")

    for i, pitcher_data in enumerate(pitchers_data):
        print(f"      Page {i+1}: {pitcher_data['name']}")

        generate_pitcher_page(
            c,
            pitcher_name=pitcher_data['name'],
            pitcher_number=pitcher_data['number'],
            pitcher_handedness=pitcher_data.get('handedness', 'R'),
            charts=pitcher_data['charts'],
            team_name=team_name,
            page_width=page_width,
            page_height=page_height
        )

        # Always call showPage() after each page (including the last one)
        # This ensures the page is properly finalized before saving
        c.showPage()

    c.save()
    print(f"   ✓ PDF saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate scouting report for opponent team")
    parser.add_argument('--team-name', required=True, help='Team name')
    parser.add_argument('--team-id', required=True, help='TruMedia team ID')
    parser.add_argument('--output-dir', default='.', help='Output directory')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print("="*60)
    print("Scouting Report Generator")
    print("="*60)
    print(f"Team: {args.team_name} ({args.team_id})")
    print(f"Season: {SEASON}")
    print("="*60)

    try:
        # Initialize scraper
        print("\n1. Connecting to Chrome...")
        scraper = TruMediaScraper(debug_port=CHROME_DEBUG_PORT, heat_map_png=True)
        scraper.connect()

        # Navigate to team pitching page
        print("\n2. Loading team pitching page...")
        url = build_team_pitching_url(args.team_name, args.team_id)
        print(f"   URL: {url}")
        scraper.driver.get(url)

        # Wait for content to load
        print("   Waiting 15 seconds for content to load...")
        time.sleep(15)

        # Progressive scroll to load all lazy-loaded charts
        print("   Progressively scrolling to load all charts...")

        # Get initial page height
        scraper.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        total_height = scraper.driver.execute_script("return document.body.scrollHeight")

        # Scroll in increments to trigger lazy loading
        scroll_increment = 1000  # pixels
        current_position = 0

        while current_position < total_height:
            current_position += scroll_increment
            scraper.driver.execute_script(f"window.scrollTo(0, {current_position});")
            time.sleep(0.5)  # Short pause to let charts load

            # Check if page height increased (more content loaded)
            new_height = scraper.driver.execute_script("return document.body.scrollHeight")
            if new_height > total_height:
                total_height = new_height
                print(f"      Page height increased to {new_height}px")

        # Final scroll to bottom and back to top
        scraper.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        scraper.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)

        print(f"      ✓ Completed progressive scroll (total height: {total_height}px)")

        # Wait for roster elements to load
        print("   Waiting for roster elements to load...")
        max_wait = 10  # seconds
        wait_interval = 1  # seconds
        total_waited = 0

        roster_check_js = """
        const app = document.querySelector('tmn-ferp-app');
        if (!app || !app.shadowRoot) return 0;

        function countEntityItems(root) {
            let count = 0;
            const items = root.querySelectorAll('[class*="entity-item"], .entity-item');
            count += items.length;

            root.querySelectorAll('*').forEach(el => {
                if (el.shadowRoot) {
                    count += countEntityItems(el.shadowRoot);
                }
            });

            return count;
        }

        return countEntityItems(app.shadowRoot);
        """

        roster_found = False
        while total_waited < max_wait:
            entity_item_count = scraper.driver.execute_script(roster_check_js)
            if entity_item_count > 0:
                print(f"      ✓ Roster loaded: {entity_item_count} entity items found")
                roster_found = True
                break
            time.sleep(wait_interval)
            total_waited += wait_interval
            print(f"      Waiting... ({total_waited}s)")

        if not roster_found:
            print(f"      ⚠ Warning: No roster elements found after {max_wait}s wait")

        # Extract pitcher list
        print("\n3. Extracting pitcher roster...")
        pitchers = extract_pitcher_info(scraper)

        if not pitchers:
            print("   ⚠ No pitchers found, using placeholder data")
            pitchers = [{"name": "Unknown Pitcher", "number": "0", "headshot": ""}]

        print(f"   ✓ Found {len(pitchers)} pitcher(s):")
        for p in pitchers:
            print(f"      - #{p['number']} {p['name']}")

        # Extract all headshots from roster page (one-time extraction)
        print("\n   Extracting headshots from roster...")
        headshots_js = """
        function findInShadowDOM(root, selector, all = false) {
            let results = [];

            function search(node) {
                if (!node) return;

                // Search in current level
                if (all) {
                    const elements = node.querySelectorAll(selector);
                    results.push(...Array.from(elements));
                } else {
                    const element = node.querySelector(selector);
                    if (element) {
                        results.push(element);
                        return;
                    }
                }

                // Search in shadow roots
                const allElements = node.querySelectorAll('*');
                for (let el of allElements) {
                    if (el.shadowRoot) {
                        search(el.shadowRoot);
                        if (!all && results.length > 0) return;
                    }
                }
            }

            search(root);
            return all ? results : results[0];
        }

        // Find all entity logo elements with player entitytype
        const logos = findInShadowDOM(document, 'tmn-baseball-entity-logo[entitytype="player"]', true);

        const headshotUrls = [];
        const seenUrls = new Set();

        for (let logo of logos) {
            if (logo.shadowRoot) {
                const img = logo.shadowRoot.querySelector('img');
                if (img && img.src) {
                    // Only add if we haven't seen this URL before (deduplicate)
                    if (!seenUrls.has(img.src)) {
                        headshotUrls.push(img.src);
                        seenUrls.add(img.src);
                    }
                }
            }
        }

        return headshotUrls;
        """

        try:
            headshot_urls = scraper.driver.execute_script(headshots_js)
            print(f"   ✓ Extracted {len(headshot_urls)} headshot(s) from roster")

            # Match headshots to pitchers by index
            for i, pitcher in enumerate(pitchers):
                if i < len(headshot_urls) and headshot_urls[i]:
                    pitcher['headshot'] = headshot_urls[i]
                    print(f"      Matched headshot for {pitcher['name']}: {headshot_urls[i][-20:]}...")
                else:
                    print(f"      ⚠ No headshot found for {pitcher['name']}")
        except Exception as e:
            print(f"   ⚠ Error extracting headshots: {e}")

        # Scrape charts for each pitcher
        print("\n4. Scraping charts...")
        charts_dir = os.path.join(args.output_dir, "scouting_charts")
        os.makedirs(charts_dir, exist_ok=True)

        pitchers_data = []
        for i, pitcher in enumerate(pitchers):
            charts = scrape_pitcher_charts(scraper, pitcher, i, charts_dir)
            pitchers_data.append({
                'name': pitcher['name'],
                'number': pitcher['number'],
                'handedness': pitcher.get('handedness', 'R'),
                'charts': charts
            })

        # Close scraper
        scraper.close()

        # Generate PDF
        print("\n5. Generating PDF...")
        output_filename = f"Scouting_Report_{args.team_name.replace(' ', '_')}_{SEASON}.pdf"
        output_path = os.path.join(args.output_dir, output_filename)

        generate_pdf(args.team_name, pitchers_data, output_path)

        print("\n" + "="*60)
        print("✓ Complete!")
        print(f"📄 Report: {output_path}")
        print("="*60)

        # Output JSON result for API
        result = {
            "success": True,
            "pdfPath": output_filename,
            "team": args.team_name,
            "pitcherCount": len(pitchers_data)
        }
        print(f"\n__RESULT_JSON__:{json.dumps(result)}:__END_RESULT__")

        return 0

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

        result = {"success": False, "error": str(e)}
        print(f"\n__RESULT_JSON__:{json.dumps(result)}:__END_RESULT__")
        return 1


if __name__ == "__main__":
    sys.exit(main())
