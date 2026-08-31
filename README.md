# 🏢 Multi-Source Business Scraper (Google Maps & Trang Vàng Việt Nam)

A lightweight, robust tool to scrape business data from **Google Maps** and **Trang Vàng Việt Nam** (`https://trangvangvietnam.com`) based on custom search keywords, automatically filter for **active businesses**, prioritize results from **position 20 onwards**, securely store data in **SQLite**, and run anywhere using **Docker**.

> 💡 **Highlights**:
>
> - **Multi-Source Support**: Crawl from **Trang Vàng Việt Nam** (`trangvangvietnam.com`), **Google Maps**, or **both sources simultaneously**.
> - **Display Position Filtering**: Specifically supports starting from **display position 20 onwards** (`--min-position 20`) on Trang Vàng Việt Nam.
> - **No Paid APIs Required**: Direct browser automation via Playwright without quota fees.
> - **Anti-Detect / Stealth Mode**: Custom Playwright context with stealth headers and anti-bot evasion to handle dynamic pages and Cloudflare protection smoothly.
> - **Phone Number Normalization**: Automatically standardizes country code `+84` to `0...` (e.g. `+84901234567` -> `0901234567`), while filtering out toll-free hotline numbers (`1900`, `1800`,...) and unwanted landline prefixes.
> - **Email & Website Extraction**: Automatically extracts company emails, official websites, categories, and full addresses.
> - **Smart Deduplication**: Intelligent UPSERT in SQLite based on unique URL or (Name + Phone).
> - **Docker Ready**: Run out-of-the-box in any environment with persistent SQLite database volume mounting.

---

## 📋 Extracted Fields

| Field | Database Column | Description & Example |
| :--- | :--- | :--- |
| **Business Name** | `name` | ABC Tech Solutions Co., Ltd |
| **Phone Number** | `phone` | `0909123456` / `0389123456` (Normalized +84 -> 0, filtered 1900/1800) |
| **Email** | `email` | `contact@company.com.vn` (Extracted from Trang Vàng / listings) |
| **Category / Industry** | `category` | May Mặc, Logistics, Phần Mềm, Xây Dựng,... |
| **Operational Status** | `status` | Đang hoạt động, Open 24 hours, Active |
| **Is Active?** | `is_active` | `1` (Active) / `0` (Closed) |
| **Is Checked?** | `is_checked` | `0` (Unchecked) / `1` (Checked) |
| **Address** | `address` | 123 Nguyen Hue Street, District 1, Ho Chi Minh City |
| **Website** | `website` | `https://example.com` |
| **Rating** | `rating` | `4.8` |
| **Reviews Count** | `reviews_count` | `150` |
| **Source URL** | `google_maps_url` | Trang Vàng listing URL or Google Maps place URL |
| **Search Query** | `search_query` | `trangvang:may mặc` or `software company Da Nang` |

---

## 🚀 Docker Quickstart (Recommended)

No need to install Python or Chromium on your machine; only Docker Desktop is required.

### 1. Build the image

```bash
docker compose build
```

### 2. Crawl using keyword list in `config/keywords.txt`

```bash
# Crawl all sources (Trang Vàng + Google Maps)
docker compose up
```

### 3. Crawl specifically from Trang Vàng Việt Nam (Position 20+)

```bash
# Crawl keyword 'may mặc' starting from position 20 onwards
docker compose run --rm crawler -q "may mặc" -s trangvang --min-position 20 -l 30

# Crawl keyword 'logistics' from Trang Vàng
docker compose run --rm crawler -q "logistics" -s trangvang -l 50
```

### 4. View statistics in SQLite

```bash
docker compose run --rm crawler --stats
```

### 5. Mark/Unmark business as verified

```bash
# Mark business ID 10 as checked
docker compose run --rm crawler --mark-checked 10

# Unmark business ID 10
docker compose run --rm crawler --unmark-checked 10
```

### 6. Export data to CSV or JSON

```bash
# Export to CSV
docker compose run --rm crawler --export-csv /app/data/businesses.csv

# Export to JSON
docker compose run --rm crawler --export-json /app/data/businesses.json
```

---

## 💻 Local Setup with Python (Without Docker)

### 1. Environment Setup

```bash
# Create virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate  # On Linux/macOS
# .venv\Scripts\activate   # On Windows

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright Chromium browser
playwright install chromium
```

### 2. Run the Crawler

```bash
# 1. Crawl Trang Vàng Việt Nam from position 20 onwards
python main.py -q "may mặc" -s trangvang --min-position 20 -l 30

# 2. Crawl Google Maps directly
python main.py -q "software company Da Nang" -s gmaps -l 20

# 3. Crawl both sources for keywords in config/keywords.txt
python main.py -f config/keywords.txt -s all -l 50

# 4. View recently scraped businesses (table display)
python main.py --list

# 5. View database overview statistics
python main.py --stats

# 6. Normalize / clean existing phone numbers in DB
python main.py --clean-phones

# 7. Export data to CSV or JSON
python main.py --export-csv data/businesses.csv
python main.py --export-json data/businesses.json
```

---

## ⚙️ Command Line Options (CLI Arguments)

| Argument | Description | Default |
| :--- | :--- | :--- |
| `-q`, `--query` | Specific search keyword | `None` |
| `-s`, `--source` | Data source (`trangvang`, `gmaps`, or `all`) | `all` |
| `--min-position` | Minimum display position on Trang Vàng | `20` |
| `-f`, `--file` | File containing list of keywords | `config/keywords.txt` |
| `-l`, `--limit` | Maximum results per keyword | `50` |
| `--headful` | Run browser in headful mode (visible UI) | `False` (Headless) |
| `--all-status` | Include closed businesses | `False` (Only active) |
| `--stats` | Display database summary statistics | - |
| `--list` | Display a table of recent businesses | - |
| `--clean-phones` | Normalize existing phone numbers (+84 -> 0, remove 1900/1800) | - |
| `--mark-checked ID` | Mark business as checked by ID | - |
| `--unmark-checked ID` | Unmark business check status by ID | - |
| `--export-csv` | Export data to CSV file | - |
| `--export-json` | Export data to JSON file | - |
| `--db` | SQLite database file path | `data/businesses.db` |

---

## 🗄️ SQLite Database Sample Queries

SQLite file location: `data/businesses.db`

### Query businesses with phone & email from Trang Vàng:

```sql
SELECT name, phone, email, category, address
FROM businesses
WHERE search_query LIKE 'trangvang%' AND phone IS NOT NULL AND phone != ''
ORDER BY id DESC;
```

### Query all unchecked businesses with phone numbers:

```sql
SELECT name, phone, email, category, status, is_checked, address
FROM businesses
WHERE is_active = 1 AND phone IS NOT NULL AND phone != '' AND is_checked = 0
ORDER BY id DESC;
```
