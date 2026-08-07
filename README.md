# Real Estate MCP

Một server [FastMCP](https://gofastmcp.com) cung cấp các công cụ phân tích thị trường bất động sản
qua Model Context Protocol (MCP), lấy dữ liệu từ Supabase Postgres. Được xây dựng để lớp
LangGraph/agent sau này gọi các công cụ này (xem `docs/PRD_LeDuyHung.pdf`).

## Bắt đầu nhanh

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env   # sau đó điền SUPABASE_SERVICE_ROLE_KEY
.\.venv\Scripts\python.exe -m app        # stdio (cho MCP client chạy cục bộ)
```

Để triển khai cho agent qua HTTP, đặt `MCP_TRANSPORT=http` trong `.env` rồi chạy cùng lệnh trên;
agent kết nối tới `http://<host>:<port>/mcp`.

## Cấu trúc

```
src/app/
  server.py        # instance `mcp` duy nhất + main()
  config.py        # cấu hình từ biến môi trường (không để secret trong code)
  db.py            # Supabase client được cache
  shaping.py       # row -> dict cho agent (ép kiểu số lưu dạng text, sửa lỗi mã hóa status)
  services/        # toàn bộ truy cập DB (locations, listings)
  tools/           # định nghĩa @mcp.tool nhóm theo user story (lớp bọc mỏng trên services)
```

## Tài liệu
- `docs/SCHEMA.md` — schema thật của database + các điểm cần lưu ý.
- `docs/PLAN.md` — kiến trúc, hướng tiếp cận và chiến lược triển khai theo từng giai đoạn.
- `docs/TOOLS_TODO.md` — checklist triển khai dành cho học viên (cần xây gì, cho từng tool).

## Skills (dành cho Claude Code)
- `.claude/skills/fastmcp` — cách xây/chạy/kiểm thử các FastMCP tool trong dự án này.
- `.claude/skills/supabase-access` — mẫu Supabase client/query mà các tool đang dùng.
