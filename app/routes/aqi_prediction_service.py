"""
AQI Prediction Service - Integrated with Flask App
===================================================
Multi-horizon prediction using 12 trained models.
Returns 24-hour data: 12 hours historical + 12 hours predicted.
"""

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
from typing import Dict, List, Optional
import os

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# OpenWeather API Configuration
API_KEY = os.getenv("OPENWEATHER_API_KEY", "6589ed49a6410165ea63662b113ed824")
API_HISTORICAL_URL = "http://api.openweathermap.org/data/2.5/air_pollution/history"

# Database Configuration
DB_CONFIG = {
    'host': os.getenv("POSTGRES_HOST", 'localhost'),
    'database': os.getenv("POSTGRES_DB", 'aqi_app_db'),
    'user': os.getenv("POSTGRES_USER", 'postgres'),
    'password': os.getenv("POSTGRES_PASSWORD", 'your_password_here'),
    'port': int(os.getenv("POSTGRES_PORT", 5432))
}

# Model Configuration - All 12 models
MODELS_DIR = os.getenv('MODELS_DIR', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models'))
FEATURE_NAMES_PATH = os.path.join(MODELS_DIR, 'feature_names.txt')

# ============================================================================
# GLOBAL MODEL CACHE
# ============================================================================

_MULTI_MODELS_CACHE = {}
_FEATURE_NAMES = None


def load_multi_horizon_models():
    """Load all 12 models into memory"""
    global _MULTI_MODELS_CACHE, _FEATURE_NAMES
    
    if not _MULTI_MODELS_CACHE:
        logger.info("🔄 Loading multi-horizon models into memory...")
        
        try:
            # Load each model (1h through 12h)
            for hours_ahead in range(1, 13):
                model_path = os.path.join(MODELS_DIR, f'aqi_rf_model_{hours_ahead}h.pkl')
                if os.path.exists(model_path):
                    model = joblib.load(model_path)
                    _MULTI_MODELS_CACHE[hours_ahead] = model
                    logger.info(f"  ✓ Loaded model for {hours_ahead}h ahead")
                else:
                    logger.warning(f"  ⚠️  Model not found: {model_path}")
            
            # Load feature names
            if os.path.exists(FEATURE_NAMES_PATH):
                with open(FEATURE_NAMES_PATH, 'r') as f:
                    _FEATURE_NAMES = [line.strip() for line in f]
                logger.info(f"✓ Loaded {len(_FEATURE_NAMES)} features")
            else:
                logger.error(f"Feature names file not found: {FEATURE_NAMES_PATH}")
                raise FileNotFoundError("Feature names file missing")
            
            logger.info(f"✅ All {len(_MULTI_MODELS_CACHE)} models loaded successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to load models: {e}")
            raise
    
    return _MULTI_MODELS_CACHE, _FEATURE_NAMES


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
    """Get AQI category"""
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
        if not connection:
            return pd.DataFrame()
            
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
                indian_aqi = EXCLUDED.indian_aqi
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
    
    logger.info(f"📡 Fetching API data from {start_time} to {end_time}")
    
    try:
        response = requests.get(API_HISTORICAL_URL, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            api_list = data.get('list', [])
            
            logger.info(f"✓ API returned {len(api_list)} records")
            
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
            logger.error(f"API error {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"API request failed: {e}")
        return []


# ============================================================================
# FEATURE ENGINEERING
# ============================================================================

def calculate_features_from_24h_data(df_24h: pd.DataFrame) -> pd.DataFrame:
    """Calculate ML features from 24 hours of data"""
    
    if len(df_24h) < 12:
        logger.warning(f"Only {len(df_24h)} hours available")
    
    df = df_24h.copy()
    df = df.sort_values('hour_timestamp').reset_index(drop=True)
    
    # Rename columns
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
    
    # Collect all new columns in a dictionary to avoid DataFrame fragmentation
    new_columns = {}
    
    # Lag features for pollutants
    for pollutant in pollutants:
        col_name = f'components.{pollutant}'
        for lag in lag_hours:
            new_columns[f'{pollutant}_lag_{lag}h'] = df[col_name].shift(lag)
    
    # Lag features for AQI
    for lag in lag_hours:
        new_columns[f'aqi_lag_{lag}h'] = df['indian_aqi'].shift(lag)
    
    # Rolling statistics
    rolling_windows = [3, 6, 12, 24]
    
    # Rolling statistics for pollutants
    for pollutant in pollutants:
        col_name = f'components.{pollutant}'
        for window in rolling_windows:
            new_columns[f'{pollutant}_rolling_mean_{window}h'] = df[col_name].rolling(window=window).mean()
            new_columns[f'{pollutant}_rolling_std_{window}h'] = df[col_name].rolling(window=window).std()
    
    # Rolling statistics for AQI
    for window in rolling_windows:
        new_columns[f'aqi_rolling_mean_{window}h'] = df['indian_aqi'].rolling(window=window).mean()
        new_columns[f'aqi_rolling_std_{window}h'] = df['indian_aqi'].rolling(window=window).std()
    
    # Rate of change for pollutants
    for pollutant in pollutants:
        col_name = f'components.{pollutant}'
        new_columns[f'{pollutant}_change_1h'] = df[col_name].diff(1)
        new_columns[f'{pollutant}_change_3h'] = df[col_name].diff(3)
    
    # Rate of change for AQI
    new_columns['aqi_change_1h'] = df['indian_aqi'].diff(1)
    new_columns['aqi_change_3h'] = df['indian_aqi'].diff(3)
    
    # Add all new columns at once using pd.concat to avoid fragmentation
    df = pd.concat([df, pd.DataFrame(new_columns, index=df.index)], axis=1)
    
    return df.iloc[[-1]]


# ============================================================================
# PREDICTION ENGINE
# ============================================================================

def predict_next_12_hours_multi_model(df_24h: pd.DataFrame) -> List[Dict]:
    """Predict next 12 hours using 12 separate models"""
    
    models, feature_names = load_multi_horizon_models()
    
    # Calculate features
    features_df = calculate_features_from_24h_data(df_24h)
    
    # Select features
    X = features_df[feature_names]
    X = X.bfill().ffill().fillna(0)
    
    predictions = []
    current_time = df_24h['hour_timestamp'].max()
    
    # Use each model
    for hours_ahead in range(1, 13):
        if hours_ahead in models:
            model = models[hours_ahead]
            predicted_aqi = model.predict(X)[0]
            prediction_time = current_time + timedelta(hours=hours_ahead)
            
            predictions.append({
                'hour': hours_ahead,
                'timestamp': prediction_time.strftime('%Y-%m-%d %H:%M:%S'),
                'aqi': round(predicted_aqi, 2),
                'category': get_aqi_category(predicted_aqi)
            })
    
    logger.info(f"✓ Generated {len(predictions)} hourly predictions")
    return predictions


# ============================================================================
# MAIN PREDICTION SERVICE
# ============================================================================

def get_aqi_prediction(latitude: float, longitude: float, location_name: str = None, current_aqi: float = None) -> Dict:
    """Main prediction service"""
    
    logger.info(f"🔍 Prediction request for ({latitude}, {longitude})")
    start_time = time.time()
    
    try:
        # Define time range
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        from_time = now - timedelta(hours=24)
        
        # Check database
        df_db = get_24h_data_from_db(latitude, longitude, from_time)
        
        # Find missing hours
        existing_hours = set(df_db['hour_timestamp']) if not df_db.empty else set()
        all_hours = [from_time + timedelta(hours=i) for i in range(25)]
        missing_hours = [h for h in all_hours if h not in existing_hours]
        
        # Fetch missing data
        if missing_hours:
            logger.info(f"📡 Fetching {len(missing_hours)} missing hours from API")
            api_start = min(missing_hours)
            api_end = max(missing_hours) + timedelta(hours=1)
            
            hourly_data = fetch_historical_data_from_api(latitude, longitude, api_start, api_end)
            
            if hourly_data:
                connection = get_db_connection()
                if connection:
                    store_hourly_data(connection, latitude, longitude, hourly_data)
                    connection.close()
                
                # Re-fetch
                df_db = get_24h_data_from_db(latitude, longitude, from_time)
        
        # Verify data
        if len(df_db) < 12:
            return {
                'success': False,
                'error': 'Insufficient data',
                'message': f'Only {len(df_db)} hours available'
            }
        
        # Predict
        predictions = predict_next_12_hours_multi_model(df_db)
        
        # Prepare response
        df_last_12h = df_db.tail(12).copy()
        
        historical_data = []
        for _, row in df_last_12h.iterrows():
            historical_data.append({
                'timestamp': row['hour_timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'aqi': round(row['indian_aqi'], 2) if row['indian_aqi'] else None,
                'category': get_aqi_category(row['indian_aqi']),
                'type': 'actual'
            })
        
        current = df_db.iloc[-1]
        processing_time = int((time.time() - start_time) * 1000)
        
        # Use passed current_aqi if available (from WAQI), otherwise use database value (from OpenWeather)
        if current_aqi is not None:
            logger.info(f"✓ Using provided current AQI: {current_aqi} (from WAQI)")
            current_aqi_value = current_aqi
        else:
            logger.info(f"✓ Using database current AQI: {current['indian_aqi']} (from OpenWeather)")
            current_aqi_value = current['indian_aqi']
        
        result = {
            'success': True,
            'location': {
                'name': location_name,
                'latitude': latitude,
                'longitude': longitude
            },
            'current': {
                'timestamp': current['hour_timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'aqi': round(current_aqi_value, 2) if current_aqi_value else None,
                'category': get_aqi_category(current_aqi_value)
            },
            'historical_data': historical_data,
            'forecast_data': predictions,
            'metadata': {
                'processing_time_ms': processing_time,
                'data_points_used': len(df_db)
            }
        }
        
        logger.info(f"✅ Prediction completed in {processing_time}ms")
        return result
        
    except Exception as e:
        logger.error(f"❌ Prediction error: {e}")
        return {
            'success': False,
            'error': str(e)
        }