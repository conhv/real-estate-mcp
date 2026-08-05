# Kế hoạch triển khai — Real Estate MCP

Kế hoạch này biến PRD (`docs/PRD_LeDuyHung.pdf`) thành một FastMCP server có thể xây dựng được, mà
các tool của nó sẽ được LangGraph agent gọi về sau. Tài liệu nêu rõ kiến trúc, lý do các tool được
thiết kế như hiện tại, và lộ trình theo giai đoạn từ "tool chạy được" đến "agent đã deploy".

## 1. MCP nằm ở đâu trong kiến trúc PRD
Pipeline AI của PRD là:
`User → Guardrail → Intent Detection → Entity Extraction → Conversation Manager → **Tool Calling Layer** → Response Composer → UI`.

**Repo này chỉ xây Tool Calling Layer** — MCP server và các tool của nó. Lớp agent (LangGraph
supervisor, intent/entity/slot-filling, Langfuse tracing, SSE streaming, Redis session) là một lớp
*riêng biệt*, sẽ kết nối tới MCP server này qua HTTP và gọi các tool. Việc giữ tool trong một MCP
server (thay vì hardcode vào agent) chính là lựa chọn "MCP as tool protocol" của PRD, và cho phép ta
thay thế/deploy lại agent một cách độc lập.

Quy tắc ranh giới (từ mục "Out of Scope" của PRD): tool chỉ trả về **dữ liệu mô tả** — không định
giá, không tính toán tài chính/vay mua, không khuyến nghị đầu tư. Ràng buộc này được áp trong
docstring của tool + instructions của server để agent không bị cám dỗ tự suy diễn ra lời khuyên.

## 2. Thực tế mô hình dữ liệu (xem docs/SCHEMA.md)
Hai bảng dùng được: `locations` (cây project/cluster/building) và `listing` (1748 căn). **Không có
bảng projects** (project là các dòng trong `locations`) và **chưa có kho dữ liệu cho RAG**. Các
trường số của listing đang lưu dạng text; `status` bị lỗi mã hóa. Toàn bộ những vấn đề này được hấp
thụ trong `shaping.py` để tool trả về JSON sạch, đúng kiểu.

## 3. Nguyên tắc thiết kế cho các tool
1. **Một MCP server, tool mỏng.** Hàm `@mcp.tool` chỉ validate input và định dạng output; toàn bộ
   truy cập DB nằm trong `services/`. Quy tắc nghiệp vụ vẫn test được và tách khỏi lớp protocol.
2. **Tool ánh xạ tới User Story.** Mỗi tool ghi rõ US của nó trong docstring để agent (và người
   chấm) truy vết được độ phủ.
3. **Docstring chính là contract.** Agent chọn tool hoàn toàn dựa trên tên + mô tả + tham số có
   kiểu. Hãy viết cho model đọc: nói rõ *nó làm gì*, *khi nào dùng*, *trả về cái gì*.
4. **Luồng ưu tiên project.** Gần như mọi US đều cần biết project là gì. Các tool được sắp xếp để
   agent xác định project trước (`search_projects`/`resolve_project`) rồi mới tìm kiếm/so sánh/đặt lịch.
5. **CTA trả về payload hành động cho UI, không phải văn xuôi.** Tool đặt lịch/tư vấn trả về một
   *form spec* (các trường phụ thuộc trạng thái đăng nhập) để frontend render — khớp với mục
   "Action Triggering" của PRD.
6. **Không để secret trong code**; service-role key lấy từ `.env`. Lỗi được chuyển thành `ToolError`,
   không bao giờ để lộ chuỗi kết nối.

## 4. Độ phủ Tool ↔ User Story (giai đoạn 1, đã triển khai hết)
| Tool | User Story | Mục đích |
|---|---|---|
| `search_projects` | US1 | tìm project theo tên/tỉnh thành (nút chọn nhanh) |
| `resolve_project` | US1/2.1/2.2/3 | slot-filling: đoạn text này có phải tên project không? |
| `list_project_buildings` | US1 | đi sâu vào các tòa nhà của một project |
| `list_provinces` | US1 | đưa ra các lựa chọn địa điểm |
| `search_listings` | US1 | tìm căn có lọc trong phạm vi một project |
| `get_listing` | US1 | trang chi tiết tin đăng |
| `list_project_listings` | US1 | danh sách "xem tất cả" |
| `compare_listings` | US6 | so sánh song song 2–4 căn |
| `project_overview` | US4 | thống kê mô tả giá/diện tích/loại hình theo project |
| `map_listings` | US5 | tọa độ lat/lng cho chế độ xem bản đồ |
| `start_visit_booking` | US2.1 | form spec đặt lịch tham quan (đã đăng nhập vs khách) |
| `start_consultation` | US2.2 | form spec tư vấn (đã đăng nhập vs khách) |
| `listing_cta_actions` | US1 | các nút CTA + tool tương ứng mà mỗi nút kích hoạt |
| `answer_project_policy` | US3 | **giai đoạn 2, đang tắt** — RAG chính sách/FAQ kèm guardrail từ chối |

## 5. Phân giai đoạn
**Giai đoạn 1 — Tool chạy trên dữ liệu thật (repo này).** ✅ Server + 13 tool + tài liệu
schema/plan/todo + skills. RAG được chủ động bỏ qua (đã stub + ghi tài liệu). Đã kiểm chứng: server
load được, liệt kê đủ tool.

**Giai đoạn 2 — Chất lượng dữ liệu + chất lượng tìm kiếm.**
- Chuẩn hóa các cột số (generated column hoặc một view đã làm sạch) để lọc theo khoảng chạy được ở SQL.
- Tìm kiếm tiếng Việt gần đúng: `pg_trgm` + `unaccent` cho `search_projects`.
- Chuyển phần tổng hợp của `project_overview` sang Postgres RPC (tránh kéo toàn bộ dòng về).
- RAG (US3): cài `vector`, tạo bảng `documents`, nạp tài liệu chính sách/FAQ/pháp lý, hybrid search
  (pgroonga/BM25 + vector) trộn bằng RRF, rerank, và **bắt buộc thực thi cơ chế từ chối theo ngưỡng
  similarity** (guardrail hallucination<1% của PRD). Sau đó bật `answer_project_policy`.
- Lưu thật booking/tư vấn (đường ghi + bảng `bookings`) thay vì chỉ trả về form spec.

**Giai đoạn 3 — Tích hợp agent & triển khai.**
- Chạy MCP qua HTTP (`MCP_TRANSPORT=http`). LangGraph supervisor kết nối vào với vai trò MCP client.
- Đấu nối Langfuse tracing, Redis session/thread state, FastAPI+SSE streaming (đều nằm ở lớp agent).
- Đánh giá trên golden dataset (RAGAS/DeepEval) trong CI trước khi release, theo PRD.

## 6. Cách chạy / kiểm chứng
```powershell
.\.venv\Scripts\python.exe -m pip install -e .
# liệt kê tool mà không cần DB:
.\.venv\Scripts\python.exe -c "import asyncio; from app.server import mcp; print(len(asyncio.run(mcp.list_tools())))"
# chạy server stdio (cần .env có SUPABASE_SERVICE_ROLE_KEY):
.\.venv\Scripts\python.exe -m app
```

## 7. Ánh xạ tiêu chí thành công (PRD §VI)
Lớp agent chịu trách nhiệm về độ chính xác intent/entity và chỉ số hallucination; lớp này hỗ trợ
bằng cách (a) biến việc xác định project/entity thành một tool hạng nhất (`resolve_project`) để nâng
độ chính xác entity, và (b) cung cấp contract từ chối của RAG (giai đoạn 2) để giữ hallucination < 1%.
