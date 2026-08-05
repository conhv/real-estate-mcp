# Tools — Checklist triển khai cho học viên

Đây là danh sách công việc cần xây. Mỗi tool gồm: User Story mà nó phục vụ, chữ ký hàm, thứ nó phải
trả về, và các tiêu chí nghiệm thu. **Bộ khung đã có sẵn** — với các tool giai đoạn 1, việc của bạn
là đọc phần code đã cung cấp, đối chiếu với DB thật, rồi tích vào ô (hoặc cải tiến). Các tool giai
đoạn 2 là phần bạn tự xây từ đặc tả.

**Quy tắc chung (áp dụng cho mọi tool):**
- Tool = lớp bọc mỏng trong `src/app/tools/`; logic DB nằm ở `src/app/services/`.
- Khai báo kiểu cho mọi tham số; tham số tùy chọn viết dạng `X | None = None`; `limit` phải có giá
  trị mặc định hợp lý.
- Docstring bắt buộc nói rõ *nó làm gì / khi nào dùng / trả về cái gì* — agent chỉ đọc đúng phần đó.
- Trả về dữ liệu JSON-serializable đã được định dạng trong `shaping.py`. Không bao giờ trả về row thô.
- Không tìm thấy / input sai → raise `fastmcp.exceptions.ToolError`. Không bao giờ để lộ key hay
  stack trace.
- Đối chiếu với schema thật trong `docs/SCHEMA.md`. Nếu không chắc, introspect lại bằng Supabase MCP.

**Cách kiểm thử:** hướng dẫn đầy đủ ở [TESTING.md](TESTING.md). Bản rút gọn — test cấp 1 không cần DB:
```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests/test_shaping.py tests/test_server_tools.py -v   # không cần DB
.\.venv\Scripts\python.exe -m pytest tests/test_live_db.py -v                              # cần .env
```
Hoặc test một tool theo kiểu tương tác:
```python
import asyncio
from app.server import mcp
print(asyncio.run(mcp.call_tool("search_projects", {"query": "Vinhomes"})).structured_content)
```
Các id mẫu hợp lệ để test nằm trong `tests/conftest.py`.

---

## Giai đoạn 1 — đã triển khai; hãy kiểm chứng & làm chắc thêm

### US1 — Tìm kiếm theo project / tỉnh thành
- [x] **`search_projects(query, province, limit)`** → danh sách node project.
  - ✅ Kiểm chứng: "Amber Riverside" → 1 kết quả; "Vinhomes" → 22; "chung cu" → 2 (trước đây là 0).
  - ✅ Làm chắc thêm: khớp 3 tầng qua RPC `search_projects_fuzzy` — `ILIKE name` (có dấu) →
    `ILIKE name_norm` (không dấu, cột DB đã lưu sẵn dạng bỏ dấu nên **không cần** `unaccent`) →
    `word_similarity >= 0.55` (chịu lỗi gõ: "vinhoms" → Vinhomes). Kết quả xếp theo điểm trigram.
    Migration: `migrations/001_search_projects_fuzzy.sql` — **phải chạy trước khi deploy**, nếu
    không sẽ lỗi `Could not find the function public.search_projects_fuzzy`.
  - Test: 7 test trong `tests/test_live_db.py` (không dấu, lỗi gõ, chặn truy vấn rác, xếp hạng,
    lọc tỉnh trong SQL, thứ tự xác định, ký tự đặc biệt).
- [x] **`resolve_project(text)`** → `{matched, project, candidates}`.
  - ✅ Khớp đúng một → `matched=true`; khớp nhiều → `matched=false` + candidates; không khớp → rỗng.
  - ✅ Sửa thêm: ưu tiên **khớp tên chính xác** (bỏ qua hoa/thường, dấu, khoảng trắng thừa).
    Trước đây gõ đủ "Vinhomes Ocean Park" vẫn trả `matched=false` vì còn "... 2" và "... 3" cùng
    khớp — agent bắt người dùng chọn lại cái tên họ vừa gõ đủ. Nay resolve thẳng.
  - Test: 3 test trong `tests/test_live_db.py` (3 nhánh hợp đồng, ưu tiên khớp chính xác).
- [x] **`list_project_buildings(project_id, level, limit)`** → các node location con.
  - ⚠️ Đã sửa lỗi: tool tra theo `parent_id` nên chỉ lấy **một tầng**. 23/57 project có tầng
    phân khu (cluster) ở giữa, nên với những project đó tool trả về cluster và **không bao giờ**
    trả về building. Vinhomes Ocean Park: 13 con trực tiếp (toàn cluster) trong khi có 53 building.
  - ✅ Nay tra theo `project_id` (cột này điền đủ 87/87 cluster + 208/208 building, và luôn khớp
    gốc của chuỗi cha) nên lấy trọn cây con: Ocean Park → 66 node (13 cluster + 53 building).
  - ✅ Thêm tham số `level` để lọc `"cluster"`/`"building"`; xếp cluster trước building rồi theo
    tên, để `limit` cắt được phần đầu có nghĩa. Lưu ý: có project chỉ có cluster mà **không có**
    building nào, nên `level="building"` trả rỗng là hợp lệ.
  - ✅ Raise `ToolError` khi `project_id` không phải project thật (trước đây trả rỗng lặng lẽ).
  - Test: 4 test trong `tests/test_live_db.py` (xuyên qua cluster, thứ tự, lọc `level`, id sai).
  - Còn thiếu: chưa lọc listing theo building được — xem mục `search_listings` bên dưới.
- [x] **`list_provinces()`** → danh sách tỉnh thành (không trùng, đã sắp xếp) có ít nhất một project.
  - ⚠️ Đã sửa lỗi thứ tự: `sorted()` của Python so theo mã Unicode, mà `ư`(U+01B0) < `ả`(U+1EA3)
    < `ồ`(U+1ED3), nên trả về *Hà Nội, Hưng Yên, Hải Phòng, Hồ Chí Minh, Long An* — sai bảng chữ
    cái tiếng Việt ngay trước mắt người dùng. Nay sắp theo tên đã bỏ dấu (tên gốc làm khoá phụ
    cho ổn định) → *Hà Nội, Hải Phòng, Hồ Chí Minh, Hưng Yên, Long An*.
    Hạn chế: bỏ dấu gộp `ă`/`â` vào `a`, `đ` vào `d`, nên chưa phải collation tiếng Việt đầy đủ.
  - ✅ Lọc `province IS NOT NULL` ở SQL thay vì lọc sau khi fetch; `.limit(1000)` khai báo tường
    minh (PostgREST vốn tự cắt ở 1000 dòng mà không báo).
  - ⚠️ **9/57 project không có `province`** (Vinhomes Pearl Bay, Happy Home Tràng Cát, ...) nên
    danh sách này *không* phủ hết kho. Docstring đã dặn agent không được nói "chỉ có bấy nhiêu
    tỉnh"; muốn tìm toàn bộ thì gọi `search_projects` không kèm `province`.
  - ✅ Docstring viết lại: phần hợp đồng trả về đặt dạng văn xuôi (FastMCP cắt bỏ khối `Returns:`),
    kèm hướng dẫn truyền ngược giá trị sang `search_projects`.
  - Test: 3 test trong `tests/test_live_db.py` (sạch/không trùng, thứ tự tiếng Việt, mỗi tỉnh
    trả về đều thật sự có project).
- [x] **`search_listings(project_id, building_id, property_type, min_price_vnd, max_price_vnd,
      bedrooms, limit)`**
  - ✅ Khoảng giá đã lọc ở SQL (`gte`/`lte` trên `price_vnd`), sắp xếp giá tăng dần.
  - 🐞 **Lỗi nặng nhất tìm được từ trước tới giờ**: `bedrooms` lọc bằng Python sau khi fetch
    `limit * 3` dòng. Vinhomes Grand Park có 587 listing; xếp theo giá thì căn 2PN đầu tiên nằm ở
    vị trí 144, nên `bedrooms=2, limit=10` chỉ nhìn 30 dòng rẻ nhất, không khớp dòng nào và trả
    về **0 kết quả trong khi có 251 căn**. `bedrooms=3` cũng trả về 0 (có 38 căn). Mọi cách lọc
    sau khi fetch đều dính lỗi này — nhân hệ số chỉ đẩy vách đá đi xa hơn chứ không xoá nó.
    Nay `q.eq("bedrooms", n)` chạy trong SQL, bỏ hẳn `limit * 3` → cả 1/2/3 PN đều trả đủ 10.
  - ✅ `property_type` sai → raise kèm đủ 8 giá trị hợp lệ. Test đối chiếu ngược: mọi giá trị
    trong `PROPERTY_TYPES` đều phải thật sự được chấp nhận, để thông báo lỗi không nói dối.
  - ✅ Thêm `building_id` → khép vòng với `list_project_buildings` (chọn project → chọn toà →
    xem căn). Chỉ khớp id cấp `building`; id cấp cluster trả rỗng.
  - ✅ Bỏ tham số `province` ở service: `listings` **không có** cột province nên tham số này
    trước đây không làm gì cả. Muốn lọc theo tỉnh thì đổi tỉnh → project id qua `locations`
    (mục `search_listings_by_province` giai đoạn 2).
  - ✅ Docstring: chuyển hợp đồng trả về + quy tắc UI (1–3 hiện card, >3 hiện "xem tất cả") sang
    văn xuôi. Trước đây nằm trong khối `Returns:` nên **FastMCP cắt bỏ, agent chưa từng đọc được**.
    Bổ sung `nha_pho` còn thiếu trong danh sách và cảnh báo `bedrooms`/`building_id` bị NULL
    trên một phần dữ liệu.
  - Test: 4 test trong `tests/test_live_db.py` (chặn hồi quy bedrooms, khoảng giá + thứ tự,
    lọc theo toà, property_type sai).
- [x] **`get_listing(listing_id)`** → chi tiết đầy đủ; raise nếu không tìm thấy.
  - ✅ Logic vốn đã đúng: trả 30 trường (16 trường card + 14 trường chi tiết), id sai → `ToolError`
    không lộ thông tin nội bộ.
  - ✅ Docstring viết lại — trước đây chỉ có một dòng, **agent không biết tool trả về những gì**.
    Nay liệt kê đủ 30 trường + 4 cảnh báo đọc dữ liệu cho trung thực:
    - Nhiều trường NULL thật (`floor_num` 60%, `bathrooms` 23%, `view` 22%, `legal_status` 12%) —
      NULL nghĩa là *chưa ghi nhận*, không phải *không có*.
    - `status` chỉ có `'ĐANG BÁN'` (1091 dòng) hoặc NULL (1264 dòng). NULL = **không rõ**, tuyệt
      đối không suy ra "đã bán" hay khẳng định căn còn bán.
    - `images` bị cắt ở **40 URL** trong khi `image_count` là số ảnh ở nguồn → 840/2355 dòng có
      `image_count > len(images)`. Nói số ảnh thực sự hiển thị được, muốn xem đủ thì mở `url`.
    - `price_type = 'asking'` — giá chào bán, không phải giá thẩm định.
  - Test: 4 test trong `tests/test_live_db.py` (đủ 30 khoá, id sai raise & không lộ nội bộ,
    chi tiết khớp với card đã sinh ra nó, chặn cảnh báo `image_count` thành lời khuyên lỗi thời).
  - ⚠️ **Đính chính số liệu**: các tỷ lệ NULL tôi ghi ở mục `search_listings` lúc đầu lấy từ
    `.limit(1000)` — PostgREST trả 1000 dòng đầu theo thứ tự vật lý, tức một khối crawl, lệch
    nặng. `floor_band` nhìn qua mẫu đó tưởng NULL 100%, thực tế chỉ 46%. Mọi con số ở trên đã
    đếm lại bằng `count="exact"` trên toàn bộ 2355 dòng.
- [x] **`list_project_listings(project_id, limit, offset)`** → toàn bộ căn trong một project
      ("xem tất cả").
  - 🐞 Tên tool là "xem tất cả" nhưng trả về đúng `limit=50` căn và **không hề nói còn nữa**.
    Vinhomes Ocean Park có 685 căn, Grand Park 623; 9/57 project vượt quá một trang. Agent nhìn
    list 50 phần tử rồi nói "đây là toàn bộ" — sai 93%.
  - ✅ Đổi kiểu trả về từ `list` sang `{total, offset, count, has_more, listings}`. `count="exact"`
    đi kèm ngay trong request nên biết tổng mà không tốn thêm round trip. Docstring dặn agent
    nói *tổng số*, không phải số căn đang hiện.
  - ✅ Thêm `offset` để lật trang; `has_more` cho biết còn hay hết.
  - 🐞 **Phân trang không ổn định** (test bắt được): chỉ `ORDER BY price_vnd` là *không* sắp toàn
    phần — riêng 60 căn rẻ nhất của Ocean Park đã có 10 mức giá bị trùng (3 căn cùng 2,116 tỷ...).
    Postgres được phép xếp nhóm trùng khác nhau ở mỗi truy vấn, nên trang 2 có thể lặp lại hoặc
    bỏ sót căn đã hiện ở trang 1. Nay thêm khoá phụ `ORDER BY id`. Đã thêm cho cả `search_listings`
    để tìm lại lần hai ra đúng kết quả cũ.
  - 🐞 Offset vượt quá cuối → PostgREST trả lỗi `PGRST103` kèm câu *"An offset of 695 was requested,
    but there are only 685 rows"* — vừa là lỗi cho một thao tác hợp lệ, vừa lộ số dòng ra ngoài.
    Nay bắt riêng mã đó và trả về trang rỗng.
  - ✅ Raise `ToolError` khi `project_id` sai, hoặc `limit < 1` / `offset < 0`.
  - Test: 3 test (báo đúng tổng, các trang khớp liền không trùng không sót + quá cuối, input sai).
- [x] **`listing_cta_actions(listing_id)`** → 4 nút CTA + `next_tool` cho từng nút.
  - 🐞 CTA trước đây **không dùng được**: `next_tool` trỏ tới `list_project_listings` /
    `start_visit_booking` / `start_consultation` / `map_listings` — cả 4 đều cần `project_id`,
    mà payload chỉ có `listing_id`. Agent bấm nút xong không biết truyền gì.
  - ✅ Thêm `project_id` và `args` điền sẵn cho từng nút → bấm là gọi được ngay.
  - ✅ Raise `ToolError` khi `listing_id` không tồn tại (trước đây dựng nút cho một căn không có
    thật mà không kiểm tra gì). Dùng `get_listing_ref` chỉ select `id,project_id` thay vì kéo cả
    hàng chi tiết kèm mảng 40 URL ảnh.
  - ✅ Quy tắc UI (1–3 hiện card+CTA; >3 hiện "xem tất cả") viết vào docstring của **cả**
    `search_listings` lẫn tool này — đây là chỗ agent thực sự đọc được.
  - Test: 2 test. Test chính đối chiếu mọi `next_tool` với danh sách tool đã đăng ký **và gọi thật
    từng tool bằng `args` kèm theo** — `next_tool` chỉ là một chuỗi, không có gì khác kiểm tra nó,
    nên đổi tên tool là agent bị đẩy đi gọi thứ không tồn tại.

### US2.1 — Đặt lịch tham quan
- [x] **`start_visit_booking(project_id, is_authenticated)`** → form spec.
  - ✅ Ba yêu cầu của đề đều đã đúng sẵn: form khách hỏi `full_name`/`phone`/`email`/
    `preferred_time`/`note`, form đã đăng nhập chỉ hỏi `preferred_time`/`note`, `project_id`
    sai thì raise `ToolError`. Đã bổ sung test khoá chặt từng điểm.
  - ⚠️ **Rủi ro lớn nhất của hai tool này: chúng không ghi gì cả.** Docstring cũ viết "Build the
    form..." nên agent rất dễ gọi xong rồi báo khách *"đã đặt lịch tham quan lúc 3h chiều thứ 7"* —
    trong khi không có bảng `bookings`, `submit_endpoint` trỏ tới endpoint giai đoạn 2 chưa tồn
    tại, và không dòng nào được lưu. Người dùng tưởng có hẹn, không ai biết để tiếp.
    Nay thêm `"persisted": false` vào payload **và** dặn thẳng trong docstring: tuyệt đối không
    xác nhận đã đặt lịch — lịch chỉ có thật sau khi người dùng submit form.
  - ⚠️ `is_authenticated` là **trạng thái phiên**, agent không có cách nào biết mà sẽ đoán. Đoán
    sai thành `true` cho khách vãng lai → form bỏ luôn tên/SĐT/email → yêu cầu đặt lịch **không có
    chút thông tin liên hệ nào**. Docstring nay ghi rõ: giá trị này do ứng dụng chủ truyền vào,
    không suy từ hội thoại; không chắc thì để `false` (hỏi lại SĐT chỉ hơi phiền, mất SĐT thì hỏng).
  - ✅ `fields` nay được copy từ template thay vì trả thẳng list hằng số ở module — trước đây mọi
    lần gọi dùng chung một object, sửa nhãn tại chỗ một lần là hỏng form của tất cả lần sau.
  - Test: 4 test (khớp đặc tả US2.1 gồm cả cờ `required`, `persisted=false`, id cấp cluster/
    building/rỗng đều raise, template không dùng chung giữa các lần gọi).

### US2.2 — Tư vấn mua nhà
- [x] **`start_consultation(project_id, is_authenticated)`** → form spec (chia theo trạng thái đăng
      nhập tương tự).
  - ✅ Dùng chung `_form_payload` với US2.1 nên mọi sửa ở trên (`persisted`, copy `fields`, dặn
    `is_authenticated`) áp dụng cho cả hai; khác nhau ở `action` và `submit_endpoint`.
    Toàn bộ test US2.1 đều chạy parametrize qua cả hai tool.
  - ✅ Docstring nói rõ ngữ cảnh riêng: dùng khi khách muốn gặp chuyên viên — kể cả khi câu hỏi
    chính sách/pháp lý vượt quá khả năng các tool khác (đây chính là **đường thoát** mà guardrail
    của US3 sẽ cần). `preferred_time` = giờ muốn được gọi, `note` = nơi ghi câu hỏi.
  - ⚠️ Cùng rủi ro với US2.1: gọi tool **không** tạo yêu cầu tư vấn nào. Không được hứa với khách
    là sẽ có chuyên viên liên hệ.

### US4 — Tổng quan project
- [ ] **`project_overview(project_id)`** → `{project, stats}` gồm số lượng, giá/giá-trên-m2
  min/max/trung bình, khoảng số phòng ngủ, tỷ trọng các loại hình. **Chỉ mang tính mô tả** — không
  định giá/tư vấn.

### US5 — Bản đồ
- [ ] **`map_listings(project_id, limit)`** → `{count, points:[{id,title,property_type,price_vnd,lat,lng}]}`.

### US6 — So sánh
- [ ] **`compare_listings(listing_ids)`** → `{listings, fields}`; bắt buộc 2–4 id khác nhau; raise
  với những listing id không tồn tại.

---

## Giai đoạn 2 — cần xây (mới chỉ có đặc tả; chưa triển khai)

### US3 / RAG — Hỏi đáp chính sách / FAQ / pháp lý  ← phần lớn nhất
File: `src/app/tools/rag.py` (tool `answer_project_policy` đã được định nghĩa nhưng **đang tắt**).
DB hiện **chưa có bảng documents** và **pgvector chưa được cài**.

- [ ] **Thiết lập DB (migration):** `CREATE EXTENSION vector;` rồi tạo bảng `documents`:
      `(id, project_id, doc_type, source_url, chunk_index, content text, embedding vector(<dim>))`.
      Thêm index HNSW trên `embedding`. Nạp skill `supabase:supabase-postgres-best-practices` trước
      khi viết migration này.
- [ ] **Job nạp dữ liệu:** lấy tài liệu chính sách/FAQ/pháp lý/tiện ích của từng project → chia
      chunk → embed → insert. (Celery/Arq theo PRD; có thể bắt đầu bằng một script.)
- [ ] **Truy hồi lai (Postgres RPC `hybrid_search_docs`):** BM25/full-text (pgroonga hoặc tsvector)
      **+** tìm kiếm vector, trộn bằng **RRF**, rồi **rerank** (cross-encoder).
- [ ] **Triển khai `answer_project_policy(project_id, question, doc_type)`** →
      `{answer, sources:[{doc_id, chunk, score}], confident}`.
- [ ] **Guardrail (bắt buộc):** nếu điểm truy hồi cao nhất **thấp hơn ngưỡng**, đặt `confident=false`
      và trả về câu từ chối chuẩn kèm đề nghị chuyển sang chuyên viên tư vấn — **không** được bịa.
      Đây là yêu cầu hallucination<1% của PRD (US3 quy định rõ phải có đường từ chối này).
- [ ] Bật tool lên: xóa dòng `mcp.disable(...)` trong `rag.py`.

### Lưu booking (nâng US2.1/US2.2 từ form-spec thành ghi thật)
- [ ] Tạo bảng `bookings` `(id, project_id, kind, contact jsonb, preferred_time, note, created_at)`.
- [ ] Thêm tool **`submit_booking(kind, project_id, payload)`** để validate rồi insert, trả về id xác
      nhận. (Đây là thao tác *ghi* — cân nhắc RLS và rate-limit trước khi bật.)

### Nâng cấp chất lượng tìm kiếm
- [x] Chuẩn hóa các cột số của listing (generated column hoặc một view đã làm sạch) để
      `bedrooms`/`area_m2` lọc theo khoảng được ở SQL, và bỏ phần lọc bằng Python trong
      `search_listings`.
  - ⚠️ **Tiền đề của mục này đã lỗi thời.** Mục được viết khi các cột số còn lưu dạng `text`.
    DB hiện tại: `bedrooms` là `int`, `area_m2` là `float8`, nên **không cần** generated column
    hay view để lọc theo khoảng — `gte`/`lte` chạy thẳng trong SQL.
  - ✅ Phần lọc bằng Python đã bỏ từ lúc làm US1 (xem mục `search_listings` ở trên).
  - ✅ Thêm `min_area_m2` / `max_area_m2` — trước đây **không hề có** bộ lọc diện tích nào.
    Kiểm chứng: 50–70m² → trả về đúng dải, 80–120m² → 92 căn.
  - ✅ Thêm `min_bedrooms` / `max_bedrooms` để diễn đạt "từ N phòng trở lên"; `bedrooms` cũ giữ
    nguyên cho khớp chính xác.
  - ✅ Khoảng ngược (`min > max`) nay raise `ToolError` nói rõ trường nào. Trước đây SQL trả rỗng
    và agent hiểu thành "không có căn nào như vậy" thay vì "bạn hỏi một khoảng bất khả thi".
  - 🐞 **Việc còn lại — và lý do thật sự cần view, khác hẳn lý do ghi trong mục này.**
    Đối chiếu cột `bedrooms` với nhãn trong tiêu đề tin đăng:

    | `bedrooms` | n | Tiêu đề thực sự nói gì |
    |---:|---:|---|
    | 0 | 188 | Studio 100% ✅ |
    | **1** | **882** | **Studio 139 · 1PN 411 · 1PN+1 206 · khác 126** ⚠️ |
    | 2 | 908 | 2PN 782 · 2PN+1 126 ✅ |
    | 3 | 219 | 3PN 218 ✅ |

    Studio bị mã hoá **hai kiểu**: 188 dòng ở `bedrooms=0` và 139 dòng nữa lẫn trong
    `bedrooms=1`. Nên `search_listings(bedrooms=0)` chỉ tìm được 188 trên khoảng 327 căn studio,
    còn `bedrooms=1` trả về 139 căn studio không phải một phòng ngủ. Từ 2PN trở lên thì sạch.
    Cột `bedrooms_plus` cũng không cứu được: 300 dòng tiêu đề ghi trơn "1 PN" nhưng cờ vẫn bật.
  - ✅ **Đã xử lý bằng `migrations/002_listings_clean.sql`** — view `listings_clean` suy
    `bedrooms_norm` từ **tiêu đề tin đăng** thay vì tin cột số (93% số dòng đọc được từ tiêu đề;
    không tiêu đề nào dùng chữ "phòng ngủ", luôn viết tắt "PN"). Kết quả đã chạy trên Supabase,
    khớp chính xác dự đoán:

    | `bedrooms_norm` | 0 | 1 | 2 | 3 | 4 | NULL |
    |---|---:|---:|---:|---:|---:|---:|
    | số dòng | **379** | 641 | 945 | 227 | 2 | 161 |

    Studio nhảy từ 188 lên **379**; `bedrooms=1` không còn lẫn studio nào.
  - ✅ **Không rơi về cột `bedrooms` khi tiêu đề im lặng → trả NULL.** 126/161 dòng còn lại là
    shophouse/liền kề/thương mại đang mang `bedrooms=1` giả (`shophouse` 39/48,
    `thuong_mai_dich_vu` 11/11). NULL nghĩa "chưa rõ", trung thực hơn số 1 sai — và NULL thì bị
    mọi bộ lọc phòng ngủ loại ra, đúng ý muốn. Đánh đổi: mất 1 dòng `lien_ke` có `bedrooms=4`
    thật mà tiêu đề không ghi.
  - ✅ Thêm `has_flex_room` phân biệt "2 PN" với "2 PN + 1" (phòng đa năng, 344 dòng). Cột
    `bedrooms_plus` sẵn có không dùng được: nó bật cả trên 300 dòng tiêu đề ghi trơn "1 PN".
  - ✅ Dùng VIEW chứ không phải generated column: quy tắc suy từ tiêu đề còn phải chỉnh, view sửa
    bằng `CREATE OR REPLACE` và không đụng dòng dữ liệu nào; generated column phải `ALTER TABLE`
    toàn bảng và không lùi được.
  - ✅ Index: `(price_vnd, id)` phục vụ cả sắp xếp lẫn phân trang — đáng giá nhất; thêm
    `(project_id, price_vnd)`, `(area_m2)`, `(bedrooms)`.
  - ✅ Mọi truy vấn listing nay đi qua view (hằng số `LISTINGS` trong service), cột thô `bedrooms`
    **không còn được select** ở đâu cả.
  - Test: 6 test mới (khoảng diện tích trong SQL, khoảng phòng ngủ, khoảng ngược raise,
    `bedrooms` khớp tiêu đề, shophouse bị loại khỏi lọc phòng ngủ, `has_flex_room` khớp "+1").
- [ ] Thêm **`search_listings_by_province(province, ...)`**: đổi tỉnh thành → danh sách project id
      qua `locations`, rồi lọc listing (nhớ rằng: `listing` không có cột province).
- [ ] Chuyển phần thống kê của `project_overview` sang Postgres RPC để không phải fetch mọi dòng.

### Tùy chọn (làm được thì tốt)
- [ ] **`nearby_listings(lat, lng, radius_m, limit)`** dùng `earthdistance`/`postgis`.
- [ ] Expose một **resource** `realestate://project/{id}` (hồ sơ project chỉ đọc) qua `@mcp.resource`.

---

## Định nghĩa Hoàn thành (cho mỗi tool)
- [ ] Chữ ký hàm có kiểu + docstring viết cho model đọc (làm gì/khi nào/trả về gì).
- [ ] Truy cập DB nằm trong một hàm ở `services/`; thân tool mỏng.
- [ ] Trả về JSON đã định dạng; lỗi là `ToolError`.
- [ ] `mcp.call_tool(...)` trả về dữ liệu đúng khi chạy với DB thật.
- [ ] Xuất hiện trong `mcp.list_tools()` (hoặc bị tắt có chủ đích kèm comment giải thích lý do).
