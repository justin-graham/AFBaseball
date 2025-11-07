#!/usr/bin/env python3
"""
TruMedia Chart Scraper - Clean & Simple (heat map compatible)
Captures baseball charts from TruMedia's shadow DOM as SVG/PNG assets.
"""

import base64
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


class TruMediaScraper:
    CHART_TYPES = [
        "tmn-pie-chart-baseball",
        "tmn-pitch-chart-baseball",
        "tmn-pitch-break-chart-baseball",
        "tmn-release-point-chart-baseball",
        "tmn-radial-histogram-chart-baseball",
        "tmn-extension-point-chart-baseball",
        "tmn-heat-map-baseball",
    ]

    def __init__(self, debug_port=9222, heat_map_png=True):
        self.debug_port = debug_port
        self.heat_map_png = heat_map_png
        self.driver = None
        self._frame_id = None

    def connect(self):
        driver_path = self._find_chromedriver()
        if not driver_path:
            raise RuntimeError("chromedriver not found in ./chromedriver directory")
        launched = self._ensure_debug_session()
        if not self._wait_for_debugger_ready(timeout=60):
            raise RuntimeError(
                f"Chrome remote debugger on port {self.debug_port} did not become ready. "
                "Ensure the debugging Chrome window is open and not blocked by dialogs."
            )
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.debug_port}")
        if not self._ensure_debugger_target():
            # Auto-create a new tab if none exist
            print("No Chrome tabs found. Creating new tab...")
            time.sleep(2)  # Give Chrome a moment
            if not self._ensure_debugger_target():
                raise RuntimeError(
                    "Chrome remote debugger is running but no tab is available. "
                    "Please ensure Chrome debug window has at least one tab open."
                )
        for attempt in range(4):
            service = Service(driver_path)
            try:
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                break
            except SessionNotCreatedException as exc:
                service.stop()
                if attempt < 3:
                    wait_time = 2 + attempt
                    print(f"Chrome not ready for remote debugging (attempt {attempt+1}/4). Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    self._wait_for_debugger_ready(timeout=15)
                    self._ensure_debugger_target()
                    continue
                self._log_debugger_snapshot()
                raise
        message = "✓ Connected to Chrome on port {} ({})"
        state = "fresh session" if launched else "existing session"
        print(message.format(self.debug_port, state))

    def build_url(self, player_name, player_id, start_date, end_date, report_id=107):
        base = "https://airforce-ncaabaseball.trumedianetworks.com"
        cp = {"filterSelections": ["anyone"], "sortSelections": ["alpha"], "playerIds": [player_id], "selectedReportId": report_id}
        f = {"bseason": ["def"], "bdr": [start_date, end_date]}
        s = {"combinedSplits": ["filterBaseballBatterHand"], "combinedSplitsSubtotals": {}}
        return (
            f"{base}/baseball/player-custom-pages-pitching/{player_name}/{player_id}"
            f"?cp={quote(json.dumps(cp))}&f={quote(json.dumps(f))}&sh={quote(json.dumps({}))}&s={quote(json.dumps(s))}"
        )

    def find_charts_in_shadow_dom(self):
        js = """
        function findCharts(root, chartTypes) {
            if (!root) return [];
            let charts = [];
            root.querySelectorAll('*').forEach(el => {
                const tag = el.tagName?.toLowerCase();
                if (chartTypes.includes(tag)) charts.push({tag, element: el});
                if (el.shadowRoot) charts = charts.concat(findCharts(el.shadowRoot, chartTypes));
            });
            return charts;
        }
        const app = document.querySelector('tmn-ferp-app');
        if (!app || !app.shadowRoot) return [];
        const chartTypes = arguments[0];
        const found = findCharts(app.shadowRoot, chartTypes);
        return found.map(c => ({tag: c.tag}));
        """
        return self.driver.execute_script(js, self.CHART_TYPES)

    def capture_chart_by_tag(self, tag, index, output_path):
        js = """
        function deepQuery(node, selector, depth = 0) {
            if (!node || depth > 12) return null;
            if (node.matches && node.matches(selector)) return node;
            if (node.querySelector) {
                const direct = node.querySelector(selector);
                if (direct) return direct;
            }
            if (node.shadowRoot) {
                const shadowResult = deepQuery(node.shadowRoot, selector, depth + 1);
                if (shadowResult) return shadowResult;
            }
            const children = node.children ? Array.from(node.children) : [];
            for (const child of children) {
                const found = deepQuery(child, selector, depth + 1);
                if (found) return found;
            }
            return null;
        }
        function findChart(root, targetTag, targetIndex, preferImage, state = {idx: 0}) {
            if (!root) return null;
            const nodes = root.querySelectorAll('*');
            for (const el of nodes) {
                const tag = el.tagName?.toLowerCase();
                if (tag === targetTag) {
                    if (state.idx === targetIndex) {
                        function findSvg(node) {
                            if (!node) return null;
                            if (node.tagName?.toLowerCase() === 'svg') return node;
                            const descendants = node.querySelectorAll ? node.querySelectorAll('*') : [];
                            for (const child of descendants) {
                                const found = findSvg(child);
                                if (found) return found;
                            }
                            return node.shadowRoot ? findSvg(node.shadowRoot) : null;
                        }
                        function captureImage(node) {
                            const img = deepQuery(node, 'img');
                            if (img) {
                                const src = img.getAttribute('src') || img.currentSrc || '';
                                if (src.startsWith('data:image/')) return {kind:'inline', data:src};
                                const canvas = document.createElement('canvas');
                                const w = img.naturalWidth || img.width || 0;
                                const h = img.naturalHeight || img.height || 0;
                                if (w && h) {
                                    canvas.width = w;
                                    canvas.height = h;
                                    canvas.getContext('2d').drawImage(img, 0, 0, w, h);
                                    return {kind:'inline', data:canvas.toDataURL('image/png')};
                                }
                            }
                            const canvasEl = deepQuery(node, 'canvas');
                            if (canvasEl) {
                                try { return {kind:'inline', data:canvasEl.toDataURL('image/png')}; } catch(e) {}
                            }
                            const svgImg = deepQuery(node, 'image');
                            if (svgImg) {
                                const href = svgImg.getAttribute('href') || svgImg.getAttribute('xlink:href');
                                if (href) {
                                    const abs = new URL(href, location.href).toString();
                                    try {
                                        const xhr = new XMLHttpRequest();
                                        xhr.open('GET', abs, false);
                                        xhr.withCredentials = true;
                                        xhr.responseType = 'arraybuffer';
                                        xhr.send();
                                        if (xhr.status >= 200 && xhr.status < 300) {
                                            const bytes = new Uint8Array(xhr.response || []);
                                            let bin = '';
                                            for (const b of bytes) bin += String.fromCharCode(b);
                                            const base64 = btoa(bin);
                                            const type = xhr.getResponseHeader('Content-Type') || 'image/png';
                                            return {kind:'inline', data:`data:${type};base64,${base64}`, mime:type};
                                        }
                                    } catch(e) {}
                                    return {kind:'href', href:abs};
                                }
                            }
                            return null;
                        }
                        const useImageFirst = preferImage === true;
                        const svg = findSvg(el);
                        const svgResult = svg ? {kind:'svg', svg: svg.outerHTML} : null;
                        const imageResult = captureImage(el);
                        if (useImageFirst) {
                            if (imageResult) return imageResult;
                            if (svgResult) return svgResult;
                        } else {
                            if (svgResult) return svgResult;
                            if (imageResult) return imageResult;
                        }
                        return {kind:'missing'};
                    }
                    state.idx++;
                }
                if (el.shadowRoot) {
                    const result = findChart(el.shadowRoot, targetTag, targetIndex, preferImage, state);
                    if (result) return result;
                }
            }
            return null;
        }
        const app = document.querySelector('tmn-ferp-app');
        if (!app || !app.shadowRoot) return {kind:'missing', reason:'main-app'};
        return findChart(app.shadowRoot, arguments[0], arguments[1], arguments[2]) || {kind:'missing'};
        """
        prefer_image = self.heat_map_png and tag == "tmn-heat-map-baseball"
        result = self.driver.execute_script(js, tag, index, prefer_image)
        if not result:
            return None
        kind = result.get("kind")
        if kind == "svg" and result.get("svg"):
            Path(output_path).write_text(result["svg"], encoding="utf-8")
            return output_path
        if kind == "inline" and result.get("data"):
            return self._write_data_url(output_path, result["data"], result.get("mime"))
        if kind == "href" and result.get("href"):
            return self._download_resource(output_path, result["href"])
        return None

    def _write_data_url(self, path, data_url, mime):
        if not data_url.startswith("data:"):
            return None
        _, _, payload = data_url.partition(",")
        binary = base64.b64decode(payload)
        extension = self._mime_to_ext(mime)
        final = Path(path).with_suffix(f".{extension}")
        final.write_bytes(binary)
        return str(final)

    def _download_resource(self, path, url):
        frame_id = self._frame_id or self._get_frame_id()
        content = self.driver.execute_cdp_cmd("Page.getResourceContent", {"frameId": frame_id, "url": url})
        data = content.get("content")
        if data is None:
            print(f"⚠️  Unable to fetch heat map image at {url}")
            return None
        binary = base64.b64decode(data) if content.get("base64Encoded") else data.encode()
        ext = self._detect_image(binary, url)
        final = Path(path).with_suffix(f".{ext}")
        final.write_bytes(binary)
        return str(final)

    def _get_frame_id(self):
        tree = self.driver.execute_cdp_cmd("Page.getFrameTree", {})
        frame_id = tree.get("frameTree", {}).get("frame", {}).get("id")
        if not frame_id:
            raise RuntimeError("Unable to determine frame id for resource download")
        self._frame_id = frame_id
        return frame_id

    @staticmethod
    def _detect_image(binary, url):
        signatures = [
            (b"\x89PNG\r\n\x1a\n", "png"),
            (b"\xff\xd8\xff", "jpg"),
            (b"GIF87a", "gif"),
            (b"GIF89a", "gif"),
            (b"RIFF", "webp"),
        ]
        for sig, ext in signatures:
            if binary.startswith(sig):
                return ext
        lower = url.lower()
        for ext in ("png", "jpg", "jpeg", "gif", "webp"):
            if lower.endswith(f".{ext}"):
                return "jpg" if ext == "jpeg" else ext
        return "png"

    def _port_open(self):
        try:
            with socket.create_connection(("127.0.0.1", self.debug_port), timeout=1):
                return True
        except OSError:
            return False

    def _ensure_debug_session(self):
        if self._port_open():
            return False
        print("Chrome debug session not detected. Launching...")
        self._launch_chrome()
        if not self._wait_for_port():
            raise RuntimeError("Chrome failed to expose the remote debugging port.")
        print("Chrome launched successfully. Waiting for it to be ready...")
        time.sleep(5)  # Give Chrome time to fully initialize
        return True

    def _launch_chrome(self):
        script = Path(__file__).parent / "launch_chrome_debug.sh"
        if not script.exists():
            raise RuntimeError("launch_chrome_debug.sh not found. Please start Chrome manually.")
        subprocess.Popen(["bash", str(script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _wait_for_port(self, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._port_open():
                return True
            time.sleep(0.5)
        return False

    def _wait_for_debugger_ready(self, timeout=15):
        endpoint = f"http://127.0.0.1:{self.debug_port}/json/version"
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(endpoint, timeout=1) as response:
                    if response.status == 200:
                        body = response.read().decode("utf-8")
                        try:
                            data = json.loads(body)
                        except json.JSONDecodeError:
                            pass
                        else:
                            if data.get("webSocketDebuggerUrl"):
                                return True
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
                pass
            time.sleep(0.5)
        return False

    def _ensure_debugger_target(self):
        tabs_endpoint = f"http://127.0.0.1:{self.debug_port}/json/list"
        try:
            with urllib.request.urlopen(tabs_endpoint, timeout=1) as response:
                body = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            return False
        try:
            pages = json.loads(body)
        except json.JSONDecodeError:
            return False
        if pages:
            return True

        # No tabs found - try to create one automatically with retry logic
        print("No tabs open in Chrome. Attempting to create a new tab...")
        for attempt in range(3):  # Try 3 times
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{self.debug_port}/json/new",
                    timeout=2
                ).read()
                time.sleep(1)  # Give tab time to open

                # Verify tab was created
                with urllib.request.urlopen(tabs_endpoint, timeout=1) as response:
                    pages = json.loads(response.read().decode("utf-8"))
                    if pages:
                        print("✓ New tab created successfully")
                        return True
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
                if attempt < 2:
                    time.sleep(1)
                continue

        return False

    def _log_debugger_snapshot(self):
        version_endpoint = f"http://127.0.0.1:{self.debug_port}/json/version"
        list_endpoint = f"http://127.0.0.1:{self.debug_port}/json/list"
        print("\nDebugger diagnostics:")
        for name, endpoint in (("version", version_endpoint), ("list", list_endpoint)):
            try:
                with urllib.request.urlopen(endpoint, timeout=2) as response:
                    body = response.read().decode("utf-8")
            except Exception as exc:  # pylint: disable=broad-except
                print(f"  • {endpoint} -> ERROR ({exc})")
            else:
                snippet = (body[:200] + "...") if len(body) > 200 else body
                print(f"  • {endpoint} -> {response.status}: {snippet}")

    def _find_chromedriver(self):
        search_root = Path(__file__).parent / "chromedriver"
        if not search_root.exists():
            return None
        for path in sorted(search_root.rglob("chromedriver")):
            if path.is_file() and os.access(path, os.X_OK):
                return str(path)
        return None

    @staticmethod
    def _mime_to_ext(mime):
        if not mime:
            return "png"
        mime = mime.lower()
        return {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/gif": "gif",
            "image/webp": "webp",
        }.get(mime, "png")

    def scrape_current_page(self, output_dir):
        print("\nWaiting for charts to load...")
        time.sleep(7)
        print("Finding charts in shadow DOM...")
        charts = self.find_charts_in_shadow_dom()
        if not charts:
            print("⚠️  No charts found")
            return []

        print(f"✓ Found {len(charts)} chart element(s)")
        chart_counts = {}
        for chart in charts:
            tag = chart["tag"]
            chart_counts[tag] = chart_counts.get(tag, 0) + 1

        os.makedirs(output_dir, exist_ok=True)
        captured = []
        print("\nCapturing charts...")
        for tag, count in chart_counts.items():
            for idx in range(count):
                chart_name = tag.replace("tmn-", "").replace("-baseball", "")
                filename = f"{chart_name}_{idx}.svg" if count > 1 else f"{chart_name}.svg"
                filepath = os.path.join(output_dir, filename)

                saved_path = self.capture_chart_by_tag(tag, idx, filepath)
                if saved_path:
                    captured.append(saved_path)
                    print(f"  ✓ {Path(saved_path).name}")

        return captured

    def scrape_player(self, player_name, player_id, start_date, end_date, output_dir):
        url = self.build_url(player_name, player_id, start_date, end_date)

        print(f"\n{'='*60}")
        print(f"Player: {player_name} (ID: {player_id})")
        print(f"Date: {start_date} to {end_date}")
        print(f"{'='*60}")

        self.driver.get(url)
        player_dir = os.path.join(output_dir, f"{player_name}_{player_id}_{start_date}_to_{end_date}")
        captured = self.scrape_current_page(player_dir)

        print(f"\n{'='*60}")
        print(f"✓ Captured {len(captured)} chart(s)")
        print(f"📁 {player_dir}")
        print(f"{'='*60}\n")

        return player_dir, captured

    def close(self):
        if self.driver:
            self.driver.quit()


def main():
    scraper = TruMediaScraper(debug_port=9222)
    try:
        scraper.connect()
        scraper.scrape_player(
            player_name="Smelcer",
            player_id=1469809434,
            start_date="2025-04-12",
            end_date="2025-04-12",
            output_dir="./trumedia_charts",
        )
    except Exception as exc:
        print(f"\n❌ Error: {exc}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
