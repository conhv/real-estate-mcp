"""OpenStreetMap (OSM) integration for nearby amenities."""

import json
import urllib.parse
import urllib.request
from typing import Any

def get_nearby_amenities(lat: float, lng: float, radius: int = 2000) -> list[dict[str, Any]]:
    """Fetch nearby amenities (schools, hospitals, parks, etc.) from OSM Overpass API.
    
    Args:
        lat: Latitude of the center point.
        lng: Longitude of the center point.
        radius: Search radius in meters (default 2000).
        
    Returns:
        List of amenities shaped as {"id", "name", "type", "lat", "lng"}.
    """
    # Overpass QL query
    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"~"school|hospital|clinic|marketplace|kindergarten"](around:{radius},{lat},{lng});
      way["amenity"~"school|hospital|clinic|marketplace|kindergarten"](around:{radius},{lat},{lng});
      node["leisure"~"park"](around:{radius},{lat},{lng});
      way["leisure"~"park"](around:{radius},{lat},{lng});
    );
    out center;
    """
    
    url = "https://overpass-api.de/api/interpreter"
    data = urllib.parse.urlencode({'data': query}).encode('utf-8')
    headers = {
        'User-Agent': 'RealEstateMCP/1.0 (test bot)',
        'Accept': '*/*'
    }
    req = urllib.request.Request(url, data=data, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            
        amenities = []
        for element in result.get('elements', []):
            tags = element.get('tags', {})
            name = tags.get('name')
            if not name:
                continue # Skip unnamed POIs
                
            # Determine type
            if 'amenity' in tags:
                poi_type = tags['amenity']
            elif 'leisure' in tags:
                poi_type = tags['leisure']
            else:
                poi_type = 'unknown'
                
            # Ways return center lat/lon if 'out center;' is used
            element_lat = element.get('lat') or element.get('center', {}).get('lat')
            element_lon = element.get('lon') or element.get('center', {}).get('lon')
            
            if element_lat and element_lon:
                amenities.append({
                    "id": str(element.get('id')),
                    "name": name,
                    "type": poi_type,
                    "lat": element_lat,
                    "lng": element_lon
                })
        
        # Sort by distance loosely (just return top 50 to avoid clutter)
        return amenities[:50]
        
    except Exception as e:
        print(f"OSM Overpass API Error: {e}")
        return []
