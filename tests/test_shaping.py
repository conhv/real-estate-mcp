"""No-DB unit tests for the row-shaping layer.

These run instantly with no Supabase connection. They pin down the tricky data-quality behavior
described in docs/SCHEMA.md: text-typed numbers and the corrupted `status` value. If you change
`shaping.py`, these tell you immediately whether you broke the contract.
"""

from __future__ import annotations

from app import shaping


class TestCoercion:
    def test_to_float_handles_text_numbers(self):
        assert shaping.to_float("75.5") == 75.5
        assert shaping.to_float("1,200") == 1200.0  # stray comma
        assert shaping.to_float("  80 ") == 80.0
        assert shaping.to_float(90) == 90.0

    def test_to_float_whole_floats_return_int(self):
        assert shaping.to_float("43.0") == 43
        assert isinstance(shaping.to_float("43.0"), int)
        assert shaping.to_float("72.5") == 72.5

    def test_to_float_bad_values_are_none(self):
        assert shaping.to_float(None) is None
        assert shaping.to_float("") is None
        assert shaping.to_float("n/a") is None

    def test_to_int_truncates(self):
        assert shaping.to_int("3") == 3
        assert shaping.to_int("2.0") == 2
        assert shaping.to_int(None) is None


class TestStatusNormalization:
    def test_clean_status_passthrough(self):
        assert shaping.normalize_status("ĐANG BÁN") == "ĐANG BÁN"

    def test_mojibake_status_is_fixed(self):
        # the corrupted variant from the DB contains the replacement char
        assert shaping.normalize_status("ANG BÁN") == "ĐANG BÁN"

    def test_empty_status_is_none(self):
        assert shaping.normalize_status(None) is None
        assert shaping.normalize_status("  ") is None


class TestShapeListingDetail:
    def test_shapes_full_detail_attributes(self):
        raw = {
            "id": "vhm:123",
            "title": "Căn hộ 2PN+1",
            "bedrooms_norm": "2",
            "has_flex_room": True,
            "bathrooms": 2,
            "floor_num": "12",
            "floor_band": "tang_trung",
            "direction_balcony": "Đông Nam",
            "view": "View Công viên",
            "legal_status": "Sổ hồng lâu dài",
            "furnishing": "Full nội thất",
            "usage_status": "Nhà trống bàn giao ngay",
            "price_vnd": 3_500_000_000,
            "area_m2": 63.5,
        }
        detail = shaping.shape_listing_detail(raw)
        assert detail["has_flex_room"] is True
        assert detail["floor_num"] == 12
        assert detail["floor_band"] == "tang_trung"
        assert detail["direction_balcony"] == "Đông Nam"
        assert detail["view"] == "View Công viên"
        assert detail["legal_status"] == "Sổ hồng lâu dài"


class TestShapeListingCard:
    def test_coerces_types_and_keeps_expected_keys(self):
        raw = {
            "id": "oh:XYZ",
            "title": "Căn 2PN",
            "area_m2": "72.3",  # text in DB
            "bedrooms_norm": "2",  # derived by the listings_clean view, not the raw column
            "has_flex_room": True,
            "bathrooms": "2",  # text in DB
            "price_vnd": 3_000_000_000,  # bigint
            "status": "�ANG BÁN",  # corrupted
            "lat": 21.0,
            "lng": 105.8,
        }
        card = shaping.shape_listing_card(raw)
        assert card["area_m2"] == 72.3
        assert card["bedrooms"] == 2
        assert card["has_flex_room"] is True
        assert card["price_vnd"] == 3_000_000_000
        assert card["status"] == "ĐANG BÁN"
        # returns plain JSON-serializable dict
        import json

        json.dumps(card)  # must not raise


class TestShapeLocation:
    def test_project_node(self):
        raw = {"id": "oh:amber-riverside", "level": "project", "name": "Amber Riverside",
               "province": "Hà Nội", "district": "Hai Bà Trưng", "parent_id": None,
               "project_id": None, "lat": 21.0, "lng": 105.8}
        out = shaping.shape_location(raw)
        assert out["id"] == "oh:amber-riverside"
        assert out["level"] == "project"
        assert set(out) == {"id", "level", "name", "province", "district", "parent_id",
                            "project_id", "lat", "lng"}


class TestComputeComparisonInsights:
    def test_insights_calculation(self):
        listings = [
            {
                "id": "item1",
                "project_id": "proj:A",
                "province": "Hà Nội",
                "price_vnd": 3_000_000_000,
                "price_per_m2_vnd": 50_000_000,
                "area_m2": 60.0,
                "bedrooms": 2,
            },
            {
                "id": "item2",
                "project_id": "proj:A",
                "province": "Hà Nội",
                "price_vnd": 4_000_000_000,
                "price_per_m2_vnd": 40_000_000,
                "area_m2": 100.0,
                "bedrooms": 3,
            },
        ]
        insights = shaping.compute_comparison_insights(listings)
        ctx = insights["context"]
        assert ctx["same_project"] is True
        assert ctx["same_province"] is True
        assert ctx["projects"] == ["proj:A"]

        deltas = insights["deltas"]
        assert deltas["price_vnd"]["diff"] == 1_000_000_000
        assert deltas["area_m2"]["diff"] == 40.0

        hl = insights["highlights"]
        assert "cheapest_price" in hl["item1"]
        assert "largest_area" in hl["item2"]
        assert "lowest_price_per_m2" in hl["item2"]


class TestProjectPriceStats:
    def test_stats_calculation(self):
        from unittest.mock import MagicMock, patch

        import app.services.listings as listing_svc

        # `bedrooms_norm`, not `bedrooms`: project_price_stats reads the listings_clean view
        # (migrations/002), where the count comes from the listing title. A mock keyed on the
        # raw column would make bedrooms_range come back all-None and the assertion below fail.
        mock_rows = [
            {
                "price_vnd": 3_000_000_000,
                "price_per_m2_vnd": 50_000_000,
                "area_m2": "60.0",
                "property_type": "can_ho",
                "bedrooms_norm": "2",
            },
            {
                "price_vnd": 5_000_000_000,
                "price_per_m2_vnd": 62_500_000,
                "area_m2": "80.0",
                "property_type": "can_ho",
                "bedrooms_norm": "3",
            },
        ]
        with patch("app.services.listings.get_client") as mock_db:
            mock_table = MagicMock()
            mock_db.return_value.table.return_value = mock_table
            mock_table.select.return_value.eq.return_value.execute.return_value.data = mock_rows

            stats = listing_svc.project_price_stats("oh:amber-riverside")
            assert stats["count"] == 2
            assert stats["price_vnd"] == {"min": 3_000_000_000, "max": 5_000_000_000, "avg": 4_000_000_000}
            assert stats["price_per_m2_vnd"] == {"min": 50_000_000, "max": 62_500_000, "avg": 56_250_000}
            assert stats["area_m2"] == {"min": 60.0, "max": 80.0, "avg": 70.0}
            assert stats["bedrooms_range"] == {"min": 2, "max": 3}
            assert stats["by_property_type"] == {"can_ho": 2}

