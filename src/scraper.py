import asyncio
import urllib.parse
import logging
from typing import List, Optional, Callable
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from src.config import (
    HEADLESS,
    MAX_RESULTS,
    TIMEOUT,
    SCROLL_DELAY,
    ITEM_DELAY,
    MAPS_LANG,
    ONLY_ACTIVE,
)
from src.parser import parse_business_details
from src.db import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("gmaps_crawler")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

class GoogleMapsScraper:
    def __init__(
        self,
        db: Optional[Database] = None,
        max_results: int = MAX_RESULTS,
        headless: bool = HEADLESS,
        only_active: bool = ONLY_ACTIVE,
    ):
        self.db = db or Database()
        self.max_results = max_results
        self.headless = headless
        self.only_active = only_active

    def build_search_url(self, query: str) -> str:
        q = query.strip()
        encoded_query = urllib.parse.quote(q)
        return f"https://www.google.com/maps/search/{encoded_query}?hl={MAPS_LANG}"

    async def _setup_browser(self, p) -> tuple[Browser, BrowserContext, Page]:
        browser = await p.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                f"--lang={MAPS_LANG}",
            ]
        )
        context = await browser.new_context(
            user_agent=USER_AGENTS[0],
            viewport={"width": 1366, "height": 768},
            locale=f"{MAPS_LANG}-VN" if MAPS_LANG == "vi" else f"{MAPS_LANG}-US",
        )
        # Anti-detect evasion script
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'vi-VN', 'vi'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)
        page = await context.new_page()
        page.set_default_timeout(TIMEOUT)
        return browser, context, page

    async def scroll_feed(self, page: Page, max_items: int) -> List[str]:
        """
        Scrolls the result feed in Google Maps to load place links.
        Returns a list of URLs for the places found.
        """
        feed_selector = "div[role='feed']"
        try:
            await page.wait_for_selector(feed_selector, timeout=10000)
        except Exception:
            logger.warning("Feed list selector not found (query might have redirected to a single result).")
            return []

        logger.info(f"Scrolling feed to load up to {max_items} businesses...")
        
        seen_urls = set()
        last_count = 0
        stuck_retries = 0

        while len(seen_urls) < max_items and stuck_retries < 5:
            # Extract links currently present
            links = await page.locator("div[role='feed'] a[href*='/maps/place/']").all()
            for link in links:
                try:
                    href = await link.get_attribute("href")
                    if href and "/maps/place/" in href:
                        seen_urls.add(href)
                except Exception:
                    continue

            logger.info(f"-> Found {len(seen_urls)} places...")

            if len(seen_urls) >= max_items:
                break

            if len(seen_urls) == last_count:
                stuck_retries += 1
            else:
                stuck_retries = 0
                last_count = len(seen_urls)

            # Check if end of list reached (supports both Vietnamese and English UI)
            end_elem = page.locator(
                "p.fontBodyMedium:has-text('kết thúc'), "
                "span:has-text('Bạn đã xem hết danh sách'), "
                "span:has-text(\"You've reached the end of the list\"), "
                "p.fontBodyMedium:has-text('end of list')"
            )
            if await end_elem.count() > 0 and await end_elem.first.is_visible():
                logger.info("Reached the end of Google Maps results list.")
                break

            # Scroll the feed
            feed = page.locator(feed_selector)
            await feed.evaluate("element => element.scrollBy(0, 1000)")
            await asyncio.sleep(SCROLL_DELAY)

        return list(seen_urls)[:max_items]

    async def scrape_place_url(self, page: Page, place_url: str, query: str) -> Optional[dict]:
        """
        Navigates to a specific place URL and extracts all details.
        """
        try:
            await page.goto(place_url, wait_until="domcontentloaded", timeout=TIMEOUT)
            # Wait for the heading to appear
            await page.wait_for_selector("h1", timeout=8000)
            await asyncio.sleep(ITEM_DELAY)

            data = await parse_business_details(page, place_url, query)
            return data
        except Exception as e:
            logger.error(f"Error scraping URL {place_url[:60]}...: {e}")
            return None

    async def crawl_query(self, query: str, limit: Optional[int] = None) -> int:
        """
        Crawls businesses for a specific query keyword.
        Returns the number of businesses saved.
        """
        max_items = limit or self.max_results
        search_url = self.build_search_url(query)
        logger.info(f"\n========================================================")
        logger.info(f"Starting crawl for keyword: '{query}'")
        logger.info(f"URL: {search_url}")
        logger.info(f"========================================================")

        saved_count = 0
        async with async_playwright() as p:
            browser, context, page = await self._setup_browser(p)
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=TIMEOUT)
                await asyncio.sleep(2)

                # Check if it directly redirected to a single place page
                current_url = page.url
                if "/maps/place/" in current_url:
                    logger.info("Search query directly matched a single place!")
                    await page.wait_for_selector("h1", timeout=5000)
                    data = await parse_business_details(page, current_url, query)
                    if self._should_save(data):
                        res = self.db.upsert_business(data)
                        logger.info(f"[{res.upper()}] {data.get('name')} | Phone: {data.get('phone')} | Category: {data.get('category')} | Status: {data.get('status')}")
                        saved_count += 1
                    return saved_count

                # Otherwise scroll the feed
                place_urls = await self.scroll_feed(page, max_items)
                logger.info(f"Total URLs collected from feed: {len(place_urls)}")

                for i, p_url in enumerate(place_urls, 1):
                    logger.info(f"[{i}/{len(place_urls)}] Extracting data...")
                    data = await self.scrape_place_url(page, p_url, query)
                    
                    if not data or not data.get("name"):
                        continue

                    if not self._should_save(data):
                        logger.info(f"[SKIPPED - CLOSED] {data.get('name')} (Status: {data.get('status')})")
                        continue

                    res = self.db.upsert_business(data)
                    logger.info(
                        f"[{res.upper()}] {data.get('name')} | "
                        f"Phone: {data.get('phone') or 'N/A'} | "
                        f"Category: {data.get('category') or 'N/A'} | "
                        f"Status: {data.get('status')}"
                    )
                    saved_count += 1
                    await asyncio.sleep(ITEM_DELAY)

            except Exception as e:
                logger.error(f"Error during crawl for keyword '{query}': {e}", exc_info=True)
            finally:
                await context.close()
                await browser.close()

        logger.info(f"Completed keyword '{query}'. Saved/Updated: {saved_count} businesses.")
        return saved_count

    def _should_save(self, data: dict) -> bool:
        if not data or not data.get("name"):
            return False
        if self.only_active and data.get("is_active") == 0:
            return False
        return True

    async def crawl_multiple(self, queries: List[str], limit_per_query: Optional[int] = None) -> int:
        total = 0
        for idx, q in enumerate(queries, 1):
            logger.info(f"\n>>> PROGRESS: Keyword {idx}/{len(queries)} <<<")
            cnt = await self.crawl_query(q, limit=limit_per_query)
            total += cnt
            await asyncio.sleep(2)
        return total
