# Lược đồ cơ sở dữ liệu (Supabase Postgres)

Project ref: `edfmsjiptksqhqfqptcc`. Soi trực tiếp ngày 2026-08-03.
Schema: `public`. **RLS bật trên mọi bảng** → MCP server dùng service-role key.
Anon key sẽ trả về 0 dòng cho mọi truy vấn **mà không báo lỗi** — xem docs/TESTING.md.

Chỉ có **hai** bảng và cả hai đều đang dùng: `locations` và `listings`.
**Không có bảng `projects`** — project nằm trong `locations` dưới dạng các dòng có `level='project'`.
**Không có bảng documents/embeddings** và `pgvector` chưa cài → RAG (US3) phải xây từ đầu.

> ⚠️ Tên bảng là **`listings`** (số nhiều). Một bản chụp cũ của bộ dữ liệu này dùng `listing`
> (số ít) với 1748 dòng và các cột số kiểu text; **giờ không còn như vậy**. Hãy soi lại lược đồ
> thay vì tin vào bất kỳ hình dạng nào trong hai cái đó.

---

## `locations` — cây địa điểm/dự án (352 dòng)

Cây tự tham chiếu. `id` là slug dạng text, ví dụ `oh:amber-riverside`.

| cột | kiểu | ghi chú |
|---|---|---|
| id | text | slug đóng vai khoá chính (**không khai báo ràng buộc PK trong DB**) |
| level | text | `project` (57), `cluster` (87), `building` (208) |
| name | text | tên hiển thị, ví dụ "Amber Riverside" |
| name_norm | text | tên đã chuẩn hoá — **đã bỏ dấu sẵn**, đây là cột giúp tìm kiếm không dấu chạy được mà không cần `unaccent` |
| parent_id | text | → `locations.id` của node cha (NULL với project) |
| project_id | text | → id của project sở hữu (NULL trên chính các dòng project) |
| province | text | ví dụ "Hà Nội". NULL trên ~9 dòng project và ~11 cluster |
| district | text | ví dụ "Hai Bà Trưng" |
| lat, lng | float8 | ⚠️ **chỉ project mới có** (47/57). Luôn NULL trên dòng cluster và building |
| sources | jsonb | mảng nhãn nguồn gốc |
| source_refs, attrs | jsonb | nguồn gốc / thuộc tính phụ |
| updated_at | timestamptz | lần ghi cuối |

**Phân cấp:** `project` (gốc, `parent_id` NULL) → `cluster` (phân khu, có thể không có) →
`building` (lá). Dòng building mang `project_id` = id của project chứa nó.

**Phân bố tỉnh:** đếm trên **tất cả các cấp** — Hà Nội 213, Hồ Chí Minh 63, Hưng Yên 35,
Hải Phòng 17, Long An 4. Riêng **dòng cấp project**: Hà Nội 37, Hưng Yên 6, Hải Phòng 2,
Hồ Chí Minh 2, Long An 1, **không có tỉnh 9**. `list_provinces()` trả về 5 giá trị khác NULL đó.

---

## `listings` — tin đăng bất động sản (2355 dòng)

Bảng lõi chứa đơn vị bán được. `id` kiểu text. **Không khai báo ràng buộc PK.**

> 🔴 **Đọc mục "Hai nguồn xếp chồng" ngay bên dưới trước khi diễn giải bất kỳ tỷ lệ NULL nào
> trong bảng cột.** Bảng này là hai catalogue gộp lại, và gần như mọi cột "thưa" thực ra đầy
> 100% ở một nguồn, rỗng 0% ở nguồn kia.

### Hai nguồn xếp chồng — trục quan trọng nhất của bảng

```
source = 'onehousing'       1264 dòng (54%)
source = 'vinhomes-market'  1091 dòng (46%)
```

Đo trên toàn bảng ngày 2026-08-05:

| Cột | onehousing | vinhomes-market | Ý nghĩa |
|---|---|---|---|
| **`price_type`** | **`estimate` 100%** | **`asking` 100%** | 🔴 Xem cảnh báo bên dưới |
| `status` | 0% | `ĐANG BÁN` 100% | Cột này chỉ đang nói "dòng đến từ Vinhomes" |
| `geo_precision` | `project` 100% | `listing` 99% | Toạ độ OneHousing là tâm dự án |
| `area_type` | `unknown` 100% | `thong_thuy` 86% | Nửa dữ liệu không rõ chuẩn đo |
| `floor_band` | 100% | 0% | Cùng thông tin tầng, |
| `floor_num` | 0% | 84% | hai cách mã hoá khác nhau |
| `bathrooms` | 100% | 49% | |
| `view` | 100% | 50% | |
| `legal_status` | 100% | 72% | |
| `building_id` | 100% | 78% | |

**Hệ quả:** "`floor_num` NULL 60%" **không phải** dữ liệu thiếu — mà là "OneHousing dùng
`floor_band` thay vì `floor_num`". Chưa có tool nào hợp nhất hai cách mã hoá này.

> 🔴 **`price_type` — 1264 dòng là GIÁ ƯỚC TÍNH, không phải giá chào bán.**
> Toàn bộ dòng `onehousing` có `price_type='estimate'`: con số do nguồn tự tính, **không ai
> đang rao ở mức đó**. Chỉ 1091 dòng `vinhomes-market` mới là `asking` — giá người bán đưa ra.
> Nhầm hai loại này là nói sai giá trị thật của căn nhà, và PRD **cấm định giá** trong khi 54%
> dữ liệu chính là định giá. Docstring `get_listing` đã dặn agent luôn nói rõ đang trích loại
> nào ("giá chào bán" hay "giá tham khảo do nguồn ước tính").
>
> ✅ **`price_type` đã được đưa vào `LISTING_CARD_COLUMNS`** (2026-08-05), nên mọi thẻ của
> `search_listings` / `list_project_listings` đều mang theo loại giá bên cạnh con số. Trước đó
> thẻ chỉ có `price_vnd` trần, và agent phải gọi thêm `get_listing` mới biết đó là giá gì.
> Có test khoá chặt việc này — đừng bỏ cột ra khỏi thẻ.
>
> Vì sao quan trọng: 5 căn rẻ nhất của Vinhomes Ocean Park **đều là `estimate`**. Câu
> "căn rẻ nhất ở đây 1,75 tỷ" nghe như một lời chào bán, thực chất là con số máy ước lượng.

| cột | kiểu | ghi chú |
|---|---|---|
| id | text | id tin đăng, ví dụ `oh:TOFMRB` |
| source | text | 🔴 **hai giá trị**: `onehousing` 1264 · `vinhomes-market` 1091. Xem mục bên trên |
| source_listing_id, listing_code, url | text | nguồn gốc / liên kết. `listing_code` điền 99% |
| title | text | tiêu đề tin |
| location_id, project_id, cluster_id, building_id | text | → `locations.id` ở từng cấp. `location_id`/`project_id` điền 100%, `building_id` 89%, `cluster_id` 83% |
| property_type | text | xem bảng bên dưới |
| **area_m2** | **float8** | ✅ số thật. Điền 2207/2355 (93%) |
| area_type | text | `unknown` 1264 (toàn bộ OneHousing) · `thong_thuy` 944. Nửa dữ liệu không rõ chuẩn đo → giá/m² giữa hai nguồn **không so trực tiếp được** |
| **bedrooms**, **bathrooms**, **floor_num** | **int** | ✅ số thật. `bedrooms` 93%, `bathrooms` 76%, `floor_num` 40% |
| bedrooms_plus | bool | cờ "N+" |
| floor_band | text | điền 1264/2355 (53%) |
| direction_balcony, view | text | `direction_balcony` 93%, `view` 77% |
| legal_status, furnishing, usage_status | text | |
| **price_vnd** | **bigint** | ✅ lọc/sắp xếp trong SQL an toàn. Điền 2331/2355 (98%) |
| **price_per_m2_vnd** | **bigint** | ✅ an toàn. Điền 2328/2355 (98%) |
| price_type | text | 🔴 **`estimate` 1264 · `asking` 1091**. `estimate` = giá nguồn tự ước tính, **không ai rao ở mức đó**; `asking` = giá người bán đưa ra. Phải phân biệt trước khi trích `price_vnd` |
| status | text | chỉ có `ĐANG BÁN` (1091 dòng) hoặc NULL (1264 dòng). **Không tồn tại giá trị `active`** |
| comp_group | text | rất thưa — chỉ điền 140/2355 (5%). Nhóm để so sánh |
| comp_one_to_one | bool | |
| lat, lng | float8 | có mặt trên **cả 2355 dòng** — nhưng đọc kỹ `geo_precision` bên dưới |
| geo_precision | text | `project` 1264 · `listing` 1080 · NULL 11. ⚠️ **54% toạ độ chỉ là toạ độ dự án chép xuống** |
| thumbnail | text | url ảnh đại diện |
| images | jsonb | mảng url ảnh — **bị cắt ở tối đa 40 URL** |
| image_count | bigint | số ảnh **ở nguồn**, nên thường lớn hơn `len(images)` (840/2355 dòng > 40) |
| raw | jsonb | payload gốc đầy đủ — không bao giờ trả cho agent |
| crawled_at, first_seen, last_seen | timestamptz | |

### Các giá trị `property_type`

| giá trị | số dòng | nghĩa |
|---|---:|---|
| `can_ho` | 2199 | căn hộ (áp đảo) |
| `lien_ke` | 83 | liền kề |
| `shophouse` | 48 | shophouse |
| `thuong_mai_dich_vu` | 11 | thương mại / dịch vụ |
| `biet_thu_song_lap` | 7 | biệt thự song lập |
| `biet_thu_tu_lap` | 3 | biệt thự tứ lập |
| `biet_thu_don_lap` | 2 | biệt thự đơn lập |
| `nha_pho` | 1 | nhà phố |
| *(NULL)* | 1 | |

Phải giữ `tools/listings.py > PROPERTY_TYPES` khớp với danh sách này — một giá trị có trong dữ
liệu mà thiếu trong tuple đó sẽ khiến `search_listings` **từ chối một bộ lọc hợp lệ**.
(`nha_pho` đã từng bị thiếu đúng theo cách này.)

---

## Những cái bẫy mà tool BẮT BUỘC phải xử lý

0. 🔴 **Phân biệt `price_type` trước khi nói bất kỳ con số giá nào.** 1264/2355 dòng là
   `estimate` — giá do nguồn ước tính, không phải giá đang rao. Xem mục "Hai nguồn xếp chồng".
1. **Không có trạng thái `active`** — đừng lọc `status='active'` (trả về rỗng). Chỉ có `ĐANG BÁN`
   hoặc NULL, và **NULL nghĩa là *không rõ*, không phải *đã bán***. Toàn bộ 1264 dòng OneHousing
   đều NULL ở cột này, nên NULL chỉ nói lên "nguồn không công bố", không nói gì về việc còn bán.
2. **`listings` không có cột `province`** — muốn lọc tin theo tỉnh thì phải đổi tỉnh → danh sách
   project id qua `locations` trước, rồi mới lọc `listings.project_id`.
3. **Không có ràng buộc FK, không khai báo PK** — mọi phép nối đều dựa trên quy ước giữa các id
   text ở trên. Xem phần "Toàn vẹn dữ liệu" bên dưới để biết điều đó đã gây ra gì.
4. **`locations.lat`/`lng` chỉ tồn tại trên dòng project.** Tool trả về node cluster hoặc building
   (`list_project_buildings`) luôn báo `lat: null` / `lng: null`.
5. **Toạ độ tin đăng đủ về số lượng nhưng không đồng đều về chất lượng.** Cả 2355 dòng đều có
   `lat`/`lng`, nhưng `geo_precision='project'` trên 1264 dòng nghĩa là toạ độ đó **thực ra là tâm
   dự án chép xuống**. Trên bản đồ, những căn này sẽ chồng lên nhau tại một điểm. `map_listings`
   hiện **chưa** trả `geo_precision` ra ngoài, nên agent không có cách nào biết để nói rõ.
6. **Cột số có thể NULL.** `price_vnd` NULL 24 dòng, `area_m2` 148, `bedrooms` 155, `floor_num` 1436.
   Lọc theo một cột sẽ **âm thầm loại bỏ** các dòng NULL của cột đó — chúng bị loại vì thiếu dữ
   liệu chứ không phải vì không thoả điều kiện. `project_price_stats` đã bỏ qua NULL; code mới
   cũng phải làm vậy.

### Toàn vẹn dữ liệu — kết quả kiểm tra thực tế

Kiểm trên toàn bộ 2355 dòng (2026-08-05):

- **Khoá ngoại mồ côi: 0.** Cả `location_id`, `project_id`, `cluster_id`, `building_id` đều trỏ
  tới `locations.id` có thật. Sạch — nhưng sạch nhờ kỷ luật của bên nạp dữ liệu, **không có ràng
  buộc nào bảo vệ**.
- **`project_id` và `building_id` suy được 100% từ `location_id`** bằng cách leo cây `parent_id`.
  Chúng là bản sao tiện dụng, không phải thông tin mới.
- ⚠️ **`cluster_id` đã sai lệch trên 60 dòng**: 38 dòng chỉ vào cluster khác với cây, 22 dòng để
  NULL trong khi cây có cluster. Nguyên nhân gốc: **cùng một phân khu ngoài đời tồn tại hai node**
  do hai nguồn khác nhau tạo ra (`oh:vinhomes-ocean-park-the-sapphire` và
  `vhm:the-sapphire-2-vinhomes-ocean-park`). Id nhúng tên nguồn vào nên không có gì ngăn trùng lặp.
- **118/352 địa điểm không được tin đăng nào trỏ tới** (33%) — `list_project_buildings` sẽ mời
  người dùng chọn cả những toà không có căn nào rao bán.

### Ghi chú về `shaping.py`

`to_float` / `to_int` / `normalize_status` được viết cho bản chụp cũ, khi các cột số còn là text
và `status` bị lỗi mã hoá. Với DB hiện tại chúng chỉ là hàm truyền thẳng. Vẫn giữ lại làm lớp
phòng vệ (chạy trên dữ liệu sạch thì không tốn gì).

Các cách lách dựng trên chúng thì **đã được gỡ bỏ**: `search_listings` từng lọc `bedrooms` bằng
Python sau khi fetch dư `limit * 3` dòng, khiến `bedrooms=2` ở Vinhomes Grand Park trả về 0 kết
quả trong khi có 251 căn. Nay `bedrooms` lọc thẳng trong SQL.

---

## Các extension Postgres (phục vụ giai đoạn 2)

> ⚠️ **Chưa xác minh trên project `edfmsjiptksqhqfqptcc`** — danh sách này mang sang từ lần soi
> project cũ. Hãy chạy `SELECT * FROM pg_extension;` (SQL Editor của Supabase hoặc Supabase MCP)
> để xác nhận trước khi lên kế hoạch giai đoạn 2 dựa vào nó.

Đã thấy cài trước đây: `pgcrypto`, `pg_stat_statements`, `supabase_vault`, `uuid-ossp`.

Đã cài trong quá trình làm US1: **`pg_trgm`** (xem `migrations/001_search_projects_fuzzy.sql`) —
dùng cho `word_similarity` chịu lỗi gõ. **Không cần `unaccent`** vì `locations.name_norm` đã lưu
sẵn dạng bỏ dấu.

Có sẵn (chưa cài) và đáng quan tâm: `vector` (pgvector — cho RAG), `pgroonga`/`rum`
(full-text/BM25), `postgis`/`earthdistance` (địa lý/bán kính), `pg_cron` (đánh lại index định kỳ).

## Cách soi lại lược đồ

Dùng Supabase MCP: `list_tables(project_id, verbose=true)` và `execute_sql(...)`, hoặc truy vấn
qua chính client của app:

```bash
set -a && . ./.env && set +a
./venv/bin/python -c "
from app.db import get_client
r = get_client().table('listings').select('*').limit(1).execute().data[0]
print(sorted(r))
"
```

⚠️ Đừng đọc tỷ lệ NULL từ một mẫu `.limit(1000)`: PostgREST trả về 1000 dòng đầu **theo thứ tự
vật lý**, tức một khối crawl, và lệch rất nặng. `floor_band` nhìn qua mẫu đó tưởng NULL 100%,
thực tế chỉ 46%. Hãy đếm bằng `count="exact"` trên toàn bảng.

**Không** hardcode giả định — kiểm chứng lại sau mỗi migration, và cập nhật file này cùng
`tests/conftest.py` (các id mẫu) khi dữ liệu thay đổi.
