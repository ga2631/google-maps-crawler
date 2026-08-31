# 🗺️ Google Maps Business Scraper

A lightweight, robust tool to scrape business data from **Google Maps** based on custom search keywords, automatically filter for **active businesses**, securely store data in **SQLite**, and run anywhere using **Docker**.

> 💡 **Highlights**:
>
> - **No Google Maps API Required**: Save costs with no quota restrictions.
> - **Playwright (Chromium) Powered**: Renders and extracts real dynamic web content.
> - **Flexible Keyword-Based Search**: No hardcoded locations; search results adapt completely to your keywords (cities, districts, categories, etc.).
> - **Phone Number Normalization**: Automatically standardizes country code `+84` to `0...` (e.g. `+84901234567` -> `0901234567`), while filtering out toll-free hotline numbers (`1900`, `1800`,...) and unwanted landline prefixes.
> - **Business Status Filtering**: Automatically detects and retains operating businesses ("Open 24 hours", "Open", etc.), filtering out "Permanently closed" and "Temporarily closed" listings.
> - **Smart Deduplication**: Uses intelligent UPSERT in SQLite based on Google Maps URL or (Name + Phone).
> - **Docker Ready**: Run out-of-the-box in any environment with persistent SQLite database volume mounting.

---

## 📋 Extracted Fields

| Field | Database Column | Example |
| :--- | :--- | :--- |
| **Business Name** | `name` | ABC Tech Solutions Co., Ltd |
| **Phone Number** | `phone` | `0909123456` / `0389123456` (Normalized +84 -> 0, filtered 1900/1800) |
| **Category / Industry** | `category` | Software company, Restaurant, Cafe,... |
| **Operational Status** | `status` | Open, Open 24 hours, Active |
| **Is Active?** | `is_active` | `1` (Active) / `0` (Closed) |
| **Is Checked?** | `is_checked` | `0` (Unchecked) / `1` (Checked) |
| **Address** | `address` | 123 Nguyen Hue Street, District 1, Ho Chi Minh City |
| **Website** | `website` | `https://example.com` |
| **Rating** | `rating` | `4.8` |
| **Reviews Count** | `reviews_count` | `150` |
| **Google Maps URL** | `google_maps_url` | `https://www.google.com/maps/place/...` |
| **Search Query** | `search_query` | `software company District 1` |

---

## 🚀 Docker Quickstart (Recommended)

No need to install Python or Chromium on your machine; only Docker Desktop is required.

### 1. Build the image

```bash
docker compose build
```

### 2. Crawl using keyword list in `config/keywords.txt`

```bash
docker compose up
```

_The database file `businesses.db` will automatically be created and updated in the `./data/` folder on your host machine._

### 3. Crawl a specific keyword

```bash
docker compose run --rm crawler -q "logistics companies in Da Nang" -l 30
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

_(The exported CSV/JSON files will appear in your `./data/` directory on the host machine)_

---

## 💻 Local Setup with Python (Without Docker)

To run directly on your machine or see the browser UI in real time (headful mode):

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
# Crawl a specific keyword directly
python main.py -q "software company Da Nang" -l 20

# Run with visual browser UI (headful mode)
python main.py -q "coffee shop Hanoi" --headful

# Crawl keywords listed in config/keywords.txt
python main.py -f config/keywords.txt -l 50

# View recently scraped businesses
python main.py --list

# View database overview statistics
python main.py --stats

# Mark a business as checked
python main.py --mark-checked 10

# Clean / normalize phone numbers in DB
python main.py --clean-phones

# Export data to CSV
python main.py --export-csv data/businesses.csv
```

---

## ⚙️ Command Line Options (CLI Arguments)

| Argument | Description | Default |
| :--- | :--- | :--- |
| `-q`, `--query` | Specific search keyword | `None` |
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

## 🗄️ SQLite Database Schema & Sample Queries

SQLite file location: `data/businesses.db`

### Query all unchecked businesses with phone numbers:

```sql
SELECT name, phone, category, status, is_checked, address
FROM businesses
WHERE is_active = 1 AND phone IS NOT NULL AND phone != '' AND is_checked = 0
ORDER BY id DESC;
```

### Group businesses by industry/category:

```sql
SELECT category, COUNT(*) as total
FROM businesses
GROUP BY category
ORDER BY total DESC;
```
