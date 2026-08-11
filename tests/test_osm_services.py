"""Integration and unit tests for OpenStreetMap (UC5) & OSRM Commute Engine (UC6)."""

import pytest
from app.services import osm as osm_svc


def test_calculate_osrm_matrix_empty():
    """Verify calculate_osrm_matrix handles empty input safely."""
    res = osm_svc.calculate_osrm_matrix([], [])
    assert res.get("status") == "error" or res.get("matrix") == []


def test_calculate_osrm_matrix_live():
    """Test live OSRM matrix calculation between multiple coordinates on road network."""
    origins = [(20.9940, 105.9510), (20.9965, 105.9535)]
    destinations = [(20.9888, 105.9468), (20.9949, 105.9589)]

    res = osm_svc.calculate_osrm_matrix(origins, destinations, profile="driving")
    assert res.get("status") == "success"
    assert "distances_m" in res
    assert "durations_s" in res
    assert len(res["matrix"]) == 2
    assert len(res["matrix"][0]) == 2
    assert res["matrix"][0][0]["distance_m"] > 0
    assert res["matrix"][0][0]["duration_min"] > 0
    assert "text" in res["matrix"][0][0]


def test_fetch_nearby_amenities_with_commute_live():
    """Test live integration of UC5 OSM amenities combined with UC6 OSRM commute measurement."""
    lat, lng = 20.9940, 105.9510
    amenities = osm_svc.fetch_nearby_amenities_with_commute(lat, lng, profile="driving")
    assert isinstance(amenities, list)
    if amenities:
        first = amenities[0]
        assert "name" in first
        assert "category" in first
        assert "lat" in first
        assert "lng" in first
        assert "distance_km" in first
        assert "duration_min" in first
        assert "travel_summary" in first
