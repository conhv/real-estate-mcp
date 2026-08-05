-- 003 — Bảng `bookings`: nâng US2.1/US2.2 từ form-spec thành ghi thật
--       (mục "Lưu booking" trong docs/TOOLS_TODO.md)
--
-- Chạy trong Supabase SQL Editor (Dashboard > SQL Editor).
--
-- ⚠️ ĐÂY LÀ BẢNG GHI ĐẦU TIÊN CỦA DỰ ÁN, VÀ NÓ CHỨA DỮ LIỆU CÁ NHÂN
-- (họ tên, số điện thoại, email của người thật). Hai bảng cũ chỉ đọc và toàn dữ liệu công
-- khai; bảng này thì không. Mọi lựa chọn dưới đây đều xoay quanh điều đó.
--
-- Chạy file này KHÔNG bật tính năng ghi. `start_visit_booking` / `start_consultation` vẫn chỉ
-- trả form-spec với `persisted: false` cho tới khi có tool `submit_booking` (mục kế tiếp trong
-- checklist). Tạo bảng trước là để đường ghi có chỗ đáp xuống.


-- =====================================================================================
-- 1. BẢNG
-- =====================================================================================

CREATE TABLE IF NOT EXISTS bookings (
  id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Khớp đúng hai giá trị `action` mà tools/cta.py sinh ra. CHECK ở đây để một giá trị
  -- lạ bị chặn ngay tại DB, không phải chỉ trong Python.
  kind              text        NOT NULL
                                CHECK (kind IN ('visit_booking', 'consultation')),

  project_id        text        NOT NULL,

  -- Không nằm trong đặc tả gốc nhưng cần thiết: form của khách vãng lai hỏi tên/SĐT/email,
  -- form đã đăng nhập thì không. Thiếu cột này thì `contact` rỗng trở nên vô nghĩa — không
  -- phân biệt được "khách đã đăng nhập, liên hệ lấy từ hồ sơ" với "form lỗi, mất liên hệ".
  is_authenticated  boolean     NOT NULL DEFAULT false,

  -- {full_name, phone, email} với khách vãng lai; {} với người đã đăng nhập.
  contact           jsonb       NOT NULL DEFAULT '{}'::jsonb,

  -- Form đánh dấu bắt buộc, nhưng để nullable: "gọi tôi lúc nào cũng được" là yêu cầu hợp lệ
  -- và có thể xuất hiện sau. Ràng buộc DB chỉ nên khoá những bất biến không bao giờ đổi.
  preferred_time    timestamptz,

  note              text,
  created_at        timestamptz NOT NULL DEFAULT now(),

  -- Bất biến thật sự: một yêu cầu từ khách vãng lai mà không có cách liên hệ thì vô dụng —
  -- không ai gọi lại được, và người đó ngồi chờ một cuộc hẹn không tồn tại. Form đã đánh dấu
  -- `phone` là required cho khách; ràng buộc này khiến quy tắc đó không thể bị lách bằng một
  -- lệnh insert trực tiếp.
  CONSTRAINT bookings_guest_needs_phone CHECK (
    is_authenticated
    OR (contact ? 'phone' AND length(btrim(contact ->> 'phone')) > 0)
  )
);

COMMENT ON TABLE  bookings IS
  'Yêu cầu đặt lịch tham quan / tư vấn (US2.1, US2.2). CHỨA DỮ LIỆU CÁ NHÂN.';
COMMENT ON COLUMN bookings.contact IS
  '{full_name, phone, email} với khách vãng lai; {} khi is_authenticated (lấy từ hồ sơ).';
COMMENT ON COLUMN bookings.kind IS
  'visit_booking = đặt lịch tham quan (US2.1); consultation = tư vấn mua nhà (US2.2).';


-- =====================================================================================
-- 2. BẢO MẬT — quan trọng hơn hai bảng cũ
-- =====================================================================================
--
-- PostgREST tự phơi mọi bảng trong schema `public` ra API. Với `locations`/`listings` thì
-- không sao (dữ liệu công khai). Với bảng này, lộ ra là lộ số điện thoại người thật.

-- RLS bật, KHÔNG có policy nào = từ chối tất cả. anon và authenticated đọc ra 0 dòng.
-- Service-role key (thứ MCP server dùng) bỏ qua RLS nên vẫn ghi/đọc được.
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;

-- Phòng vệ lớp hai: gỡ luôn quyền ở tầng GRANT. Nếu sau này ai đó lỡ thêm một policy dễ dãi
-- (`USING (true)`), thiếu GRANT thì vẫn không đọc được. Một sơ suất không đủ để rò dữ liệu.
REVOKE ALL ON TABLE bookings FROM anon, authenticated;


-- =====================================================================================
-- 3. INDEX
-- =====================================================================================

-- Truy vấn hay dùng nhất: "các yêu cầu mới nhất của dự án này".
CREATE INDEX IF NOT EXISTS bookings_project_created_idx
  ON bookings (project_id, created_at DESC);

-- Bảng điều khiển: "yêu cầu mới nhất, mọi dự án".
CREATE INDEX IF NOT EXISTS bookings_created_idx
  ON bookings (created_at DESC);


-- =====================================================================================
-- 4. TUỲ CHỌN — khoá ngoại sang `locations`
-- =====================================================================================
--
-- Bỏ qua được: `_form_payload` trong tools/cta.py đã kiểm `project_id` phải là node
-- `level='project'` có thật. Nhưng đó là kiểm ở tầng ứng dụng, một lệnh insert thẳng vào DB
-- lách được — và với bảng ghi thì DB nên tự giữ được bất biến của nó.
--
-- Vướng: `locations` HIỆN KHÔNG CÓ PRIMARY KEY (xem docs/SCHEMA.md), mà khoá ngoại thì cần.
-- Đã kiểm: 352 dòng / 352 id khác nhau / không NULL → thêm PK an toàn.
--
-- Đây là thay đổi lên một bảng đang dùng, nên tách riêng để bạn tự quyết. Chạy hay không
-- chạy đều không ảnh hưởng phần 1–3 ở trên.
--
--   ALTER TABLE locations ADD PRIMARY KEY (id);
--   ALTER TABLE bookings  ADD CONSTRAINT bookings_project_fk
--     FOREIGN KEY (project_id) REFERENCES locations (id);
--
-- Lưu ý sau khi chạy: mọi lần nạp lại `locations` có id trùng sẽ bị từ chối thay vì lặng lẽ
-- ghi đè. Đó là điều mong muốn, nhưng job nạp dữ liệu cần biết trước.


-- =====================================================================================
-- 5. KIỂM CHỨNG
-- =====================================================================================
--
-- ① Bảng tồn tại và rỗng — kỳ vọng 0.
--    SELECT count(*) FROM bookings;
--
-- ② RLS đã bật — kỳ vọng true.
--    SELECT relrowsecurity FROM pg_class WHERE relname = 'bookings';
--
-- ③ Không có policy nào (tức từ chối tất cả) — kỳ vọng 0.
--    SELECT count(*) FROM pg_policies WHERE tablename = 'bookings';
--
-- ④ Ràng buộc liên hệ hoạt động — câu này PHẢI BÁO LỖI:
--    INSERT INTO bookings (kind, project_id, contact)
--    VALUES ('visit_booking', 'oh:amber-riverside', '{"full_name":"Test"}');
--    -- kỳ vọng: new row violates check constraint "bookings_guest_needs_phone"
--
-- ⑤ Còn câu này phải CHẠY ĐƯỢC, rồi nhớ xoá dòng test đi:
--    INSERT INTO bookings (kind, project_id, contact, preferred_time)
--    VALUES ('visit_booking', 'oh:amber-riverside',
--            '{"full_name":"Nguyễn Văn A","phone":"0900000000"}', now() + interval '2 days')
--    RETURNING id, created_at;
--
--    DELETE FROM bookings WHERE contact ->> 'phone' = '0900000000';
