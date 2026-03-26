"""
Location Search API Proxy
Proxies requests to OpenStreetMap Nominatim API to avoid CORS issues
"""

from flask import Blueprint, request, jsonify
import requests
from functools import lru_cache
import time

location_api = Blueprint('location_api', __name__)

# Rate limiting
last_request_time = 0
MIN_REQUEST_INTERVAL = 1.0  # seconds

@lru_cache(maxsize=100)
def cached_location_search(query):
    """Cached location search to reduce API calls"""
    return search_location_nominatim(query)

def search_location_nominatim(query):
    """Search for locations using OpenStreetMap Nominatim API"""
    global last_request_time
    
    # Rate limiting - Nominatim requires 1 request per second
    current_time = time.time()
    time_since_last = current_time - last_request_time
    if time_since_last < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - time_since_last)
    
    last_request_time = time.time()
    
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'format': 'json',
            'q': query,
            'limit': 5,
            'addressdetails': 1
        }
        headers = {
            'User-Agent': 'AQI_Smart_Health_Advisor/1.0 (Flask Backend Proxy)'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        
        return response.json()
    except requests.RequestException as e:
        print(f"Nominatim API error: {e}")
        return []

@location_api.route('/api/location/search', methods=['GET'])
def location_search():
    """
    API endpoint to search for locations
    Query parameter: q (search query)
    Returns: JSON with location results
    """
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({
            'success': False,
            'message': 'Query parameter is required',
            'results': []
        }), 400
    
    if len(query) < 2:
        return jsonify({
            'success': False,
            'message': 'Query must be at least 2 characters',
            'results': []
        }), 400
    
    try:
        # Use cached search to reduce API calls
        results = cached_location_search(query)
        
        # Format results
        formatted_results = []
        for place in results:
            formatted_results.append({
                'display_name': place.get('display_name', ''),
                'lat': place.get('lat', ''),
                'lon': place.get('lon', ''),
                'type': place.get('type', ''),
                'importance': place.get('importance', 0)
            })
        
        return jsonify({
            'success': True,
            'results': formatted_results,
            'count': len(formatted_results)
        }), 200
        
    except Exception as e:
        print(f"Location search error: {e}")
        return jsonify({
            'success': False,
            'message': 'Location search failed',
            'results': []
        }), 500

# Clear cache periodically (every hour)
def clear_old_cache():
    """Clear location search cache"""
    cached_location_search.cache_clear()
    print("Location search cache cleared")