import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

# Database configuration
DB_DIR = BASE_DIR / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = os.getenv("DB_PATH", str(DB_DIR / "businesses.db"))

# Crawler settings
HEADLESS = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")
MAX_RESULTS = int(os.getenv("MAX_RESULTS", "50"))
TIMEOUT = int(os.getenv("TIMEOUT", "30000"))  # ms
SCROLL_DELAY = float(os.getenv("SCROLL_DELAY", "2.0"))  # seconds
ITEM_DELAY = float(os.getenv("ITEM_DELAY", "1.5"))  # seconds
CONCURRENCY = int(os.getenv("CONCURRENCY", "1"))

# Google Maps settings
MAPS_LANG = os.getenv("MAPS_LANG", "vi")

# Keywords file
CONFIG_DIR = BASE_DIR / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
KEYWORDS_FILE = os.getenv("KEYWORDS_FILE", str(CONFIG_DIR / "keywords.txt"))

# Only save active businesses
ONLY_ACTIVE = os.getenv("ONLY_ACTIVE", "true").lower() in ("true", "1", "yes")

# Source and position filtering settings
DEFAULT_SOURCE = os.getenv("CRAWL_SOURCE", "all")  # 'gmaps', 'trangvang', or 'all'
MIN_POSITION = int(os.getenv("MIN_POSITION", "20"))  # Start from position 20 onwards for Trang Vang

