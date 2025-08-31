import json
import os
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
import importlib

# Try to dynamically import playwright_stealth.stealth_sync; fall back to a no-op.
try:
    _ps = importlib.import_module('playwright_stealth')
    stealth_sync = getattr(_ps, 'stealth_sync', lambda page: None)
except Exception:
    def stealth_sync(page):
        return None

from parsel import Selector

# Cache file
CACHE_FILE = "xstocks_cache.json"

def check_cache():
    if os.path.exists(CACHE_FILE):
        # Check if cache is less than 24 hours old
        cache_mtime = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
        if datetime.now() - cache_mtime < timedelta(hours=24):
            print(f"Using cached data from {CACHE_FILE}")
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
    return None

def scrape_xstocks():
    tokens = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br"
            }
        )
        page = context.new_page()
        stealth_sync(page)  # Apply stealth to bypass anti-scraping
        try:
            page.goto('https://xstocks.com/products', wait_until='networkidle', timeout=60000)
            html_content = page.content()

            # Try parsing __NEXT_DATA__ (Next.js)
            # Use explicit text= to avoid ambiguity in Selector constructor
            selector = Selector(text=html_content)
            data = selector.css("script#__NEXT_DATA__::text").get()
            if data:
                try:
                    data = json.loads(data)
                    # Adjust path based on actual JSON structure (hypothetical)
                    products = data.get('props', {}).get('pageProps', {}).get('products', [])
                    for product in products:
                        symbol = product.get('symbol')
                        address = product.get('mintAddress')  # Adjust key name if different
                        if symbol and address:
                            tokens.append({"symbol": symbol, "address": address})
                    if tokens:
                        print("Extracted tokens from __NEXT_DATA__")
                except json.JSONDecodeError as e:
                    print(f"Error parsing __NEXT_DATA__: {e}")

            # Fallback to parsing the saved HTML with parsel if no tokens from __NEXT_DATA__
            if not tokens:
                print("No tokens found in __NEXT_DATA__. Trying HTML parsing with parsel...")
                # The site renders rows like: <tr id="ABTx">...<h2 class="...">ABTx</h2>...<a href="https://solscan.io/token/<ADDRESS>">...
                rows = selector.css('tr[id]')
                for row in rows:
                    # Prefer the tr id as the symbol (example: id="ABTx"). Fall back to h2 text.
                    symbol = row.attrib.get('id') or row.css('h2::text').get()
                    if symbol:
                        symbol = symbol.strip()

                    # Look for solscan token links inside the row and extract the token address from the href
                    href = row.css('div.TableRow_address__TerfE a::attr(href)').get() or row.css('a::attr(href)').get()
                    address = None
                    if href:
                        if '/token/' in href:
                            # href like https://solscan.io/token/<ADDRESS>
                            try:
                                address = href.split('/token/')[1].split('?')[0].strip()
                            except Exception:
                                address = href.strip()
                        else:
                            address = href.strip()

                    if symbol and address:
                        tokens.append({"symbol": symbol, "address": address})

            if not tokens:
                print("No tokens extracted from DOM or __NEXT_DATA__")

            # Save to cache (UTF-8, keep non-ascii characters intact)
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(tokens, f, indent=2, ensure_ascii=False)
            print(f"Scraped data saved to {CACHE_FILE}")
            return tokens
        except Exception as e:
            print(f"Error: Failed to scrape xstocks.com: {e}")
            return None
        finally:
            browser.close()

def print_xstocks_map(tokens):
    if not tokens:
        print(f"Error: No data available (cache file {CACHE_FILE} not found or empty)")
        return
    for token in tokens:
        print(f"{token['symbol']} {token['address']}")

def main():
    cached_data = check_cache()
    if cached_data:
        print_xstocks_map(cached_data)
    else:
        print("Cache missing or outdated. Scraping xstocks.com...")
        tokens = scrape_xstocks()
        if tokens:
            print_xstocks_map(tokens)
        else:
            print("Scraping failed. Please check xstocks.com manually or update DOM selectors in scrape_xstocks.py.")
            exit(1)

if __name__ == "__main__":
    main()