import asyncio
import logging
import urllib.parse
from typing import List, Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from src.config import (
    HEADLESS,
    MAX_RESULTS,
    TIMEOUT,
    ITEM_DELAY,
    ONLY_ACTIVE,
    MIN_POSITION,
)
from src.parser import clean_text, clean_phone
from src.db import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("trangvang_crawler")
logger.setLevel(logging.INFO)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

JS_EXTRACT_CARDS = """
() => {
    const list = [];
    const cards = document.querySelectorAll('.tvx-card');
    cards.forEach((c, idx) => {
        const sttElem = c.querySelector('.stt_txt, .stt');
        const stt = sttElem ? parseInt(sttElem.innerText.trim(), 10) : null;
        
        const h2 = c.querySelector('h2.tvx-cn a, h2.tvx-cn, h2 a, h2, h3');
        const name = h2 ? h2.innerText.trim() : '';
        const link = h2 && h2.href ? h2.href : (h2 && h2.querySelector('a') ? h2.querySelector('a').href : '');
        
        const telElements = Array.from(c.querySelectorAll('a[href^="tel:"]'));
        const phones = telElements.map(t => t.innerText.trim() || t.href.replace('tel:', '').trim());
        
        const mailElements = Array.from(c.querySelectorAll('a[href^="mailto:"]'));
        const emails = mailElements.map(m => m.href.replace('mailto:', '').trim());
        
        // Category
        let category = '';
        const fullText = c.innerText;
        const lines = fullText.split('\\n').map(l => l.trim()).filter(Boolean);
        for (let line of lines) {
            if (line.toUpperCase().startsWith('NGÀNH:')) {
                category = line.replace(/^NGÀNH:\s*/i, '').trim();
                break;
            }
        }
        
        // Address
        let address = '';
        const addrElem = c.querySelector('.tvx-addr, .diachi, address');
        if (addrElem) {
            address = addrElem.innerText.trim();
        } else {
            for (let line of lines) {
                if (line.includes('Việt Nam') || line.includes('TP.') || line.includes('Quận') || line.includes('Huyện') || line.includes('Đường') || line.includes('Tỉnh') || line.includes('Phường')) {
                    if (!line.toUpperCase().startsWith('NGÀNH') && !line.startsWith('Hotline') && !line.startsWith('Tài trợ') && !line.startsWith('Xác thực') && !line.startsWith('i')) {
                        address = line;
                        break;
                    }
                }
            }
        }

        // Website
        const webElem = Array.from(c.querySelectorAll('a')).find(a => {
            const h = a.href || '';
            return h && !h.includes('trangvangvietnam.com') && !h.startsWith('tel:') && !h.startsWith('mailto:') && !h.includes('zalo.me');
        });
        const website = webElem ? webElem.href : '';

        list.push({
            domIndex: idx + 1,
            stt,
            name,
            link,
            phones,
            emails,
            category,
            address,
            website
        });
    });
    return list;
}
"""

class TrangVangScraper:
    def __init__(
        self,
        db: Optional[Database] = None,
        max_results: int = MAX_RESULTS,
        min_position: int = MIN_POSITION,
        headless: bool = HEADLESS,
        only_active: bool = ONLY_ACTIVE,
    ):
        self.db = db or Database()
        self.max_results = max_results
        self.min_position = min_position
        self.headless = headless
        self.only_active = only_active

    def build_search_url(self, query: str) -> str:
        encoded_query = urllib.parse.quote_plus(query.strip())
        return f"https://trangvangvietnam.com/search.asp?keyword={encoded_query}"

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
                "--lang=vi-VN",
            ]
        )
        context = await browser.new_context(
            user_agent=USER_AGENTS[0],
            viewport={"width": 1366, "height": 768},
            locale="vi-VN",
        )
        # Anti-detect evasion script
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'vi', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)
        page = await context.new_page()
        page.set_default_timeout(TIMEOUT)
        return browser, context, page

    async def crawl_query(
        self,
        query: str,
        limit: Optional[int] = None,
        min_position: Optional[int] = None,
    ) -> int:
        """
        Crawls businesses from Trang Vang Vietnam for a specific keyword.
        Prioritizes results starting from min_position (default: 20) onwards.
        """
        max_items = limit or self.max_results
        start_pos = min_position if min_position is not None else self.min_position
        search_url = self.build_search_url(query)

        logger.info(f"========================================================")
        logger.info(f"🚀 TRANG VÀNG VIỆT NAM CRAWLER")
        logger.info(f"📌 Keyword            : '{query}'")
        logger.info(f"🎯 Min Position (STT) : {start_pos}+ (Bắt đầu từ vị trí {start_pos} trở đi)")
        logger.info(f"🎯 Max Results        : {max_items}")
        logger.info(f"🔗 Search URL         : {search_url}")
        logger.info(f"========================================================")

        saved_count = 0

        async with async_playwright() as p:
            browser, context, page = await self._setup_browser(p)
            try:
                # 1. Initial navigation to search query
                logger.info("Connecting to Trang Vang search engine...")
                await page.goto(search_url, wait_until="domcontentloaded", timeout=TIMEOUT)
                await asyncio.sleep(1.5)

                page_num = 1
                while saved_count < max_items:
                    logger.info(f"\n📄 [Page {page_num}] Extracting listings (Current URL: {page.url})...")
                    cards = await page.evaluate(JS_EXTRACT_CARDS)
                    if not cards:
                        logger.info(f"No listings found on page {page_num}. Ending crawl.")
                        break

                    logger.info(f"Found {len(cards)} listings on page {page_num}.")

                    page_saved = 0
                    for c in cards:
                        stt = c["stt"] if c["stt"] is not None else ((page_num - 1) * len(cards) + c["domIndex"])

                        # Filter: Only collect listings from min_position onwards
                        if stt < start_pos:
                            continue

                        name = clean_text(c.get("name"))
                        if not name:
                            continue

                        # Extract and normalize phone numbers
                        phone = ""
                        for p_raw in c.get("phones", []):
                            cleaned = clean_phone(p_raw)
                            if cleaned:
                                phone = cleaned
                                break

                        email = c.get("emails", [""])[0] if c.get("emails") else ""
                        category = clean_text(c.get("category"))
                        address = clean_text(c.get("address"))
                        website = c.get("website", "")
                        listing_url = c.get("link") or f"https://trangvangvietnam.com/dn/{urllib.parse.quote(name)}"

                        item = {
                            "name": name,
                            "phone": phone,
                            "email": email,
                            "category": category,
                            "status": "Đang hoạt động",
                            "is_active": 1,
                            "is_checked": 0,
                            "address": address,
                            "website": website,
                            "rating": None,
                            "reviews_count": None,
                            "google_maps_url": listing_url,
                            "search_query": f"trangvang:{query}",
                        }

                        res = self.db.upsert_business(item)
                        saved_count += 1
                        page_saved += 1

                        logger.info(
                            f"[{res.upper()}] STT #{stt} | {name} | "
                            f"📞 Phone: {phone or 'N/A'} | "
                            f"✉️ Email: {email or 'N/A'} | "
                            f"🏷️ Cat: {category or 'N/A'}"
                        )

                        if saved_count >= max_items:
                            break

                    logger.info(f"-> Page {page_num} processed. Collected {page_saved} businesses (Total: {saved_count}/{max_items}).")

                    if saved_count >= max_items:
                        logger.info(f"🎯 Target limit ({max_items}) reached!")
                        break

                    # Look for next page button inside #paging
                    next_btn = page.locator(f'#paging a[href*="page={page_num + 1}"], #paging a:has-text("Tiếp")').first
                    if await next_btn.count() == 0:
                        logger.info("Reached the last page of search results.")
                        break

                    logger.info(f"Navigating to page {page_num + 1}...")
                    try:
                        await next_btn.click()
                        await page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT)
                        await asyncio.sleep(2.0)
                        try:
                            await page.wait_for_selector(".tvx-card", timeout=5000)
                        except Exception:
                            pass
                        page_num += 1
                    except Exception as e:
                        logger.warning(f"Could not click next page link: {e}")
                        break

            except Exception as e:
                logger.error(f"Error during Trang Vang crawl for keyword '{query}': {e}", exc_info=True)
            finally:
                await context.close()
                await browser.close()

        logger.info(f"✅ Completed keyword '{query}'. Total saved from position {start_pos}+: {saved_count} businesses.")
        return saved_count

    async def crawl_multiple(
        self,
        queries: List[str],
        limit_per_query: Optional[int] = None,
        min_position: Optional[int] = None,
    ) -> int:
        total = 0
        for idx, q in enumerate(queries, 1):
            logger.info(f"\n>>> [TRANG VÀNG] PROGRESS: Keyword {idx}/{len(queries)}: '{q}' <<<")
            cnt = await self.crawl_query(q, limit=limit_per_query, min_position=min_position)
            total += cnt
            await asyncio.sleep(2)
        return total
