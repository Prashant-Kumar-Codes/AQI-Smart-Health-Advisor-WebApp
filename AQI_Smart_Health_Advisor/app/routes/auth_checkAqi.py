from .extensions import *
from .locationService import location_service
import os
import requests

# Import the prediction service
from .aqi_prediction_service import get_aqi_prediction, load_multi_horizon_models

checkAqi_auth = Blueprint('checkAqi_auth', __name__)

# AQI API Configuration
WAQI_BASE_URL = 'https://api.waqi.info'
WAQI_API_TOKEN = os.getenv('WAQI_API_TOKEN', '46797eab2434e3cb85537e21e9a80bcb309220e3')

# OpenWeather API Configuration
OPENWEATHER_BASE_URL = 'https://api.openweathermap.org/data/2.5'
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '6589ed49a6410165ea63662b113ed824')

# Load ML models at startup
try:
    load_multi_horizon_models()
    print("✅ ML prediction models loaded successfully")
except Exception as e:
    print(f"⚠️ Warning: Could not load ML models: {e}")


def get_aqi_category(aqi):
    """Get AQI category based on value"""
    if aqi <= 50:
        return 'Good'
    elif aqi <= 100:
        return 'Moderate'
    elif aqi <= 150:
        return 'Unhealthy for Sensitive Groups'
    elif aqi <= 200:
        return 'Unhealthy'
    elif aqi <= 300:
        return 'Very Unhealthy'
    else:
        return 'Hazardous'


def fetch_weather_data(lat, lon):
    """Fetch weather data from OpenWeather API"""
    try:
        url = f"{OPENWEATHER_BASE_URL}/weather"
        params = {
            'lat': lat,
            'lon': lon,
            'appid': OPENWEATHER_API_KEY,
            'units': 'metric'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'temperature': data['main'].get('temp'),
                'humidity': data['main'].get('humidity'),
                'pressure': data['main'].get('pressure'),
                'wind_speed': data['wind'].get('speed'),
                'conditions': data['weather'][0].get('description') if data.get('weather') else None
            }
        else:
            print(f"⚠️ Weather API error: {response.status_code}")
            return {}
            
    except Exception as e:
        print(f"⚠️ Weather API exception: {e}")
        return {}


def parse_waqi_response(station_data):
    """Parse WAQI API response and extract relevant data"""
    try:
        iaqi = station_data.get('iaqi', {})
        
        pollutants = {}
        
        # Extract pollutant values
        if 'pm25' in iaqi:
            pollutants['pm25'] = iaqi['pm25'].get('v')
        if 'pm10' in iaqi:
            pollutants['pm10'] = iaqi['pm10'].get('v')
        if 'o3' in iaqi:
            pollutants['o3'] = iaqi['o3'].get('v')
        if 'no2' in iaqi:
            pollutants['no2'] = iaqi['no2'].get('v')
        if 'so2' in iaqi:
            pollutants['so2'] = iaqi['so2'].get('v')
        if 'co' in iaqi:
            pollutants['co'] = iaqi['co'].get('v')
        
        return pollutants
        
    except Exception as e:
        print(f"⚠️ Parse WAQI response error: {e}")
        return {}


@checkAqi_auth.route('/check_aqi')
def check_aqi():
    """Render the AQI monitoring page"""
    return render_template('auth/checkAqi.html')


@checkAqi_auth.route('/api/aqi/city/<city_name>', methods=['GET'])
def get_aqi_by_city(city_name):
    """Get AQI data using centralized location service"""
    try:
        print(f"\n{'='*60}")
        print(f"🔍 Fetching AQI for: {city_name}")
        print(f"{'='*60}")
        
        # ✅ Use centralized location service
        result = location_service.get_aqi_from_location_name(city_name)
        
        if not result['success']:
            print(f"❌ Failed to get AQI: {result['error']}")
            return jsonify({'error': result['error']}), 404
        
        location_data = result['location']
        aqi_data = result['aqi_data']
        
        # Get weather data
        weather_data = fetch_weather_data(location_data['lat'], location_data['lon'])
        
        # Parse pollutants from AQI data
        pollutants = {}
        if 'iaqi' in aqi_data:
            iaqi = aqi_data['iaqi']
            if 'pm25' in iaqi:
                pollutants['pm25'] = iaqi['pm25'].get('v')
            if 'pm10' in iaqi:
                pollutants['pm10'] = iaqi['pm10'].get('v')
            if 'o3' in iaqi:
                pollutants['o3'] = iaqi['o3'].get('v')
            if 'no2' in iaqi:
                pollutants['no2'] = iaqi['no2'].get('v')
            if 'so2' in iaqi:
                pollutants['so2'] = iaqi['so2'].get('v')
            if 'co' in iaqi:
                pollutants['co'] = iaqi['co'].get('v')
        
        aqi_category = get_aqi_category(aqi_data['aqi'])
        
        print(f"\n✅ Complete AQI Data Retrieved:")
        print(f"  📊 Location: {location_data['display_name']}")
        print(f"  📊 Coordinates: ({location_data['lat']:.4f}, {location_data['lon']:.4f})")
        print(f"  📊 AQI: {aqi_data['aqi']}")
        print(f"  📊 Category: {aqi_category}")
        
        # Return structured data
        return jsonify({
            'aqi': aqi_data['aqi'],
            'category': aqi_category,
            'city': {
                'name': aqi_data.get('station_name', location_data['display_name']),
                'geo': [location_data['lat'], location_data['lon']]
            },
            'iaqi': aqi_data.get('iaqi', {}),
            'pollutants': pollutants,
            'weather': weather_data,
            'time': aqi_data.get('time', {}),
            'dominentpol': aqi_data.get('dominentpol'),
            'query_location': city_name,
            'precise_location': location_data['full_address']
        }), 200
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@checkAqi_auth.route('/api/aqi/geo', methods=['GET'])
def get_aqi_by_geo():
    """Get AQI data using direct lat/lon (for current location feature)"""
    try:
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lng', type=float)
        
        if not lat or not lon:
            return jsonify({'error': 'Missing latitude or longitude'}), 400
        
        print(f"\n{'='*60}")
        print(f"🔍 Fetching AQI for coordinates:")
        print(f"  📍 Lat: {lat}, Lon: {lon}")
        print(f"{'='*60}")
        
        # ✅ Use centralized location service
        result = location_service.get_aqi_from_coordinates(lat, lon)
        
        if not result['success']:
            print(f"❌ Failed to get AQI: {result['error']}")
            return jsonify({'error': result['error']}), 404
        
        location_data = result['location']
        aqi_data = result['aqi_data']
        
        # Get weather data
        weather_data = fetch_weather_data(lat, lon)
        
        # Parse pollutants
        pollutants = {}
        if 'iaqi' in aqi_data:
            iaqi = aqi_data['iaqi']
            if 'pm25' in iaqi:
                pollutants['pm25'] = iaqi['pm25'].get('v')
            if 'pm10' in iaqi:
                pollutants['pm10'] = iaqi['pm10'].get('v')
            if 'o3' in iaqi:
                pollutants['o3'] = iaqi['o3'].get('v')
            if 'no2' in iaqi:
                pollutants['no2'] = iaqi['no2'].get('v')
            if 'so2' in iaqi:
                pollutants['so2'] = iaqi['so2'].get('v')
            if 'co' in iaqi:
                pollutants['co'] = iaqi['co'].get('v')
        
        aqi_category = get_aqi_category(aqi_data['aqi'])
        
        print(f"\n✅ AQI Data Retrieved:")
        print(f"  📊 Location: {location_data['display_name']}")
        print(f"  📊 AQI: {aqi_data['aqi']}")
        print(f"  📊 Category: {aqi_category}")
        
        return jsonify({
            'aqi': aqi_data['aqi'],
            'category': aqi_category,
            'city': {
                'name': location_data['display_name'],
                'geo': [lat, lon]
            },
            'iaqi': aqi_data.get('iaqi', {}),
            'pollutants': pollutants,
            'weather': weather_data,
            'time': aqi_data.get('time', {}),
            'dominentpol': aqi_data.get('dominentpol'),
            'precise_location': location_data['full_address']
        }), 200
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# NEW: ML PREDICTION ENDPOINTS
# ============================================================================

@checkAqi_auth.route('/api/aqi/predict/city/<city_name>', methods=['GET'])
def predict_aqi_by_city(city_name):
    """Get 24-hour AQI prediction for a city (12h historical + 12h forecast)"""
    try:
        print(f"\n{'='*60}")
        print(f"🤖 ML Prediction request for: {city_name}")
        print(f"{'='*60}")
        
        # Get optional current_aqi parameter from query string
        current_aqi = request.args.get('current_aqi', type=float)
        
        # Get coordinates from location service
        result = location_service.get_aqi_from_location_name(city_name)
        
        if not result['success']:
            return jsonify({'error': result['error']}), 404
        
        location_data = result['location']
        lat = location_data['lat']
        lon = location_data['lon']
        
        # Get prediction - pass current_aqi if provided
        prediction_result = get_aqi_prediction(lat, lon, location_data['display_name'], current_aqi)
        
        if not prediction_result['success']:
            return jsonify(prediction_result), 500
        
        print(f"✅ Prediction generated successfully")
        print(f"  📊 Historical data points: {len(prediction_result['historical_data'])}")
        print(f"  📊 Forecast data points: {len(prediction_result['forecast_data'])}")
        if current_aqi:
            print(f"  📊 Using WAQI current AQI: {current_aqi}")
        
        return jsonify(prediction_result), 200
        
    except Exception as e:
        print(f"❌ Prediction error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


@checkAqi_auth.route('/api/aqi/predict/geo', methods=['GET'])
def predict_aqi_by_geo():
    """Get 24-hour AQI prediction for coordinates"""
    try:
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lng', type=float)
        
        if not lat or not lon:
            return jsonify({'error': 'Missing latitude or longitude', 'success': False}), 400
        
        # Get optional current_aqi parameter from query string
        current_aqi = request.args.get('current_aqi', type=float)
        
        print(f"\n{'='*60}")
        print(f"🤖 ML Prediction request for: ({lat}, {lon})")
        print(f"{'='*60}")
        
        # Get location name
        result = location_service.get_aqi_from_coordinates(lat, lon)
        location_name = result.get('location', {}).get('display_name', 'Unknown Location')
        
        # Get prediction - pass current_aqi if provided
        prediction_result = get_aqi_prediction(lat, lon, location_name, current_aqi)
        
        if not prediction_result['success']:
            return jsonify(prediction_result), 500
        
        print(f"✅ Prediction generated successfully")
        if current_aqi:
            print(f"  📊 Using WAQI current AQI: {current_aqi}")
        
        return jsonify(prediction_result), 200
        
    except Exception as e:
        print(f"❌ Prediction error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


# ============================================================================
# EXISTING ENDPOINTS
# ============================================================================

@checkAqi_auth.route('/api/aqi/station/<uid>')
def get_aqi_by_station(uid):
    """Get specific station data"""
    try:
        url = f"{WAQI_BASE_URL}/feed/@{uid}/?token={WAQI_API_TOKEN}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('status') == 'ok':
            station_data = data['data']
            aqi_value = station_data.get('aqi')
            
            if aqi_value:
                station_data['category'] = get_aqi_category(int(aqi_value))
            
            return jsonify(station_data), 200
        
        return jsonify({'error': 'Station not available'}), 404
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'error': str(e)}), 500


@checkAqi_auth.route('/api/aqi/ai-recommendation', methods=['POST'])
def get_ai_recommendation():
    """Basic AI recommendation endpoint"""
    try:
        data = request.get_json()
        aqi = data.get('aqi', 0)
        
        recommendations = {
            'good': "Air quality is excellent! Perfect time for outdoor activities.",
            'moderate': "Air quality is acceptable for most people.",
            'unhealthy_sensitive': "Sensitive groups should limit outdoor exposure.",
            'unhealthy': "Everyone should reduce outdoor activities.",
            'very_unhealthy': "Everyone should avoid outdoor exposure.",
            'hazardous': "Health emergency - stay indoors!"
        }
        
        if aqi <= 50:
            severity = 'good'
        elif aqi <= 100:
            severity = 'moderate'
        elif aqi <= 150:
            severity = 'unhealthy_sensitive'
        elif aqi <= 200:
            severity = 'unhealthy'
        elif aqi <= 300:
            severity = 'very_unhealthy'
        else:
            severity = 'hazardous'
        
        return jsonify({
            'recommendation': recommendations[severity],
            'aqi': aqi,
            'severity': severity
        }), 200
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'error': 'Failed to generate recommendation'}), 500


@checkAqi_auth.route('/api/user/city')
def get_user_city():
    """Get user's city from session"""
    try:
        if 'user_id' in session:
            user_city = session.get('user_city')
            if user_city:
                return jsonify({'city': user_city}), 200
        
        return jsonify({'city': None}), 200
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'city': None}), 200