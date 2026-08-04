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
        assert shaping.normalize_status("�ANG BÁN") == "ĐANG BÁN"

    def test_empty_status_is_none(self):
        assert shaping.normalize_status(None) is None
        assert shaping.normalize_status("  ") is None


class TestShapeListingCard:
    def test_coerces_types_and_keeps_expected_keys(self):
        raw = {
            "id": "oh:XYZ",
            "title": "Căn 2PN",
            "area_m2": "72.3",  # text in DB
            "bedrooms": "2",  # text in DB
            "bathrooms": "2",  # text in DB
            "price_vnd": 3_000_000_000,  # bigint
            "status": "�ANG BÁN",  # corrupted
            "lat": 21.0,
            "lng": 105.8,
        }
        card = shaping.shape_listing_card(raw)
        assert card["area_m2"] == 72.3
        assert card["bedrooms"] == 2
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


class TestProjectPriceStats:
    def test_stats_calculation(self):
        from unittest.mock import MagicMock, patch
        import app.services.listings as listing_svc

        mock_rows = [
            {
                "price_vnd": 3_000_000_000,
                "price_per_m2_vnd": 50_000_000,
                "area_m2": "60.0",
                "property_type": "can_ho",
                "bedrooms": "2",
            },
            {
                "price_vnd": 5_000_000_000,
                "price_per_m2_vnd": 62_500_000,
                "area_m2": "80.0",
                "property_type": "can_ho",
                "bedrooms": "3",
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


