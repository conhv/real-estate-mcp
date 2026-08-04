import json
import os
import webbrowser
import asyncio
from dotenv import load_dotenv

# Đọc cấu hình từ file .env
load_dotenv('.env')

from app.server import mcp

async def main():
    print("\n--- TEST BẢN ĐỒ UC5 ---")
    user_input = input("Nhập project_id (Ví dụ: vhm:vinhomes-grand-park) hoặc nhấn Enter để chọn ngẫu nhiên: ").strip()
    
    if user_input:
        project_id = user_input
        print(f"Ban da chon du an: {project_id}")
    else:
        # Tự động tìm một dự án bất kỳ có chứa listing hợp lệ (có tọa độ)
        try:
            from app.db import get_client
            client = get_client()
            sample = client.table("listings_full").select("project_id").not_.is_("lat", "null").limit(1).execute()
            if not sample.data:
                print("Khong tim thay du an nao co toa do trong Database.")
                return
            project_id = sample.data[0]["project_id"]
            print(f"Da tim thay du an co du lieu toa do: {project_id}")
        except Exception as e:
            print(f"Loi khi tim du an: {e}")
            return
    
    try:
        # Nếu muốn lấy tất cả dự án, đổi project_id=None
        res = await mcp.call_tool("map_listings", {"project_id": project_id, "limit": 100, "include_amenities": True})
        
        # Tương thích với thay đổi phiên bản của fastmcp (.structured_content hoặc .data)
        data = getattr(res, "structured_content", None)
        if data is None:
            data = getattr(res, "data", {})
            
        points = data.get("points", [])
        amenities = data.get("amenities", [])
        print(f"Da lay thanh cong {len(points)} dia diem tu DB va {len(amenities)} tien ich xung quanh.")
        
    except Exception as e:
        print(f"Co loi xay ra khi goi DB: {e}")
        return

    # Tạo giao diện Bản đồ bằng HTML + Leaflet.js
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Visual Test UC5 - Map Listings</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <!-- Tải thư viện Bản đồ Leaflet -->
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            #map {{ height: 100vh; width: 100%; margin: 0; padding: 0; }}
            body {{ margin: 0; padding: 0; font-family: sans-serif; }}
            .info-panel {{
                position: absolute; top: 10px; right: 10px; z-index: 999;
                background: white; padding: 15px; border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            }}
            .property-tooltip {{
                background-color: white;
                border: 1px solid #ccc;
                box-shadow: 0 1px 3px rgba(0,0,0,0.3);
                font-size: 13px;
                font-weight: 500;
                padding: 4px 8px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="info-panel">
            <h3>Test UC5: Bản đồ</h3>
            <p>Dự án: <b>{project_id}</b></p>
            <p>Số lượng điểm BĐS: <b>{len(points)}</b></p>
            <p>Số lượng Tiện ích: <b style="color: green;">{len(amenities)}</b></p>
        </div>
        <div id="map"></div>
        <script>
            // Dữ liệu lấy trực tiếp từ Supabase và OSM
            var points = {json.dumps(points)};
            var amenities = {json.dumps(amenities)};
            
            if (points.length === 0) {{
                alert("Không có điểm nào được trả về từ DB (Hoặc dự án chưa có tọa độ).");
            }}
            
            // Tìm tọa độ trung tâm để camera lia tới
            var centerLat = points.length > 0 ? points[0].lat : 21.0285;
            var centerLng = points.length > 0 ? points[0].lng : 105.8542;
            
            var map = L.map('map').setView([centerLat, centerLng], 14);
            
            // Load bản đồ nền từ OpenStreetMap
            L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19,
                attribution: '&copy; OpenStreetMap'
            }}).addTo(map);
            
            // Cắm các ghim (Marker) BĐS lên bản đồ
            points.forEach(function(p) {{
                if (p.lat && p.lng) {{
                    var priceStr = p.price_vnd ? (p.price_vnd / 1000000000).toFixed(2) + " Tỷ VNĐ" : "Thỏa thuận";
                    var popupText = "<b>" + p.title + "</b><br>" +
                                    "Loại: " + p.property_type + "<br>" +
                                    "<b style='color:red;'>Giá: " + priceStr + "</b>";
                    var tooltipText = p.title + "<br><b style='color:red;'>" + priceStr + "</b>";
                    
                    L.marker([p.lat, p.lng])
                     .addTo(map)
                     .bindPopup(popupText)
                     .bindTooltip(tooltipText, {{direction: 'top', className: 'property-tooltip'}});
                }}
            }});
            
            // Icon màu xanh lá cho tiện ích OSM
            var greenIcon = new L.Icon({{
                iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
                shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                iconSize: [25, 41],
                iconAnchor: [12, 41],
                popupAnchor: [1, -34],
                shadowSize: [41, 41]
            }});
            
            // Cắm các ghim tiện ích lên bản đồ
            amenities.forEach(function(a) {{
                if (a.lat && a.lng) {{
                    var popupText = "<b style='color:green;'>" + a.name + "</b><br>" +
                                    "Loại tiện ích: " + a.type;
                    L.marker([a.lat, a.lng], {{icon: greenIcon}}).addTo(map).bindPopup(popupText);
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    # Ghi ra file HTML
    html_path = os.path.abspath("uc5_map_test.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"Da tao file giao dien: {html_path}")
    print("Dang tu dong mo trinh duyet de hien thi ban do...")
    
    # Tự động mở trình duyệt web mặc định của bạn
    webbrowser.open('file://' + html_path)

if __name__ == "__main__":
    asyncio.run(main())
