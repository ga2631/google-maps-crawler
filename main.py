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
    print("\n" + "="*50)
    print(" 📊 THỐNG KÊ DỮ LIỆU DOANH NGHIỆP TRONG SQLITE")
    print("="*50)
    print(f"📁 Đường dẫn DB        : {db.db_path}")
    print(f"🏢 Tổng số doanh nghiệp: {stats['total_businesses']}")
    print(f"🟢 Đang hoạt động       : {stats['active_businesses']}")
    print(f"✅ Đã check thông tin  : {stats['checked_businesses']}")
    print(f"⏳ Chưa check          : {stats['unchecked_businesses']}")
    print(f"📞 Có số điện thoại     : {stats['with_phone']}")
    print(f"🏷️  Số ngành nghề khác nhau: {stats['distinct_categories']}")
    print("-" * 50)
    
    if stats["top_categories"]:
        print("📌 Top 5 ngành nghề phổ biến:")
        table_cats = [[c["category"], c["count"]] for c in stats["top_categories"][:5]]
        print(tabulate(table_cats, headers=["Ngành nghề", "Số lượng"], tablefmt="grid"))
    
    if stats["top_queries"]:
        print("\n🔍 Top 5 từ khóa đã cào:")
        table_queries = [[q["search_query"], q["count"]] for q in stats["top_queries"][:5]]
        print(tabulate(table_queries, headers=["Từ khóa", "Số lượng"], tablefmt="grid"))
    print("="*50 + "\n")

def display_list(db: Database, limit: int = 15):
    rows = db.list_businesses(limit=limit)
    if not rows:
        print("⚠️ Chưa có dữ liệu trong database.")
        return
    
    print(f"\n📋 Danh sách {len(rows)} doanh nghiệp gần nhất:")
    table_data = []
    for r in rows:
        name = (r["name"][:25] + "..") if len(r["name"] or "") > 25 else (r["name"] or "")
        phone = r["phone"] or "-"
        cat = (r["category"][:20] + "..") if len(r["category"] or "") > 20 else (r["category"] or "-")
        status = r["status"] or "-"
        checked_str = "✅ Đã check" if r.get("is_checked") == 1 else "⏳ Chưa"
        addr = (r["address"][:25] + "..") if len(r["address"] or "") > 25 else (r["address"] or "-")
        table_data.append([r["id"], name, phone, cat, status, checked_str, addr])
        
    print(tabulate(
        table_data,
        headers=["ID", "Tên", "Điện thoại", "Ngành nghề", "Trạng thái", "Đã check", "Địa chỉ"],
        tablefmt="grid"
    ))

async def main():
    parser = argparse.ArgumentParser(
        description="Google Maps Business Scraper for Ho Chi Minh City (Không dùng API - Lưu SQLite)"
    )
    
    parser.add_argument("-q", "--query", type=str, help="Từ khóa cần cào (vd: 'công ty phần mềm Quận 1 Hồ Chí Minh')")
    parser.add_argument("-f", "--file", type=str, default=KEYWORDS_FILE, help=f"Đường dẫn file chứa danh sách từ khóa (mặc định: {KEYWORDS_FILE})")
    parser.add_argument("-l", "--limit", type=int, default=MAX_RESULTS, help=f"Số lượng kết quả tối đa cho mỗi từ khóa (mặc định: {MAX_RESULTS})")
    parser.add_argument("--headful", action="store_true", help="Chạy browser hiển thị giao diện (mặc định headless)")
    parser.add_argument("--all-status", action="store_true", help="Lưu cả doanh nghiệp đã đóng cửa (mặc định chỉ lưu đang hoạt động)")
    parser.add_argument("--stats", action="store_true", help="Xem thống kê dữ liệu hiện có trong SQLite")
    parser.add_argument("--list", action="store_true", help="Xem danh sách doanh nghiệp vừa cào")
    parser.add_argument("--clean-phones", action="store_true", help="Chuẩn hoá số điện thoại hiện có trong DB (xoá +84, bỏ số bàn 028/+8428)")
    parser.add_argument("--mark-checked", type=int, metavar="ID", help="Đánh dấu doanh nghiệp đã kiểm tra thông tin theo ID")
    parser.add_argument("--unmark-checked", type=int, metavar="ID", help="Bỏ đánh dấu kiểm tra thông tin theo ID")
    parser.add_argument("--export-csv", type=str, metavar="PATH", help="Xuất toàn bộ dữ liệu ra file CSV (vd: data/output.csv)")
    parser.add_argument("--export-json", type=str, metavar="PATH", help="Xuất toàn bộ dữ liệu ra file JSON (vd: data/output.json)")
    parser.add_argument("--db", type=str, default=DB_PATH, help=f"Đường dẫn file SQLite DB (mặc định: {DB_PATH})")

    args = parser.parse_args()
    db = Database(db_path=args.db)

    if args.clean_phones:
        res = db.clean_existing_phones()
        print("=" * 50)
        print(" 📞 KẾT QUẢ CHUẨN HOÁ SỐ ĐIỆN THOẠI TRONG DB")
        print("=" * 50)
        print(f"📊 Tổng số SĐT đã kiểm tra   : {res['total_checked']}")
        print(f"🔄 Số bản ghi đã chuẩn hoá (+84): {res['updated']}")
        print(f"🗑️  Số SĐT bàn 028/+8428 đã xoá : {res['removed_028']}")
        print("=" * 50)
        return

    if args.mark_checked is not None:
        if db.update_checked_status(args.mark_checked, 1):
            print(f"✅ Đã đánh dấu DOANH NGHIỆP ID {args.mark_checked} là ĐÃ CHECK THÔNG TIN.")
        else:
            print(f"❌ Không tìm thấy doanh nghiệp có ID {args.mark_checked}.")
        return

    if args.unmark_checked is not None:
        if db.update_checked_status(args.unmark_checked, 0):
            print(f"✅ Đã chuyển DOANH NGHIỆP ID {args.unmark_checked} về trạng thái CHƯA CHECK.")
        else:
            print(f"❌ Không tìm thấy doanh nghiệp có ID {args.unmark_checked}.")
        return

    if args.stats:
        display_stats(db)
        return

    if args.list:
        display_list(db)
        return

    if args.export_csv:
        count = db.export_to_csv(args.export_csv, only_active=not args.all_status)
        print(f"✅ Đã xuất {count} doanh nghiệp ra file CSV: {args.export_csv}")
        return

    if args.export_json:
        count = db.export_to_json(args.export_json, only_active=not args.all_status)
        print(f"✅ Đã xuất {count} doanh nghiệp ra file JSON: {args.export_json}")
        return

    # Determine keywords to scrape
    queries = []
    if args.query:
        queries = [args.query]
    else:
        queries = load_keywords(args.file)
        if not queries:
            print(f"⚠️ Không tìm thấy từ khóa nào trong file {args.file}!")
            print("👉 Bạn có thể chỉ định từ khóa bằng tham số -q 'từ khóa' hoặc thêm vào file config/keywords.txt.")
            sys.exit(1)

    is_headless = not args.headful if args.headful else HEADLESS
    only_active = not args.all_status if args.all_status else ONLY_ACTIVE

    print("="*60)
    print("🚀 GOOGLE MAPS BUSINESS CRAWLER - KHU VỰC HỒ CHÍ MINH")
    print("="*60)
    print(f"📌 Số lượng từ khóa      : {len(queries)}")
    print(f"🎯 Giới hạn mỗi từ khóa   : {args.limit} kết quả")
    print(f"🟢 Chỉ lấy đang hoạt động : {only_active}")
    print(f"🖥️  Chế độ hiển thị        : {'Headless' if is_headless else 'Giao diện trực quan'}")
    print(f"💾 Cơ sở dữ liệu SQLite   : {args.db}")
    print("="*60)

    try:
        from src.scraper import GoogleMapsScraper
    except ImportError as e:
        print("\n❌ Lỗi: Chưa cài đặt thư viện Playwright hoặc dependencies.")
        print("👉 Nếu chạy trực tiếp: hãy chạy 'pip install -r requirements.txt && playwright install chromium'")
        print("👉 Hoặc chạy đơn giản qua Docker: 'docker compose up'")
        sys.exit(1)

    scraper = GoogleMapsScraper(
        db=db,
        max_results=args.limit,
        headless=is_headless,
        only_active=only_active,
    )

    total_scraped = await scraper.crawl_multiple(queries, limit_per_query=args.limit)
    print("\n" + "="*60)
    print(f"🎉 HOÀN THÀNH TẤT CẢ! Đã thu thập và lưu {total_scraped} lượt doanh nghiệp.")
    print("="*60)
    display_stats(db)

if __name__ == "__main__":
    asyncio.run(main())
