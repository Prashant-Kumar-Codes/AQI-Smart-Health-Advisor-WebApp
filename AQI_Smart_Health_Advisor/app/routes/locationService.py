"""
Centralized Location Service for Backend
Handles geocoding, reverse geocoding, and AQI data fetching
WITH FLASK ROUTES
"""

import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from math import radians, sin, cos, sqrt, atan2
import os
from flask import Blueprint, request, jsonify

# AQI API Configuration
WAQI_API_TOKEN = os.getenv('WAQI_API_TOKEN', '46797eab2434e3cb85537e21e9a80bcb309220e3')
WAQI_BASE_URL = 'https://api.waqi.info'


class LocationService:
    """Centralized location and AQI service"""
    
    def __init__(self):
        self.geolocator = Nominatim(user_agent="aqi_health_advisor")
    
    @staticmethod
    def calculate_distance(lat1, lon1, lat2, lon2):
        """Calculate distance between two coordinates in kilometers"""
        try:
            lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            return round(6371 * c, 1)
        except Exception as e:
            print(f"Distance calculation error: {e}")
            return None
    
    def geocode_location(self, location_name):
        """
        Convert location name to precise coordinates
        Returns: dict with lat, lon, display_name, address
        """
        try:
            print(f"\n🔍 Geocoding: {location_name}")
            
            location = self.geolocator.geocode(
                location_name,
                timeout=10,
                language='en',
                addressdetails=True
            )
            
            if not location:
                return {
                    'success': False,
                    'error': f'Location "{location_name}" not found'
                }
            
            # Extract clean city name
            city_name = (
                location.raw.get('address', {}).get('city') or
                location.raw.get('address', {}).get('town') or
                location.raw.get('address', {}).get('village') or
                location.raw.get('address', {}).get('municipality') or
                location.raw.get('address', {}).get('county') or
                location.address.split(',')[0]
            )
            
            result = {
                'success': True,
                'lat': location.latitude,
                'lon': location.longitude,
                'display_name': city_name,
                'full_address': location.address,
                'address': location.raw.get('address', {})
            }
            
            print(f"✅ Geocoded: {city_name} ({result['lat']:.4f}, {result['lon']:.4f})")
            return result
            
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"❌ Geocoding error: {e}")
            return {
                'success': False,
                'error': 'Geocoding service unavailable. Please try again.'
            }
        except Exception as e:
            print(f"❌ Unexpected geocoding error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def reverse_geocode(self, lat, lon):
        """
        Convert coordinates to location name
        Returns: dict with display_name, address
        """
        try:
            print(f"\n📍 Reverse geocoding: {lat:.4f}, {lon:.4f}")
            
            location = self.geolocator.reverse(
                (lat, lon),
                timeout=10,
                language='en',
                addressdetails=True
            )
            
            if not location:
                return {
                    'success': False,
                    'error': 'Location not found for coordinates'
                }
            
            # Extract clean city name
            city_name = (
                location.raw.get('address', {}).get('city') or
                location.raw.get('address', {}).get('town') or
                location.raw.get('address', {}).get('village') or
                location.raw.get('address', {}).get('municipality') or
                location.raw.get('address', {}).get('county') or
                location.address.split(',')[0]
            )
            
            result = {
                'success': True,
                'display_name': city_name,
                'full_address': location.address,
                'address': location.raw.get('address', {})
            }
            
            print(f"✅ Reverse geocoded: {city_name}")
            return result
            
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"❌ Reverse geocoding error: {e}")
            return {
                'success': False,
                'error': 'Reverse geocoding service unavailable'
            }
        except Exception as e:
            print(f"❌ Unexpected reverse geocoding error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_aqi_by_coordinates(self, lat, lon):
        """
        Fetch AQI data using precise coordinates
        Returns: dict with AQI data
        """
        try:
            print(f"\n🌡️ Fetching AQI for: {lat:.4f}, {lon:.4f}")
            
            url = f"{WAQI_BASE_URL}/feed/geo:{lat};{lon}/?token={WAQI_API_TOKEN}"
            
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if data.get('status') != 'ok':
                return {
                    'success': False,
                    'error': 'AQI data not available for this location'
                }
            
            station_data = data.get('data', {})
            aqi_value = station_data.get('aqi', 0)
            station_name = station_data.get('city', {}).get('name', 'Unknown Station')
            
            print(f"✅ AQI data retrieved: {aqi_value} from {station_name}")
            
            return {
                'success': True,
                'aqi': aqi_value,
                'city': station_data.get('city', {}),
                'iaqi': station_data.get('iaqi', {}),
                'time': station_data.get('time', {}),
                'dominentpol': station_data.get('dominentpol'),
                'station_name': station_name
            }
            
        except requests.RequestException as e:
            print(f"❌ AQI API request error: {e}")
            return {
                'success': False,
                'error': 'Failed to fetch AQI data. Please try again.'
            }
        except Exception as e:
            print(f"❌ Unexpected AQI fetch error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_aqi_from_location_name(self, location_name):
        """
        Complete flow: Location name -> Coordinates -> AQI
        Returns: dict with location and AQI data
        """
        # Step 1: Geocode location
        geocode_result = self.geocode_location(location_name)
        if not geocode_result['success']:
            return geocode_result
        
        # Step 2: Fetch AQI
        aqi_result = self.get_aqi_by_coordinates(
            geocode_result['lat'],
            geocode_result['lon']
        )
        
        if not aqi_result['success']:
            return aqi_result
        
        # Combine results
        return {
            'success': True,
            'location': {
                'lat': geocode_result['lat'],
                'lon': geocode_result['lon'],
                'display_name': geocode_result['display_name'],
                'full_address': geocode_result['full_address']
            },
            'aqi_data': aqi_result
        }
    
    def get_aqi_from_coordinates(self, lat, lon):
        """
        Complete flow: Coordinates -> Location name -> AQI
        Returns: dict with location and AQI data
        """
        # Step 1: Reverse geocode
        geocode_result = self.reverse_geocode(lat, lon)
        
        # Step 2: Fetch AQI
        aqi_result = self.get_aqi_by_coordinates(lat, lon)
        
        if not aqi_result['success']:
            return aqi_result
        
        # Combine results
        return {
            'success': True,
            'location': {
                'lat': lat,
                'lon': lon,
                'display_name': geocode_result.get('display_name', 'Unknown') if geocode_result['success'] else 'Unknown',
                'full_address': geocode_result.get('full_address', '') if geocode_result['success'] else ''
            },
            'aqi_data': aqi_result
        }


# Create singleton instance
location_service = LocationService()


# ========== FLASK ROUTES ==========
# Create Blueprint for geocoding endpoints
geocode_blueprint = Blueprint('geocode', __name__)


@geocode_blueprint.route('/api/geocode/reverse', methods=['GET'])
def api_reverse_geocode():
    """
    API endpoint for reverse geocoding
    Converts coordinates to location name
    Usage: /api/geocode/reverse?lat=30.7333&lng=76.7794
    """
    try:
        lat = request.args.get('lat', type=float)
        lng = request.args.get('lng', type=float)
        
        if lat is None or lng is None:
            return jsonify({
                'success': False,
                'error': 'Missing lat or lng parameter'
            }), 400
        
        # Validate coordinates
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return jsonify({
                'success': False,
                'error': 'Invalid coordinates'
            }), 400
        
        # Perform reverse geocoding
        result = location_service.reverse_geocode(lat, lng)
        
        if not result['success']:
            # Return a fallback response instead of error
            return jsonify({
                'success': True,
                'display_name': 'Location detected',
                'full_address': f"{lat:.4f}, {lng:.4f}",
                'city': None,
                'state': None,
                'country': None,
                'address': {},
                'lat': lat,
                'lng': lng
            }), 200
        
        # Return successful result
        return jsonify({
            'success': True,
            'display_name': result.get('display_name', 'Unknown'),
            'full_address': result.get('full_address', ''),
            'city': result.get('address', {}).get('city'),
            'state': result.get('address', {}).get('state'),
            'country': result.get('address', {}).get('country'),
            'address': result.get('address', {}),
            'lat': lat,
            'lng': lng
        }), 200
        
    except Exception as e:
        print(f"❌ Reverse geocode API error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return fallback instead of error
        lat = request.args.get('lat', type=float)
        lng = request.args.get('lng', type=float)
        
        return jsonify({
            'success': True,
            'display_name': 'Location detected',
            'full_address': f"{lat:.4f}, {lng:.4f}" if lat and lng else 'Unknown',
            'lat': lat,
            'lng': lng
        }), 200


@geocode_blueprint.route('/api/geocode/forward', methods=['GET'])
def api_forward_geocode():
    """
    API endpoint for forward geocoding
    Converts location name to coordinates
    Usage: /api/geocode/forward?q=New York
    """
    try:
        query = request.args.get('q', type=str)
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Missing query parameter'
            }), 400
        
        # Perform geocoding
        result = location_service.geocode_location(query)
        
        if not result['success']:
            return jsonify(result), 404
        
        # Return successful result
        return jsonify({
            'success': True,
            'lat': result['lat'],
            'lon': result['lon'],
            'display_name': result['display_name'],
            'full_address': result['full_address'],
            'address': result.get('address', {})
        }), 200
        
    except Exception as e:
        print(f"❌ Forward geocode API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@geocode_blueprint.route('/api/geocode/search', methods=['GET'])
def api_search_locations():
    """
    API endpoint for location search/autocomplete
    Usage: /api/geocode/search?q=New&limit=5
    """
    try:
        query = request.args.get('q', type=str)
        limit = request.args.get('limit', default=5, type=int)
        
        if not query or len(query) < 2:
            return jsonify([]), 200
        
        # Use Nominatim search
        geolocator = Nominatim(user_agent="aqi_health_advisor")
        locations = geolocator.geocode(
            query,
            exactly_one=False,
            limit=limit,
            addressdetails=True,
            language='en'
        )
        
        if not locations:
            return jsonify([]), 200
        
        # Format results
        results = []
        for loc in locations:
            city_name = (
                loc.raw.get('address', {}).get('city') or
                loc.raw.get('address', {}).get('town') or
                loc.raw.get('address', {}).get('village') or
                loc.address.split(',')[0]
            )
            
            results.append({
                'display_name': city_name,
                'full_address': loc.address,
                'lat': loc.latitude,
                'lon': loc.longitude,
                'address': loc.raw.get('address', {})
            })
        
        return jsonify(results), 200
        
    except Exception as e:
        print(f"❌ Location search error: {str(e)}")
        return jsonify([]), 200  # Return empty array on error


# ========== EXPORT BLUEPRINT ==========
# To use in your main app:
# from locationService import geocode_blueprint
# app.register_blueprint(geocode_blueprint)