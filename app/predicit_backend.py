import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from app.db import get_db_connection
from datetime import datetime, timedelta
import time
import logging
import json
import numpy as np
import pandas as pd
import joblib
from typing import Dict, List, Optional, Tuple
from functools import lru_cache
import os

API_KEY = "your_api_key_here"
API_HISTORICAL_URL = "http://api.openweathermap.org/data/2.5/air_pollution/history"

# Base directory for the application
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# Model configuration
MODELS_DIR = os.path.join(APP_ROOT, 'models')
MODEL_PATH = os.path.join(MODELS_DIR, 'aqi_rf_model_1h.pkl')
FEATURE_NAMES_PATH = os.path.join(MODELS_DIR, 'feature_names.txt')


# Cache configuration
PREDICTION_CACHE_MINUTES = 10  # Cache predictions for 10 minutes

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# GLOBAL MODEL CACHE (Load once at startup)
# ============================================================================

_MODEL_CACHE = None
_FEATURE_NAMES = None

def load_model_to_memory():
    """Load ML model into memory once at startup"""
    global _MODEL_CACHE, _FEATURE_NAMES
    
    if _MODEL_CACHE is None:
        logger.info("Loading ML model into memory...")
        try:
            _MODEL_CACHE = joblib.load(MODEL_PATH)
            logger.info(f"✓ Model loaded successfully from {MODEL_PATH}")
            
            # Load feature names
            with open(FEATURE_NAMES_PATH, 'r') as f:
                _FEATURE_NAMES = [line.strip() for line in f]
            logger.info(f"✓ Loaded {len(_FEATURE_NAMES)} feature names")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    return _MODEL_CACHE, _FEATURE_NAMES


# ============================================================================
# INDIAN AQI CALCULATION
# ============================================================================

def convert_to_indian_aqi(pollutant_values: Dict[str, float]) -> Dict:
    """Convert pollutant concentrations to Indian CPCB AQI"""
    
    indian_breakpoints = {
        'pm25': [(0, 30, 0, 50), (31, 60, 51, 100), (61, 90, 101, 200),
                 (91, 120, 201, 300), (121, 250, 301, 400), (251, 380, 401, 500)],
        'pm10': [(0, 50, 0, 50), (51, 100, 51, 100), (101, 250, 101, 200),
                 (251, 350, 201, 300), (351, 430, 301, 400), (431, 550, 401, 500)],
        'no2': [(0, 40, 0, 50), (41, 80, 51, 100), (81, 180, 101, 200),
                (181, 280, 201, 300), (281, 400, 301, 400), (401, 550, 401, 500)],
        'so2': [(0, 40, 0, 50), (41, 80, 51, 100), (81, 380, 101, 200),
                (381, 800, 201, 300), (801, 1600, 301, 400), (1601, 2100, 401, 500)],
        'co': [(0, 1.0, 0, 50), (1.1, 2.0, 51, 100), (2.1, 10, 101, 200),
               (10.1, 17, 201, 300), (17.1, 34, 301, 400), (34.1, 46, 401, 500)],
        'o3': [(0, 50, 0, 50), (51, 100, 51, 100), (101, 168, 101, 200),
               (169, 208, 201, 300), (209, 748, 301, 400), (749, 1000, 401, 500)]
    }
    
    def calculate_sub_index(pollutant: str, concentration: float) -> Optional[int]:
        if pollutant not in indian_breakpoints or concentration is None:
            return None
        
        breakpoints = indian_breakpoints[pollutant]
        for bp_lo, bp_hi, aqi_lo, aqi_hi in breakpoints:
            if bp_lo <= concentration <= bp_hi:
                if (bp_hi - bp_lo) == 0:
                    return aqi_lo
                aqi = ((aqi_hi - aqi_lo) / (bp_hi - bp_lo)) * (concentration - bp_lo) + aqi_lo
                return round(aqi)
        
        if concentration > breakpoints[-1][1]:
            return 500
        elif concentration < breakpoints[0][0]:
            return 0
        return None
    
    sub_indices = {}
    
    for pollutant in ['pm25', 'pm10', 'no2', 'so2']:
        if pollutant in pollutant_values and pollutant_values[pollutant] is not None:
            sub_indices[pollutant] = calculate_sub_index(pollutant, pollutant_values[pollutant])
    
    # CO: Convert from µg/m³ to mg/m³
    if 'co' in pollutant_values and pollutant_values['co'] is not None:
        co_value = pollutant_values['co'] / 1000.0
        sub_indices['co'] = calculate_sub_index('co', co_value)
    
    if 'o3' in pollutant_values and pollutant_values['o3'] is not None:
        sub_indices['o3'] = calculate_sub_index('o3', pollutant_values['o3'])
    
    sub_indices = {k: v for k, v in sub_indices.items() if v is not None}
    
    if not sub_indices:
        return {'aqi': None, 'dominant_pollutant': None, 'sub_indices': {}}
    
    dominant_pollutant = max(sub_indices, key=sub_indices.get)
    overall_aqi = sub_indices[dominant_pollutant]
    
    return {
        'aqi': overall_aqi,
        'dominant_pollutant': dominant_pollutant,
        'sub_indices': sub_indices
    }


def get_aqi_category(aqi: float) -> str:
    """Get AQI category based on Indian standards"""
    if aqi is None:
        return "Unknown"
    if aqi <= 50:
        return "Good"
    elif aqi <= 100:
        return "Satisfactory"
    elif aqi <= 200:
        return "Moderate"
    elif aqi <= 300:
        return "Poor"
    elif aqi <= 400:
        return "Very Poor"
    else:
        return "Severe"


# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def get_db_connection_old():
    """Get database connection (legacy)"""
    from app.db import get_db_connection as connect
    return connect()


def get_24h_data_from_db(latitude: float, longitude: float, from_time: datetime) -> pd.DataFrame:
    """Get 24 hours of data from database"""
    try:
        connection = get_db_connection()
        from app.db import get_db_cursor
        cursor = get_db_cursor(connection, dict_cursor=True)
        
        query = """
            SELECT 
                hour_timestamp,
                pm2_5, pm10, no2, so2, co, o3,
                indian_aqi, dominant_pollutant
            FROM aqi_hourly_data
            WHERE latitude = %s 
              AND longitude = %s
              AND hour_timestamp >= %s
              AND hour_timestamp < %s + INTERVAL '24 hours'
            ORDER BY hour_timestamp ASC
        """
        
        cursor.execute(query, (latitude, longitude, from_time, from_time))
        data = cursor.fetchall()
        cursor.close()
        connection.close()
        
        if data:
            df = pd.DataFrame(data)
            df['hour_timestamp'] = pd.to_datetime(df['hour_timestamp'])
            return df
        return pd.DataFrame()
        
    except Exception as e:
        logger.error(f"Error fetching data from database: {e}")
        return pd.DataFrame()


def find_missing_hours(latitude: float, longitude: float, from_time: datetime, to_time: datetime) -> List[datetime]:
    """Find which hours are missing in the database"""
    try:
        connection = get_db_connection()
        from app.db import get_db_cursor
        cursor = get_db_cursor(connection, dict_cursor=True)
        
        query = """
            SELECT hour_timestamp 
            FROM aqi_hourly_data
            WHERE latitude = %s 
              AND longitude = %s
              AND hour_timestamp >= %s
              AND hour_timestamp < %s
            ORDER BY hour_timestamp ASC
        """
        
        cursor.execute(query, (latitude, longitude, from_time, to_time))
        existing_hours = {row['hour_timestamp'] for row in cursor.fetchall()}
        cursor.close()
        connection.close()
        
        # Generate all hours in range
        all_hours = []
        current = from_time
        while current < to_time:
            all_hours.append(current)
            current += timedelta(hours=1)
        
        # Find missing hours
        missing = [h for h in all_hours if h not in existing_hours]
        return missing
        
    except Exception as e:
        logger.error(f"Error finding missing hours: {e}")
        return []


def store_hourly_data(connection, latitude: float, longitude: float, hourly_records: List[Dict]):
    """Store hourly data in database"""
    try:
        cursor = connection.cursor()
        
        insert_query = """
            INSERT INTO aqi_hourly_data (
                latitude, longitude, location_name,
                hour_timestamp, unix_timestamp,
                pm2_5, pm10, no2, so2, co, o3, no, nh3,
                indian_aqi, dominant_pollutant, aqi_category,
                sub_index_pm25, sub_index_pm10, sub_index_no2,
                sub_index_so2, sub_index_co, sub_index_o3,
                data_source
            ) VALUES (
                %(latitude)s, %(longitude)s, %(location_name)s,
                %(hour_timestamp)s, %(unix_timestamp)s,
                %(pm2_5)s, %(pm10)s, %(no2)s, %(so2)s, %(co)s, %(o3)s, %(no)s, %(nh3)s,
                %(indian_aqi)s, %(dominant_pollutant)s, %(aqi_category)s,
                %(sub_index_pm25)s, %(sub_index_pm10)s, %(sub_index_no2)s,
                %(sub_index_so2)s, %(sub_index_co)s, %(sub_index_o3)s,
                'api'
            )
            ON CONFLICT (latitude, longitude, hour_timestamp) DO UPDATE SET
                pm2_5 = EXCLUDED.pm2_5,
                pm10 = EXCLUDED.pm10,
                no2 = EXCLUDED.no2,
                so2 = EXCLUDED.so2,
                co = EXCLUDED.co,
                o3 = EXCLUDED.o3,
                indian_aqi = EXCLUDED.indian_aqi,
                dominant_pollutant = EXCLUDED.dominant_pollutant
        """
        
        cursor.executemany(insert_query, hourly_records)
        connection.commit()
        cursor.close()
        
        logger.info(f"✓ Stored {len(hourly_records)} hourly records")
        return True
        
    except Exception as e:
        logger.error(f"Error storing data: {e}")
        connection.rollback()
        return False


# ============================================================================
# API FUNCTIONS
# ============================================================================

def fetch_historical_data_from_api(latitude: float, longitude: float, start_time: datetime, end_time: datetime) -> List[Dict]:
    """Fetch historical data from OpenWeatherMap API"""
    
    start_unix = int(start_time.timestamp())
    end_unix = int(end_time.timestamp())
    
    params = {
        'lat': latitude,
        'lon': longitude,
        'start': start_unix,
        'end': end_unix,
        'appid': API_KEY
    }
    
    logger.info(f"Fetching API data from {start_time} to {end_time}")
    start_req = time.time()
    
    try:
        response = requests.get(API_HISTORICAL_URL, params=params, timeout=15)
        response_time_ms = int((time.time() - start_req) * 1000)
        
        if response.status_code == 200:
            data = response.json()
            api_list = data.get('list', [])
            
            logger.info(f"✓ API returned {len(api_list)} records in {response_time_ms}ms")
            
            # Process each record
            hourly_records = []
            for record in api_list:
                components = record.get('components', {})
                dt = record.get('dt')
                
                pollutant_values = {
                    'pm25': components.get('pm2_5'),
                    'pm10': components.get('pm10'),
                    'no2': components.get('no2'),
                    'so2': components.get('so2'),
                    'co': components.get('co'),
                    'o3': components.get('o3')
                }
                
                aqi_data = convert_to_indian_aqi(pollutant_values)
                
                hourly_records.append({
                    'latitude': latitude,
                    'longitude': longitude,
                    'location_name': None,
                    'hour_timestamp': datetime.fromtimestamp(dt).replace(minute=0, second=0, microsecond=0),
                    'unix_timestamp': dt,
                    'pm2_5': components.get('pm2_5'),
                    'pm10': components.get('pm10'),
                    'no2': components.get('no2'),
                    'so2': components.get('so2'),
                    'co': components.get('co'),
                    'o3': components.get('o3'),
                    'no': components.get('no'),
                    'nh3': components.get('nh3'),
                    'indian_aqi': aqi_data['aqi'],
                    'dominant_pollutant': aqi_data['dominant_pollutant'],
                    'aqi_category': get_aqi_category(aqi_data['aqi']),
                    'sub_index_pm25': aqi_data['sub_indices'].get('pm25'),
                    'sub_index_pm10': aqi_data['sub_indices'].get('pm10'),
                    'sub_index_no2': aqi_data['sub_indices'].get('no2'),
                    'sub_index_so2': aqi_data['sub_indices'].get('so2'),
                    'sub_index_co': aqi_data['sub_indices'].get('co'),
                    'sub_index_o3': aqi_data['sub_indices'].get('o3')
                })
            
            return hourly_records
            
        else:
            logger.error(f"API error {response.status_code}: {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"API request failed: {e}")
        return []


# ============================================================================
# FEATURE ENGINEERING
# ============================================================================

def calculate_features_from_24h_data(df_24h: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate ML features from 24 hours of data
    Returns a single row with all features for the latest timestamp
    """
    
    if len(df_24h) < 24:
        logger.warning(f"Only {len(df_24h)} hours available, need 24 for accurate features")
    
    df = df_24h.copy()
    df = df.sort_values('hour_timestamp').reset_index(drop=True)
    
    # Rename columns to match training data
    df = df.rename(columns={
        'pm2_5': 'components.pm2_5',
        'pm10': 'components.pm10',
        'no2': 'components.no2',
        'so2': 'components.so2',
        'co': 'components.co',
        'o3': 'components.o3'
    })
    
    # Temporal features
    df['datetime'] = df['hour_timestamp']
    df['hour'] = df['datetime'].dt.hour
    df['day_of_week'] = df['datetime'].dt.dayofweek
    df['day_of_month'] = df['datetime'].dt.day
    df['month'] = df['datetime'].dt.month
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    
    # Cyclical encoding
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
    
    # Lag features
    lag_hours = [1, 2, 3, 6, 12, 24]
    pollutants = ['pm2_5', 'pm10', 'no2', 'so2', 'co', 'o3']
    
    for pollutant in pollutants:
        col_name = f'components.{pollutant}'
        for lag in lag_hours:
            df[f'{pollutant}_lag_{lag}h'] = df[col_name].shift(lag)
    
    for lag in lag_hours:
        df[f'aqi_lag_{lag}h'] = df['indian_aqi'].shift(lag)
    
    # Rolling statistics
    rolling_windows = [3, 6, 12, 24]
    
    for pollutant in pollutants:
        col_name = f'components.{pollutant}'
        for window in rolling_windows:
            df[f'{pollutant}_rolling_mean_{window}h'] = df[col_name].rolling(window=window).mean()
            df[f'{pollutant}_rolling_std_{window}h'] = df[col_name].rolling(window=window).std()
    
    for window in rolling_windows:
        df[f'aqi_rolling_mean_{window}h'] = df['indian_aqi'].rolling(window=window).mean()
        df[f'aqi_rolling_std_{window}h'] = df['indian_aqi'].rolling(window=window).std()
    
    # Rate of change
    for pollutant in pollutants:
        col_name = f'components.{pollutant}'
        df[f'{pollutant}_change_1h'] = df[col_name].diff(1)
        df[f'{pollutant}_change_3h'] = df[col_name].diff(3)
    
    df['aqi_change_1h'] = df['indian_aqi'].diff(1)
    df['aqi_change_3h'] = df['indian_aqi'].diff(3)
    
    # Return only the last row (most recent with all features)
    return df.iloc[[-1]]


# ============================================================================
# PREDICTION ENGINE
# ============================================================================

def predict_next_12_hours(df_24h: pd.DataFrame, model, feature_names: List[str]) -> List[Dict]:
    """
    Predict AQI for next 12 hours hourly
    
    NOTE: This uses iterative prediction since the model was trained for 12h ahead.
    For better accuracy, train separate models for each hour (1h, 2h, 3h... 12h ahead)
    """
    
    predictions = []
    current_data = df_24h.copy()
    
    current_time = current_data['hour_timestamp'].max()
    
    for hour_ahead in range(1, 13):
        # Calculate features from current data
        features_df = calculate_features_from_24h_data(current_data)
        
        # Select features in correct order
        X = features_df[feature_names]
        
        # Handle any missing features
        X = X.fillna(method='bfill').fillna(method='ffill').fillna(0)
        
        # Predict
        predicted_aqi = model.predict(X)[0]
        prediction_time = current_time + timedelta(hours=hour_ahead)
        
        predictions.append({
            'hour': hour_ahead,
            'timestamp': prediction_time.strftime('%Y-%m-%d %H:%M:%S'),
            'aqi': round(predicted_aqi, 2),
            'category': get_aqi_category(predicted_aqi)
        })
        
        # Add prediction to data for next iteration (iterative forecasting)
        # This is a simplified approach - assumes pollutants stay similar
        last_row = current_data.iloc[-1].copy()
        new_row = {
            'hour_timestamp': prediction_time,
            'pm2_5': last_row['pm2_5'],  # Simplified: use last known values
            'pm10': last_row['pm10'],
            'no2': last_row['no2'],
            'so2': last_row['so2'],
            'co': last_row['co'],
            'o3': last_row['o3'],
            'indian_aqi': predicted_aqi,
            'dominant_pollutant': last_row['dominant_pollutant']
        }
        
        current_data = pd.concat([current_data, pd.DataFrame([new_row])], ignore_index=True)
        
        # Keep only last 24 rows
        if len(current_data) > 24:
            current_data = current_data.iloc[-24:]
    
    logger.info(f"✓ Generated 12 hourly predictions")
    return predictions


# ============================================================================
# MAIN SERVICE FUNCTION
# ============================================================================

def get_aqi_prediction(latitude: float, longitude: float, location_name: str = None) -> Dict:
    """
    Main function: Get AQI prediction for a location
    
    Returns dictionary with:
    - last_12h_actual: List of actual AQI data
    - next_12h_predicted: List of predicted AQI data
    - current_aqi: Current AQI value
    - metadata: Timestamps, location info, etc.
    """
    
    logger.info(f"=== AQI Prediction Request for ({latitude}, {longitude}) ===")
    
    start_time = time.time()
    
    try:
        # Load model (cached in memory)
        model, feature_names = load_model_to_memory()
        
        # Define time range: 24 hours ago to now
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        from_time = now - timedelta(hours=24)
        
        # Step 1: Check database for existing data
        logger.info("Step 1: Checking database for cached data...")
        df_db = get_24h_data_from_db(latitude, longitude, from_time)
        
        # Step 2: Find missing hours
        missing_hours = find_missing_hours(latitude, longitude, from_time, now + timedelta(hours=1))
        
        if missing_hours:
            logger.info(f"Step 2: Found {len(missing_hours)} missing hours, fetching from API...")
            
            # Fetch missing data from API
            # API works best with continuous ranges, so fetch in chunks
            if missing_hours:
                api_start = min(missing_hours)
                api_end = max(missing_hours) + timedelta(hours=1)
                
                hourly_data = fetch_historical_data_from_api(latitude, longitude, api_start, api_end)
                
                if hourly_data:
                    # Store in database
                    connection = get_db_connection()
                    store_hourly_data(connection, latitude, longitude, hourly_data)
                    connection.close()
                    
                    # Re-fetch from database to get complete 24h data
                    df_db = get_24h_data_from_db(latitude, longitude, from_time)
        else:
            logger.info("Step 2: All data available in cache, no API call needed")
        
        # Step 3: Verify we have enough data
        if len(df_db) < 12:
            return {
                'error': 'Insufficient data',
                'message': f'Only {len(df_db)} hours of data available, need at least 12',
                'success': False
            }
        
        logger.info(f"Step 3: Have {len(df_db)} hours of data")
        
        # Step 4: Predict next 12 hours
        logger.info("Step 4: Predicting next 12 hours...")
        predictions = predict_next_12_hours(df_db, model, feature_names)
        
        # Step 5: Prepare response
        logger.info("Step 5: Preparing response...")
        
        # Get last 12 hours of actual data
        df_last_12h = df_db.tail(12).copy()
        
        historical_data = []
        for _, row in df_last_12h.iterrows():
            historical_data.append({
                'timestamp': row['hour_timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'aqi': round(row['indian_aqi'], 2) if row['indian_aqi'] else None,
                'category': get_aqi_category(row['indian_aqi']),
                'dominant_pollutant': row['dominant_pollutant'],
                'pm2_5': round(row['pm2_5'], 2) if row['pm2_5'] else None,
                'pm10': round(row['pm10'], 2) if row['pm10'] else None,
                'type': 'actual'
            })
        
        # Current AQI (latest data point)
        current = df_db.iloc[-1]
        
        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        result = {
            'success': True,
            'location': {
                'name': location_name,
                'latitude': latitude,
                'longitude': longitude
            },
            'current': {
                'timestamp': current['hour_timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'aqi': round(current['indian_aqi'], 2) if current['indian_aqi'] else None,
                'category': get_aqi_category(current['indian_aqi']),
                'dominant_pollutant': current['dominant_pollutant']
            },
            'historical_data': historical_data,  # Last 12 hours actual
            'forecast_data': predictions,  # Next 12 hours predicted
            'metadata': {
                'data_points_used': len(df_db),
                'api_calls_made': len(missing_hours) > 0,
                'processing_time_ms': processing_time_ms,
                'model_version': '1.0',
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        }
        
        logger.info(f"✓ Prediction completed in {processing_time_ms}ms")
        return result
        
    except Exception as e:
        logger.error(f"Error in prediction service: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'message': 'Failed to generate prediction'
        }


# ============================================================================
# FLASK API ENDPOINT (Optional - can use FastAPI instead)
# ============================================================================

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

@app.route('/api/predict', methods=['GET'])
def predict_endpoint():
    """
    API endpoint: GET /api/predict?lat=30.727987&lon=76.693266&location=Chandigarh
    """
    try:
        latitude = float(request.args.get('lat'))
        longitude = float(request.args.get('lon'))
        location_name = request.args.get('location', None)
        
        result = get_aqi_prediction(latitude, longitude, location_name)
        return jsonify(result)
        
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Invalid coordinates',
            'message': 'Latitude and longitude must be valid numbers'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Internal server error'
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'model_loaded': _MODEL_CACHE is not None,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })


# ============================================================================
# STARTUP
# ============================================================================

if __name__ == '__main__':
    # Load model into memory at startup
    logger.info("=" * 70)
    logger.info("AQI Prediction Service Starting...")
    logger.info("=" * 70)
    
    load_model_to_memory()
    
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=5222, debug=False)