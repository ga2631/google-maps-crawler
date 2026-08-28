import re
from typing import Dict, Any, Optional

try:
    from playwright.async_api import Page, Locator
except ImportError:
    Page = Any  # type: ignore
    Locator = Any  # type: ignore

PHONE_REGEX = re.compile(r'(\+?84|0|1[89]00)(?:[\s.-]?\d){6,10}\b')
COORDS_REGEX = re.compile(r'@([0-9\.\-]+),([0-9\.\-]+)')
URL_COORDS_REGEX = re.compile(r'!3d([0-9\.\-]+)!4d([0-9\.\-]+)')

CLOSED_KEYWORDS = [
    "đã đóng cửa vĩnh viễn",
    "tạm thời đóng cửa",
    "đóng cửa vĩnh viễn",
    "permanently closed",
    "temporarily closed",
    "closed permanently",
]

ACTIVE_KEYWORDS = [
    "đang mở cửa",
    "mở cả ngày",
    "mở cửa 24/24",
    "sắp đóng cửa",
    "sắp mở cửa",
    "mở cửa",
    "open 24 hours",
    "open",
    "closes soon",
    "opens soon",
]

def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    # Strip private use unicode characters (icons / glyphs like \ue8b5, \ue5cf)
    cleaned = re.sub(r'[\uE000-\uF8FF\u200B-\u200D\uFEFF]', '', text)
    # Normalize spaces and newlines
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def clean_phone(phone_raw: Optional[str]) -> str:
    if not phone_raw:
        return ""
    # Extract phone numbers using regex
    match = PHONE_REGEX.search(phone_raw)
    raw = match.group(0) if match else phone_raw.strip()
    
    # Strip any characters other than digits and '+'
    digits = re.sub(r'[^\d+]', '', raw)
    
    # 1. Bỏ qua các số bàn TP.HCM bắt đầu bằng 028, +8428, 8428
    if (
        digits.startswith("+8428")
        or digits.startswith("8428")
        or digits.startswith("+84028")
        or digits.startswith("84028")
        or digits.startswith("028")
    ):
        return ""

    # 2. Xoá đầu số quốc gia +84 / 84 và chuẩn hoá về đầu 0 (hoặc giữ đầu tổng đài 1800/1900)
    if digits.startswith("+84"):
        digits = digits[3:]
        if not (digits.startswith("1800") or digits.startswith("1900")) and not digits.startswith("0"):
            digits = "0" + digits
    elif digits.startswith("84") and len(digits) >= 11:
        digits = digits[2:]
        if not (digits.startswith("1800") or digits.startswith("1900")) and not digits.startswith("0"):
            digits = "0" + digits

    # 3. Kiểm tra lại sau khi chuẩn hoá nếu có dạng 028 hoặc 28 thì loại bỏ
    if digits.startswith("028") or digits.startswith("28"):
        return ""

    if len(digits) < 7:
        return ""

    return digits

def determine_activity_status(status_text: str) -> tuple[str, int]:
    """
    Returns (status_label, is_active)
    is_active: 1 if active, 0 if permanently/temporarily closed
    """
    status_lower = status_text.lower()
    
    for kw in CLOSED_KEYWORDS:
        if kw in status_lower:
            return status_text, 0

    for kw in ACTIVE_KEYWORDS:
        if kw in status_lower:
            return status_text, 1

    # If status is unknown but not explicitly closed, treat as active
    if status_text:
        return status_text, 1
    return "Đang hoạt động", 1

def extract_coordinates_from_url(url: str) -> tuple[Optional[float], Optional[float]]:
    if not url:
        return None, None
    
    # Try @lat,lng
    match = COORDS_REGEX.search(url)
    if match:
        try:
            return float(match.group(1)), float(match.group(2))
        except ValueError:
            pass

    # Try !3dlat!4dlng
    match2 = URL_COORDS_REGEX.search(url)
    if match2:
        try:
            return float(match2.group(1)), float(match2.group(2))
        except ValueError:
            pass

    return None, None

async def parse_business_details(page: Page, url: str = "", query: str = "") -> Dict[str, Any]:
    """
    Extracts business details from the active Google Maps detail panel on the page.
    """
    # 1. Business Name
    name = ""
    name_selectors = [
        "h1.DUwDvf",
        "h1.fontHeadlineLarge",
        "div.TIHn2 h1",
        "h1",
    ]
    for sel in name_selectors:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=1000):
                name = clean_text(await loc.inner_text())
                if name:
                    break
        except Exception:
            continue

    # 2. Category / Industry
    category = ""
    category_selectors = [
        "button[jsaction*='pane.rating.category']",
        "button.DkEaL",
        "span.DkEaL",
        "button[jsaction*='category']",
        "div.fontBodyMedium span button",
    ]
    for sel in category_selectors:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=800):
                category = clean_text(await loc.inner_text())
                if category:
                    break
        except Exception:
            continue

    # 3. Status / Opening Hours
    status = ""
    status_selectors = [
        "div[data-item-id='oh']",
        "div.t39EBf",
        "span.ZDu9vd",
        "div.OM3Du",
        "div[aria-label*='Giờ mở cửa']",
        "div[aria-label*='Mở cửa']",
        "div[aria-label*='Đóng cửa']",
        "div[aria-label*='Hours']",
    ]
    for sel in status_selectors:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=800):
                text = clean_text(await loc.inner_text())
                if text:
                    # Take first line if multiple lines (e.g. "Đang mở cửa ⋅ Đóng cửa lúc 22:00")
                    status = text.split("⋅")[0].strip() if "⋅" in text else text
                    break
        except Exception:
            continue

    # Check for permanently / temporarily closed banner
    try:
        closed_banner = page.locator("div.fontBodyMedium:has-text('đóng cửa'), div.fontBodyMedium:has-text('closed')").first
        if await closed_banner.is_visible(timeout=500):
            banner_text = clean_text(await closed_banner.inner_text())
            if banner_text:
                status = banner_text
    except Exception:
        pass

    status_label, is_active = determine_activity_status(status)

    # 4. Phone Number
    phone = ""
    phone_selectors = [
        "button[data-item-id^='phone:']",
        "button[data-tooltip*='số điện thoại']",
        "button[data-tooltip*='Sao chép số điện thoại']",
        "button[aria-label*='Số điện thoại']",
        "button[aria-label*='Điện thoại']",
        "button[data-item-id*='phone']",
        "a[href^='tel:']",
    ]
    for sel in phone_selectors:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=800):
                text = await loc.get_attribute("aria-label") or await loc.inner_text()
                phone = clean_phone(text)
                if phone:
                    break
        except Exception:
            continue

    # Fallback search for phone in all action buttons
    if not phone:
        try:
            buttons = page.locator("button[data-item-id]")
            count = await buttons.count()
            for i in range(count):
                btn = buttons.nth(i)
                item_id = await btn.get_attribute("data-item-id") or ""
                if "phone:" in item_id:
                    phone = clean_phone(item_id.replace("phone:", ""))
                    if phone:
                        break
                text = await btn.inner_text()
                if PHONE_REGEX.search(text):
                    phone = clean_phone(text)
                    if phone:
                        break
        except Exception:
            pass

    # 5. Address
    address = ""
    address_selectors = [
        "button[data-item-id='address']",
        "button[data-item-id*='address']",
        "button[aria-label*='Địa chỉ']",
        "button[aria-label*='Address']",
    ]
    for sel in address_selectors:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=800):
                text = await loc.get_attribute("aria-label") or await loc.inner_text()
                # Remove "Địa chỉ: " prefix if present
                address = clean_text(re.sub(r'^(Địa chỉ|Address):\s*', '', text, flags=re.IGNORECASE))
                if address:
                    break
        except Exception:
            continue

    # 6. Website
    website = ""
    website_selectors = [
        "a[data-item-id='authority']",
        "a[aria-label*='Trang web']",
        "a[aria-label*='Website']",
    ]
    for sel in website_selectors:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=800):
                website = await loc.get_attribute("href") or clean_text(await loc.inner_text())
                if website:
                    break
        except Exception:
            continue

    # 7. Rating & Reviews
    rating = None
    reviews_count = None
    try:
        rating_elem = page.locator("div.F7nice span[aria-hidden='true']").first
        if await rating_elem.is_visible(timeout=800):
            rating_text = clean_text(await rating_elem.inner_text()).replace(",", ".")
            try:
                rating = float(rating_text)
            except ValueError:
                pass

        reviews_elem = page.locator("div.F7nice span:last-child").first
        if await reviews_elem.is_visible(timeout=800):
            reviews_text = clean_text(await reviews_elem.inner_text())
            reviews_match = re.search(r'[\(\[]?([\d.,]+)[\)\]]?', reviews_text)
            if reviews_match:
                count_str = reviews_match.group(1).replace(".", "").replace(",", "")
                try:
                    reviews_count = int(count_str)
                except ValueError:
                    pass
    except Exception:
        pass

    # 8. Coordinates & Current URL
    current_url = page.url or url
    lat, lng = extract_coordinates_from_url(current_url)

    return {
        "name": name,
        "phone": phone,
        "category": category,
        "status": status_label,
        "is_active": is_active,
        "address": address,
        "website": website,
        "rating": rating,
        "reviews_count": reviews_count,
        "google_maps_url": current_url,
        "search_query": query,
        "latitude": lat,
        "longitude": lng,
    }
