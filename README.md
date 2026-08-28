# 🗺️ Google Maps Business Scraper (Khu vực TP. Hồ Chí Minh)

Công cụ cào dữ liệu doanh nghiệp trên **Google Maps** trong khu vực **TP. Hồ Chí Minh**, tự động lọc các doanh nghiệp **đang hoạt động**, lưu trữ an toàn vào **SQLite**, và đóng gói hoàn chỉnh bằng **Docker**.

> 💡 **Điểm nổi bật**:
> - **Không sử dụng Google Maps API** (tiết kiệm chi phí, không giới hạn quota).
> - **Sử dụng Playwright (Chromium)** để render và cào dữ liệu trang động thực tế.
> - **Tự động định vị TP.HCM** (`10.776889,106.700806`) và hỗ trợ giao diện tiếng Việt (`vi`).
> - **Chuẩn hoá số điện thoại**: Tự động xoá đầu số quốc gia `+84` (chuyển về đầu `0...` hoặc giữ đầu tổng đài `1800`/`1900`), và **loại bỏ không lưu các số điện thoại bàn `028`, `+8428`** vào database.
> - **Lọc trạng thái hoạt động**: Tự động nhận diện và chỉ lưu các doanh nghiệp đang hoạt động ("Đang mở cửa", "Mở cả ngày", v.v.), loại bỏ các điểm "Đã đóng cửa vĩnh viễn" / "Tạm thời đóng cửa".
> - **Chống trùng lặp**: Cơ chế UPSERT thông minh trong SQLite dựa trên URL Google Maps hoặc cặp (Tên + SĐT).
> - **Đóng gói Docker**: Chạy độc lập mọi môi trường, tự động mount volume lưu file SQLite ra máy host.

---

## 📋 Các trường thông tin thu thập

| Trường dữ liệu | Tên cột trong DB | Ví dụ |
| :--- | :--- | :--- |
| **Tên doanh nghiệp** | `name` | Công Ty TNHH Giải Pháp Công Nghệ ABC |
| **Số điện thoại** | `phone` | `0909123456` / `0389123456` / `1900636688` (Đã lọc bỏ số 028/+8428) |
| **Ngành nghề kinh doanh** | `category` | Công ty phần mềm, Nhà hàng, Quán cafe,... |
| **Tình trạng hoạt động** | `status` | Đang mở cửa, Mở cả ngày, Đang hoạt động |
| **Đang hoạt động?** | `is_active` | `1` (Đang hoạt động) / `0` (Đóng cửa) |
| **Đã check thông tin?** | `is_checked` | `0` (Chưa check) / `1` (Đã check) |
| **Địa chỉ** | `address` | 123 Đường Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP.HCM |
| **Website** | `website` | `https://example.com` |
| **Đánh giá** | `rating` | `4.8` |
| **Số lượt đánh giá** | `reviews_count` | `150` |
| **Link Google Maps** | `google_maps_url` | `https://www.google.com/maps/place/...` |
| **Từ khóa tìm kiếm** | `search_query` | `công ty phần mềm Quận 1 Hồ Chí Minh` |

---

## 🚀 Hướng dẫn sử dụng với Docker (Khuyên Dùng)

Bạn không cần cài đặt Python hay Chromium trên máy, chỉ cần có Docker Desktop.

### 1. Build image
```bash
docker compose build
```

### 2. Chạy cào theo danh sách từ khóa trong `config/keywords.txt`
```bash
docker compose up
```
*File cơ sở dữ liệu `businesses.db` sẽ tự động được lưu và cập nhật trong thư mục `./data/` trên máy tính của bạn.*

### 3. Chạy cào 1 từ khóa cụ thể
```bash
docker compose run --rm crawler -q "công ty logistics TP Thủ Đức Hồ Chí Minh" -l 30
```

### 4. Xem thống kê dữ liệu trong SQLite
```bash
docker compose run --rm crawler --stats
```

### 5. Đánh dấu đã kiểm tra thông tin
```bash
# Đánh dấu đã check cho doanh nghiệp ID 10
docker compose run --rm crawler --mark-checked 10

# Bỏ đánh dấu check cho doanh nghiệp ID 10
docker compose run --rm crawler --unmark-checked 10
```

### 6. Xuất dữ liệu ra file CSV hoặc JSON
```bash
# Xuất ra CSV
docker compose run --rm crawler --export-csv /app/data/doanh_nghiep_hcm.csv

# Xuất ra JSON
docker compose run --rm crawler --export-json /app/data/doanh_nghiep_hcm.json
```
*(File CSV/JSON sẽ xuất hiện ngay trong thư mục `./data/` trên máy host)*

---

## 💻 Hướng dẫn chạy trực tiếp bằng Python (Không dùng Docker)

Nếu bạn muốn chạy trực tiếp trên máy và xem trình duyệt mở lên (headful mode):

### 1. Cài đặt môi trường
```bash
# Tạo môi trường ảo (khuyên dùng)
python3 -m venv .venv
source .venv/bin/activate  # Trên Linux/macOS
# .venv\Scripts\activate   # Trên Windows

# Cài đặt thư viện
pip install -r requirements.txt

# Cài đặt browser Chromium cho Playwright
playwright install chromium
```

### 2. Chạy cào dữ liệu
```bash
# Cào theo từ khóa nhập trực tiếp
python main.py -q "công ty phần mềm Quận Tân Bình Hồ Chí Minh" -l 20

# Cào và mở cửa sổ trình duyệt trực quan (để xem thao tác cào)
python main.py -q "quán cafe Quận 1 Hồ Chí Minh" --headful

# Cào danh sách từ khóa trong file config/keywords.txt
python main.py -f config/keywords.txt -l 50

# Xem danh sách doanh nghiệp vừa cào
python main.py --list

# Xem bảng thống kê tổng quan
python main.py --stats

# Đánh dấu đã kiểm tra thông tin
python main.py --mark-checked 10

# Xuất dữ liệu ra CSV
python main.py --export-csv data/doanh_nghiep_hcm.csv
```

---

## ⚙️ Các tùy chọn dòng lệnh (CLI Arguments)

| Tham số | Ý nghĩa | Mặc định |
| :--- | :--- | :--- |
| `-q`, `--query` | Từ khóa tìm kiếm cụ thể | `None` |
| `-f`, `--file` | File chứa danh sách từ khóa | `config/keywords.txt` |
| `-l`, `--limit` | Số lượng kết quả tối đa mỗi từ khóa | `50` |
| `--headful` | Mở trình duyệt có giao diện | `False` (Headless) |
| `--all-status` | Lưu cả doanh nghiệp đã đóng cửa | `False` (Chỉ lưu đang hoạt động) |
| `--stats` | Xem thống kê số lượng & ngành nghề | - |
| `--list` | Hiển thị bảng danh sách các doanh nghiệp gần nhất | - |
| `--clean-phones` | Chuẩn hoá SĐT cũ trong DB (xoá +84, bỏ số 028/+8428) | - |
| `--mark-checked ID` | Đánh dấu doanh nghiệp đã kiểm tra thông tin theo ID | - |
| `--unmark-checked ID` | Bỏ đánh dấu kiểm tra thông tin theo ID | - |
| `--export-csv` | Xuất dữ liệu ra file CSV | - |
| `--export-json` | Xuất dữ liệu ra file JSON | - |
| `--db` | Đường dẫn file SQLite | `data/businesses.db` |

---

## 🗄️ Cấu trúc bảng SQLite & Truy vấn mẫu

File SQLite lưu tại: `data/businesses.db`

### Truy vấn tất cả doanh nghiệp có số điện thoại và chưa kiểm tra:
```sql
SELECT name, phone, category, status, is_checked, address 
FROM businesses 
WHERE is_active = 1 AND phone IS NOT NULL AND phone != '' AND is_checked = 0
ORDER BY id DESC;
```

### Thống kê số lượng theo ngành nghề:
```sql
SELECT category, COUNT(*) as total 
FROM businesses 
GROUP BY category 
ORDER BY total DESC;
```
