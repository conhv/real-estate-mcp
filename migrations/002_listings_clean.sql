-- 002 — View chuẩn hoá số phòng ngủ + index cho lọc theo khoảng
--       (mục "Nâng cấp chất lượng tìm kiếm" trong docs/TOOLS_TODO.md)
--
-- Chạy trong Supabase SQL Editor (Dashboard > SQL Editor) TRƯỚC khi deploy code gọi
-- `listings_clean`. Không có view này thì services/listings.py sẽ lỗi
-- "Could not find the table public.listings_clean", giống hệt cách 001 từng lỗi.
--
-- An toàn khi chạy: view là đối tượng mới, index dùng IF NOT EXISTS, bảng `listings` không
-- bị sửa. Code hiện tại vẫn đọc bảng gốc nên chạy file này không làm hỏng gì đang chạy.


-- =====================================================================================
-- 1. VIEW listings_clean
-- =====================================================================================
--
-- VÌ SAO CẦN: cột `bedrooms` không đáng tin ở nhóm nhỏ. Đối chiếu 2355 dòng với nhãn
-- trong tiêu đề tin đăng:
--
--   bedrooms=0   188 dòng   Studio 100%                          ✅ sạch
--   bedrooms=1   882 dòng   Studio 139 · 1PN 411 · 1PN+1 206 ·
--                           Shop/liền kề 126                     ⚠️ lẫn lộn
--   bedrooms=2   908 dòng   2PN 782 · 2PN+1 126                  ✅ sạch
--   bedrooms=3   219 dòng   3PN 218                              ✅ sạch
--
-- Hai hậu quả: (a) studio bị mã hoá hai kiểu nên tìm bedrooms=0 chỉ ra 188/379 căn;
-- (b) tìm bedrooms=1 trả về 139 căn studio và 126 căn shophouse/liền kề.
--
-- Riêng shophouse có bedrooms=1 trên 39/48 dòng và thuong_mai_dich_vu trên 11/11 —
-- một căn shophouse không có "1 phòng ngủ", đó là giá trị mặc định chứ không phải dữ liệu.
--
-- QUY TẮC: tiêu đề là nguồn đáng tin, không phải cột số. Suy được 2194/2355 dòng (93%).
-- Không có tiêu đề nào dùng chữ "phòng ngủ" — luôn viết tắt "PN".
--
-- KHÔNG rơi về cột `bedrooms` khi tiêu đề im lặng: 126/161 dòng còn lại chính là nhóm
-- shophouse/liền kề mang giá trị rác nói trên. NULL ("chưa rõ") trung thực hơn số 1 sai.
--
-- Dùng VIEW chứ không phải generated column: quy tắc suy từ tiêu đề chắc chắn còn phải
-- chỉnh, mà view sửa bằng CREATE OR REPLACE và không đụng một dòng dữ liệu nào; generated
-- column thì phải ALTER TABLE trên toàn bảng và không lùi lại được.

CREATE OR REPLACE VIEW listings_clean AS
SELECT
  l.*,

  -- Số phòng ngủ đã chuẩn hoá. NULL = tiêu đề không nói, và cột gốc không đáng tin.
  CASE
    WHEN l.title ILIKE '%studio%' THEN 0
    WHEN substring(l.title from '(?i)(\d)\s*PN') IS NOT NULL
      THEN substring(l.title from '(?i)(\d)\s*PN')::int
    ELSE NULL
  END AS bedrooms_norm,

  -- "+1" trong "2 PN + 1" = phòng đa năng. Chỉ tin tiêu đề: cột bedrooms_plus bật cả trên
  -- 300 dòng mà tiêu đề ghi trơn "1 PN", nên tự nó không phân biệt được gì.
  (l.title ~* '\d\s*PN\s*\+\s*1') AS has_flex_room

FROM listings l;

COMMENT ON VIEW listings_clean IS
  'listings + bedrooms_norm/has_flex_room suy từ tiêu đề. Xem migrations/002.';


-- =====================================================================================
-- 2. INDEX cho lọc theo khoảng và phân trang
-- =====================================================================================
--
-- Đặt trên bảng gốc; view kế thừa vì nó chỉ là truy vấn có tên.

-- Mọi truy vấn listing đều ORDER BY price_vnd, id — index tổ hợp này phục vụ cả phần
-- sắp xếp lẫn phần RANGE() của phân trang, nên là cái đáng giá nhất trong ba cái.
CREATE INDEX IF NOT EXISTS listings_price_id_idx ON listings (price_vnd, id);

CREATE INDEX IF NOT EXISTS listings_area_idx     ON listings (area_m2);
CREATE INDEX IF NOT EXISTS listings_bedrooms_idx ON listings (bedrooms);

-- Lọc theo dự án là bộ lọc hay dùng nhất, gần như luôn đi kèm sắp xếp theo giá.
CREATE INDEX IF NOT EXISTS listings_project_price_idx ON listings (project_id, price_vnd);


-- =====================================================================================
-- 3. KIỂM CHỨNG — chạy và đối chiếu trước khi tin dùng
-- =====================================================================================
--
-- ① Phân bố mới. Kỳ vọng chính xác:  0→379  1→641  2→945  3→227  4→2  NULL→161
--    SELECT bedrooms_norm, count(*) FROM listings_clean
--    GROUP BY 1 ORDER BY 1 NULLS LAST;
--
-- ② Studio gộp về một mối: 379, không còn 188.
--    SELECT count(*) FROM listings_clean WHERE bedrooms_norm = 0;
--
-- ③ Không còn studio nào bị xếp là 1 phòng ngủ — phải trả về 0 dòng.
--    SELECT count(*) FROM listings_clean
--    WHERE bedrooms_norm = 1 AND title ILIKE '%studio%';
--
-- ④ Shophouse/thương mại không còn mang số phòng ngủ giả — phải trả về 0 dòng.
--    SELECT count(*) FROM listings_clean
--    WHERE property_type IN ('shophouse','thuong_mai_dich_vu')
--      AND bedrooms_norm IS NOT NULL;
--
-- ⑤ Phòng đa năng: kỳ vọng 344 dòng.
--    SELECT count(*) FROM listings_clean WHERE has_flex_room;
--
-- ⑥ Tổng số dòng không đổi: 2355. View không được thêm hay bớt dòng nào.
--    SELECT count(*) FROM listings_clean;
