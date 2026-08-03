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
- [ ] **`search_projects(query, province, limit)`** → danh sách node project.
  - Kiểm chứng: trả về 1–3 kết quả với tên rõ ràng, và nhiều kết quả với tên một phần (vd "chung cu").
  - Làm chắc thêm: đổi `ilike` → `pg_trgm similarity` + `unaccent` để "vinhome"/"Vinhomes" và truy
    vấn không dấu đều khớp. (các extension đã có sẵn; xem SCHEMA.md)
- [ ] **`resolve_project(text)`** → `{matched, project, candidates}`.
  - Khớp đúng một → `matched=true`; khớp nhiều → `matched=false` + candidates; không khớp → rỗng.
- [ ] **`list_project_buildings(project_id, limit)`** → các node location con.
- [ ] **`list_provinces()`** → danh sách tỉnh thành (không trùng, đã sắp xếp) có ít nhất một project.
- [ ] **`search_listings(project_id, property_type, min_price_vnd, max_price_vnd, bedrooms, limit)`**
  - Xác nhận khoảng giá được lọc ở SQL; xác nhận việc lọc `bedrooms` sau khi fetch hoạt động đúng
    (trường này là text!).
  - Xác nhận `property_type` không hợp lệ sẽ raise kèm danh sách giá trị hợp lệ.
- [ ] **`get_listing(listing_id)`** → chi tiết đầy đủ; raise nếu không tìm thấy.
- [ ] **`list_project_listings(project_id, limit)`** → toàn bộ căn trong một project ("xem tất cả").
- [ ] **`listing_cta_actions(listing_id)`** → 4 nút CTA + `next_tool` cho từng nút.
  - Quy tắc UI cần thực thi ở lớp trên: 1–3 kết quả thì hiện card+CTA; >3 thì hiện "xem tất cả".

### US2.1 — Đặt lịch tham quan
- [ ] **`start_visit_booking(project_id, is_authenticated)`** → form spec.
  - Form cho khách hỏi tên/điện thoại/email/thời gian/ghi chú; form đã đăng nhập chỉ hỏi thời
    gian/ghi chú.
  - Raise nếu `project_id` không phải project có thật.

### US2.2 — Tư vấn mua nhà
- [ ] **`start_consultation(project_id, is_authenticated)`** → form spec (chia theo trạng thái đăng
      nhập tương tự).

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
- [ ] Chuẩn hóa các cột số của listing (generated column hoặc một view đã làm sạch) để
      `bedrooms`/`area_m2` lọc theo khoảng được ở SQL, và bỏ phần lọc bằng Python trong
      `search_listings`.
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
