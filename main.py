import argparse
import asyncio
import sys
from pathlib import Path
try:
    from tabulate import tabulate
except ImportError:
    def tabulate(rows, headers=None, tablefmt=None):
        out = []
        if headers:
            out.append(" | ".join(str(h) for h in headers))
            out.append("-" * 40)
        for r in rows:
            out.append(" | ".join(str(c) for c in r))
        return "\n".join(out)

from src.config import (
    DB_PATH,
    HEADLESS,
    MAX_RESULTS,
    KEYWORDS_FILE,
    ONLY_ACTIVE,
    DEFAULT_SOURCE,
    MIN_POSITION,
)
from src.db import Database

def load_keywords(file_path: str) -> list[str]:
    p = Path(file_path)
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
    return lines

def display_stats(db: Database):
    stats = db.get_stats()
    print("\n" + "="*55)
    print(" 📊 BUSINESS DATABASE STATISTICS (SQLITE)")
    print("="*55)
    print(f"📁 Database Path       : {db.db_path}")
    print(f"🏢 Total Businesses    : {stats['total_businesses']}")
    print(f"🟢 Active Businesses   : {stats['active_businesses']}")
    print(f"✅ Verified / Checked  : {stats['checked_businesses']}")
    print(f"⏳ Unchecked           : {stats['unchecked_businesses']}")
    print(f"📞 With Phone Number   : {stats['with_phone']}")
    print(f"✉️  With Email          : {stats.get('with_email', 0)}")
    print(f"🏷️  Distinct Categories : {stats['distinct_categories']}")
    print("-" * 55)
    
    if stats["top_categories"]:
        print("📌 Top 5 Categories:")
        table_cats = [[c["category"], c["count"]] for c in stats["top_categories"][:5]]
        print(tabulate(table_cats, headers=["Category", "Count"], tablefmt="grid"))
    
    if stats["top_queries"]:
        print("\n🔍 Top 5 Search Queries / Sources:")
        table_queries = [[q["search_query"], q["count"]] for q in stats["top_queries"][:5]]
        print(tabulate(table_queries, headers=["Search Query", "Count"], tablefmt="grid"))
    print("="*55 + "\n")

def display_list(db: Database, limit: int = 15):
    rows = db.list_businesses(limit=limit)
    if not rows:
        print("⚠️ No data available in database.")
        return
    
    print(f"\n📋 Latest {len(rows)} businesses:")
    table_data = []
    for r in rows:
        name = (r["name"][:25] + "..") if len(r["name"] or "") > 25 else (r["name"] or "")
        phone = r["phone"] or "-"
        email = (r.get("email")[:18] + "..") if len(r.get("email") or "") > 18 else (r.get("email") or "-")
        cat = (r["category"][:18] + "..") if len(r["category"] or "") > 18 else (r["category"] or "-")
        status = r["status"] or "-"
        checked_str = "✅ Checked" if r.get("is_checked") == 1 else "⏳ Unchecked"
        addr = (r["address"][:22] + "..") if len(r["address"] or "") > 22 else (r["address"] or "-")
        table_data.append([r["id"], name, phone, email, cat, status, checked_str, addr])
        
    print(tabulate(
        table_data,
        headers=["ID", "Name", "Phone", "Email", "Category", "Status", "Checked", "Address"],
        tablefmt="grid"
    ))

async def main():
    parser = argparse.ArgumentParser(
        description="Multi-Source Business Scraper (Google Maps & Trang Vàng Việt Nam - SQLite Storage)"
    )
    
    parser.add_argument("-q", "--query", type=str, help="Specific search keyword (e.g. 'may mặc', 'software company Da Nang', 'cafe Hanoi')")
    parser.add_argument("-s", "--source", type=str, default=DEFAULT_SOURCE, choices=["trangvang", "gmaps", "all"], help=f"Data source to crawl: 'trangvang', 'gmaps', or 'all' (default: {DEFAULT_SOURCE})")
    parser.add_argument("--min-position", type=int, default=MIN_POSITION, help=f"Minimum display position on Trang Vàng (default: {MIN_POSITION} - start from position 20 onwards)")
    parser.add_argument("-f", "--file", type=str, default=KEYWORDS_FILE, help=f"Path to file with keywords (default: {KEYWORDS_FILE})")
    parser.add_argument("-l", "--limit", type=int, default=MAX_RESULTS, help=f"Maximum results per keyword (default: {MAX_RESULTS})")
    parser.add_argument("--headful", action="store_true", help="Run browser in headful mode with visible UI (default: headless)")
    parser.add_argument("--all-status", action="store_true", help="Save closed businesses as well (default: only active)")
    parser.add_argument("--stats", action="store_true", help="View database statistics")
    parser.add_argument("--list", action="store_true", help="List recent businesses in database")
    parser.add_argument("--clean-phones", action="store_true", help="Normalize phone numbers in DB (+84 -> 0, remove 1900/1800 and landlines)")
    parser.add_argument("--mark-checked", type=int, metavar="ID", help="Mark business as checked by ID")
    parser.add_argument("--unmark-checked", type=int, metavar="ID", help="Unmark business check status by ID")
    parser.add_argument("--export-csv", type=str, metavar="PATH", help="Export all data to a CSV file (e.g. data/output.csv)")
    parser.add_argument("--export-json", type=str, metavar="PATH", help="Export all data to a JSON file (e.g. data/output.json)")
    parser.add_argument("--db", type=str, default=DB_PATH, help=f"Path to SQLite DB file (default: {DB_PATH})")

    args = parser.parse_args()
    db = Database(db_path=args.db)

    if args.clean_phones:
        res = db.clean_existing_phones()
        print("=" * 50)
        print(" 📞 PHONE NUMBER NORMALIZATION RESULT")
        print("=" * 50)
        print(f"📊 Total phones checked        : {res['total_checked']}")
        print(f"🔄 Standardized (+84 -> 0)     : {res['updated']}")
        print(f"🗑️  Removed invalid / hotlines  : {res.get('removed_invalid', 0)}")
        print("=" * 50)
        return

    if args.mark_checked is not None:
        if db.update_checked_status(args.mark_checked, 1):
            print(f"✅ Marked business ID {args.mark_checked} as CHECKED.")
        else:
            print(f"❌ Business ID {args.mark_checked} not found.")
        return

    if args.unmark_checked is not None:
        if db.update_checked_status(args.unmark_checked, 0):
            print(f"✅ Reverted business ID {args.unmark_checked} to UNCHECKED status.")
        else:
            print(f"❌ Business ID {args.unmark_checked} not found.")
        return

    if args.stats:
        display_stats(db)
        return

    if args.list:
        display_list(db)
        return

    if args.export_csv:
        count = db.export_to_csv(args.export_csv, only_active=not args.all_status)
        print(f"✅ Exported {count} businesses to CSV file: {args.export_csv}")
        return

    if args.export_json:
        count = db.export_to_json(args.export_json, only_active=not args.all_status)
        print(f"✅ Exported {count} businesses to JSON file: {args.export_json}")
        return

    # Determine keywords to scrape
    queries = []
    if args.query:
        queries = [args.query]
    else:
        queries = load_keywords(args.file)
        if not queries:
            print(f"⚠️ No keywords found in file: {args.file}!")
            print("👉 Specify keywords using -q 'keyword' or add lines to config/keywords.txt.")
            sys.exit(1)

    is_headless = not args.headful if args.headful else HEADLESS
    only_active = not args.all_status if args.all_status else ONLY_ACTIVE

    print("="*60)
    print("🚀 MULTI-SOURCE BUSINESS CRAWLER")
    print("="*60)
    print(f"📌 Data Source(s)         : {args.source.upper()}")
    print(f"📌 Total Keywords         : {len(queries)}")
    print(f"🎯 Limit Per Keyword      : {args.limit} results")
    if args.source in ("trangvang", "all"):
        print(f"🎯 Trang Vàng Min Pos     : {args.min_position}+ (Vị trí >= {args.min_position})")
    print(f"🟢 Only Active Businesses : {only_active}")
    print(f"🖥️  Browser Mode           : {'Headless' if is_headless else 'Headful (Visible)'}")
    print(f"💾 SQLite Database        : {args.db}")
    print("="*60)

    total_scraped = 0

    # 1. Crawl Trang Vàng Việt Nam
    if args.source in ("trangvang", "all"):
        try:
            from src.trangvang_scraper import TrangVangScraper
            tv_scraper = TrangVangScraper(
                db=db,
                max_results=args.limit,
                min_position=args.min_position,
                headless=is_headless,
                only_active=only_active,
            )
            print(f"\n⚡ [1/2] Launching Trang Vàng Việt Nam crawler (Position {args.min_position}+)...")
            tv_count = await tv_scraper.crawl_multiple(
                queries,
                limit_per_query=args.limit,
                min_position=args.min_position
            )
            total_scraped += tv_count
            print(f"✅ Trang Vàng crawl finished. Saved: {tv_count} businesses.")
        except ImportError as e:
            print(f"\n❌ Error importing Trang Vàng scraper: {e}")
        except Exception as e:
            print(f"\n❌ Error during Trang Vàng crawl: {e}")

    # 2. Crawl Google Maps
    if args.source in ("gmaps", "all"):
        try:
            from src.scraper import GoogleMapsScraper
            gmaps_scraper = GoogleMapsScraper(
                db=db,
                max_results=args.limit,
                headless=is_headless,
                only_active=only_active,
            )
            print(f"\n⚡ [2/2] Launching Google Maps crawler...")
            gmaps_count = await gmaps_scraper.crawl_multiple(queries, limit_per_query=args.limit)
            total_scraped += gmaps_count
            print(f"✅ Google Maps crawl finished. Saved: {gmaps_count} businesses.")
        except ImportError as e:
            print(f"\n❌ Error importing Google Maps scraper: {e}")
        except Exception as e:
            print(f"\n❌ Error during Google Maps crawl: {e}")

    print("\n" + "="*60)
    print(f"🎉 ALL TASKS COMPLETED! Total records collected & saved: {total_scraped}")
    print("="*60)
    display_stats(db)

if __name__ == "__main__":
    asyncio.run(main())
