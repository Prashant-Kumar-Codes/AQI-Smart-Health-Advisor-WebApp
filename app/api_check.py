import requests

# API Configuration
API_KEY = "your_openweather_api_key_here"
LAT = 16.78  # Example: Talikota
LON = 76.31

def calculate_sub_index(cp, breakpoints):
    """Calculate AQI sub-index for a pollutant"""
    # Handle None or invalid values
    if cp is None or cp < 0:
        return None
    
    for bp in breakpoints:
        if bp["low"] <= cp <= bp["high"]:
            aqi = ((bp["Ihigh"] - bp["Ilow"]) / (bp["high"] - bp["low"])) * (cp - bp["low"]) + bp["Ilow"]
            return round(aqi, 2)
    
    # If value exceeds all breakpoints, return highest index
    if cp > breakpoints[-1]["high"]:
        return breakpoints[-1]["Ihigh"]
    
    return None

# Indian AQI Breakpoints (CPCB Standards)
PM25_BREAKPOINTS = [
    {"low": 0, "high": 30, "Ilow": 0, "Ihigh": 50},
    {"low": 31, "high": 60, "Ilow": 51, "Ihigh": 100},
    {"low": 61, "high": 90, "Ilow": 101, "Ihigh": 200},
    {"low": 91, "high": 120, "Ilow": 201, "Ihigh": 300},
    {"low": 121, "high": 250, "Ilow": 301, "Ihigh": 400},
    {"low": 251, "high": 380, "Ilow": 401, "Ihigh": 500},
]

PM10_BREAKPOINTS = [
    {"low": 0, "high": 50, "Ilow": 0, "Ihigh": 50},
    {"low": 51, "high": 100, "Ilow": 51, "Ihigh": 100},
    {"low": 101, "high": 250, "Ilow": 101, "Ihigh": 200},
    {"low": 251, "high": 350, "Ilow": 201, "Ihigh": 300},
    {"low": 351, "high": 430, "Ilow": 301, "Ihigh": 400},
    {"low": 431, "high": 500, "Ilow": 401, "Ihigh": 500},
]

NO2_BREAKPOINTS = [
    {"low": 0, "high": 40, "Ilow": 0, "Ihigh": 50},
    {"low": 41, "high": 80, "Ilow": 51, "Ihigh": 100},
    {"low": 81, "high": 180, "Ilow": 101, "Ihigh": 200},
    {"low": 181, "high": 280, "Ilow": 201, "Ihigh": 300},
    {"low": 281, "high": 400, "Ilow": 301, "Ihigh": 400},
    {"low": 401, "high": 500, "Ilow": 401, "Ihigh": 500},
]

SO2_BREAKPOINTS = [
    {"low": 0, "high": 40, "Ilow": 0, "Ihigh": 50},
    {"low": 41, "high": 80, "Ilow": 51, "Ihigh": 100},
    {"low": 81, "high": 380, "Ilow": 101, "Ihigh": 200},
    {"low": 381, "high": 800, "Ilow": 201, "Ihigh": 300},
    {"low": 801, "high": 1600, "Ilow": 301, "Ihigh": 400},
    {"low": 1601, "high": 2000, "Ilow": 401, "Ihigh": 500},
]

CO_BREAKPOINTS = [
    {"low": 0, "high": 1, "Ilow": 0, "Ihigh": 50},
    {"low": 1.1, "high": 2, "Ilow": 51, "Ihigh": 100},
    {"low": 2.1, "high": 10, "Ilow": 101, "Ihigh": 200},
    {"low": 10.1, "high": 17, "Ilow": 201, "Ihigh": 300},
    {"low": 17.1, "high": 34, "Ilow": 301, "Ihigh": 400},
    {"low": 34.1, "high": 50, "Ilow": 401, "Ihigh": 500},
]

O3_BREAKPOINTS = [
    {"low": 0, "high": 50, "Ilow": 0, "Ihigh": 50},
    {"low": 51, "high": 100, "Ilow": 51, "Ihigh": 100},
    {"low": 101, "high": 168, "Ilow": 101, "Ihigh": 200},
    {"low": 169, "high": 208, "Ilow": 201, "Ihigh": 300},
    {"low": 209, "high": 748, "Ilow": 301, "Ihigh": 400},
    {"low": 749, "high": 1000, "Ilow": 401, "Ihigh": 500},
]

def openweather_aqi_label(aqi):
    """Convert OpenWeather AQI number to label"""
    labels = {
        1: "Good",
        2: "Fair",
        3: "Moderate",
        4: "Poor",
        5: "Very Poor"
    }
    return labels.get(aqi, "Unknown")

def indian_aqi_category(aqi):
    """Get Indian AQI category"""
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

# =========================================
# WEATHER API
# =========================================
weather_url = "https://api.openweathermap.org/data/2.5/weather"
weather_params = {
    "lat": LAT,
    "lon": LON,
    "appid": API_KEY,
    "units": "metric"
}

try:
    weather_response = requests.get(weather_url, params=weather_params, timeout=10)
    weather_data = weather_response.json()
    
    print("\n================ WEATHER DATA ================")
    print(f"City: {weather_data.get('name', 'Unknown')}")
    print(f"Temperature: {weather_data['main']['temp']}°C")
    print(f"Humidity: {weather_data['main']['humidity']}%")
    print(f"Condition: {weather_data['weather'][0]['description']}")
except Exception as e:
    print(f"Weather API Error: {e}")

# =========================================
# AIR POLLUTION API
# =========================================
aqi_url = "https://api.openweathermap.org/data/2.5/air_pollution"
aqi_params = {
    "lat": LAT,
    "lon": LON,
    "appid": API_KEY
}

try:
    aqi_response = requests.get(aqi_url, params=aqi_params, timeout=10)
    aqi_data = aqi_response.json()
    
    pollution = aqi_data["list"][0]
    components = pollution["components"]
    openweather_aqi = pollution["main"]["aqi"]
    
    print("\n=============== AIR QUALITY DATA ===============")
    print(f"OpenWeather AQI: {openweather_aqi} - {openweather_aqi_label(openweather_aqi)}")
    print(f"PM2.5: {components['pm2_5']} µg/m³")
    print(f"PM10: {components['pm10']} µg/m³")
    print(f"CO: {components['co']} µg/m³")
    print(f"NO2: {components['no2']} µg/m³")
    print(f"SO2: {components['so2']} µg/m³")
    print(f"O3: {components['o3']} µg/m³")
    
    # =========================================
    # INDIAN AQI CALCULATION (FIXED)
    # =========================================
    pm25 = components["pm2_5"]
    pm10 = components["pm10"]
    no2 = components["no2"]
    so2 = components["so2"]
    co = components["co"] / 1000  # Convert µg/m³ to mg/m³
    o3 = components["o3"]
    
    # Calculate sub-indices
    pm25_index = calculate_sub_index(pm25, PM25_BREAKPOINTS)
    pm10_index = calculate_sub_index(pm10, PM10_BREAKPOINTS)
    no2_index = calculate_sub_index(no2, NO2_BREAKPOINTS)
    so2_index = calculate_sub_index(so2, SO2_BREAKPOINTS)
    co_index = calculate_sub_index(co, CO_BREAKPOINTS)
    o3_index = calculate_sub_index(o3, O3_BREAKPOINTS)
    
    # Filter out None values and get maximum
    indices = [idx for idx in [pm25_index, pm10_index, no2_index, so2_index, co_index, o3_index] if idx is not None]
    
    if indices:
        indian_aqi = int(max(indices))
        
        print("\n=============== INDIAN AQI (CPCB) ===============")
        print(f"PM2.5 Index: {pm25_index}")
        print(f"PM10 Index: {pm10_index}")
        print(f"NO2 Index: {no2_index}")
        print(f"SO2 Index: {so2_index}")
        print(f"CO Index: {co_index}")
        print(f"O3 Index: {o3_index}")
        print(f"\n🎯 Final AQI Value: {indian_aqi}")
        print(f"📊 Category: {indian_aqi_category(indian_aqi)}")
    else:
        print("\n⚠️ Could not calculate Indian AQI - insufficient data")
        
except Exception as e:
    print(f"Air Quality API Error: {e}")
    import traceback
    traceback.print_exc()