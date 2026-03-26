import requests
import pandas as pd


# # ================= CONFIG =================
API_KEY = "6589ed49a6410165ea63662b113ed824"  # Do not hardcode in production

HISTORICAL_DATA_URL = "http://api.openweathermap.org/data/2.5/air_pollution/history"



LAT = 16.454572
LON = 76.262705

# LAT = 28.6139                  # Delhi
# LON = 77.2090

START = 1479801810
END = 1611510610

params = {
    "lat": LAT,
    "lon": LON,
    "start": START,
    "end": END,
    "appid": API_KEY
}

response = requests.get(HISTORICAL_DATA_URL, params=params)

if response.status_code == 200:
    data = response.json()

    # ✅ Extract AQI list
    aqi_list = data.get("list", [])

    # ✅ Convert to DataFrame
    df = pd.json_normalize(aqi_list)

    # # ✅ Save correctly
    # output_path = r"D:\Codes\Projects\AQI_SMART_HEALTH_ADVISOR\historical_data.json"
    # df.to_json(output_path, orient="records", indent=2)

    print("AQI historical data saved successfully.")
    print(df)
else:
    print("API Error:", response.status_code, response.text)


# weather_url = "https://api.openweathermap.org/data/2.5/weather"
# weather_params = {
#     "lat": LAT,
#     "lon": LON,
#     "appid": API_KEY,
#     "units": "metric"
# }

# weather_response = requests.get(weather_url, params=weather_params)
# weather_data = weather_response.json()


# def calculate_sub_index(cp, breakpoints):
#     for bp in breakpoints:
#         if bp["low"] <= cp <= bp["high"]:
#             return ((bp["Ihigh"] - bp["Ilow"]) / (bp["high"] - bp["low"])) * (cp - bp["low"]) + bp["Ilow"]
#     return None


# PM25_BREAKPOINTS = [
#     {"low": 0, "high": 30, "Ilow": 0, "Ihigh": 50},
#     {"low": 31, "high": 60, "Ilow": 51, "Ihigh": 100},
#     {"low": 61, "high": 90, "Ilow": 101, "Ihigh": 200},
#     {"low": 91, "high": 120, "Ilow": 201, "Ihigh": 300},
#     {"low": 121, "high": 250, "Ilow": 301, "Ihigh": 400},
#     {"low": 251, "high": 500, "Ilow": 401, "Ihigh": 500},
#     {"low": 501, "high": 9999, "Ilow": 501, "Ihigh": 500},
# ]

# PM10_BREAKPOINTS = [
#     {"low": 0, "high": 50, "Ilow": 0, "Ihigh": 50},
#     {"low": 51, "high": 100, "Ilow": 51, "Ihigh": 100},
#     {"low": 101, "high": 250, "Ilow": 101, "Ihigh": 200},
#     {"low": 251, "high": 350, "Ilow": 201, "Ihigh": 300},
#     {"low": 351, "high": 430, "Ilow": 301, "Ihigh": 400},
#     {"low": 431, "high": 600, "Ilow": 401, "Ihigh": 500},
#     {"low": 601, "high": 9999, "Ilow": 501, "Ihigh": 500},
# ]


# def openweather_aqi_label(aqi):
#     labels = {
#         1: "Good",
#         2: "Fair",
#         3: "Moderate",
#         4: "Poor",
#         5: "Very Poor"
#     }
#     return labels.get(aqi, "Unknown")


# def indian_aqi_category(aqi):
#     if aqi <= 50:
#         return "Good"
#     elif aqi <= 100:
#         return "Satisfactory"
#     elif aqi <= 200:
#         return "Moderate"
#     elif aqi <= 300:
#         return "Poor"
#     elif aqi <= 400:
#         return "Very Poor"
#     else:
#         return "Severe"


# # =========================================
# # WEATHER API
# # =========================================

# weather_url = "https://api.openweathermap.org/data/2.5/weather"
# weather_params = {
#     "lat": LAT,
#     "lon": LON,
#     "appid": API_KEY,
#     "units": "metric"
# }

# weather_response = requests.get(weather_url, params=weather_params)
# weather_data = weather_response.json()

# print("\n================ WEATHER DATA ================")
# print("City:", weather_data.get("name"))
# print("Temperature:", weather_data["main"]["temp"], "°C")
# print("Humidity:", weather_data["main"]["humidity"], "%")
# print("Condition:", weather_data["weather"][0]["description"])


# # =========================================
# # AIR POLLUTION API
# # =========================================

# aqi_url = "https://api.openweathermap.org/data/2.5/air_pollution"
# aqi_params = {
#     "lat": LAT,
#     "lon": LON,
#     "appid": API_KEY
# }

# aqi_response = requests.get(aqi_url, params=aqi_params)
# aqi_data = aqi_response.json()

# pollution = aqi_data["list"][0]
# components = pollution["components"]

# openweather_aqi = pollution["main"]["aqi"]

# print("\n=============== AIR QUALITY DATA ===============")
# print("OpenWeather AQI:", openweather_aqi, "-", openweather_aqi_label(openweather_aqi))
# print("PM2.5:", components["pm2_5"], "µg/m³")
# print("PM10:", components["pm10"], "µg/m³")
# print("CO:", components["co"], "µg/m³")
# print("NO2:", components["no2"], "µg/m³")
# print("SO2:", components["so2"], "µg/m³")
# print("O3:", components["o3"], "µg/m³")


# # =========================================
# # INDIAN AQI CALCULATION
# # =========================================

# pm25 = components["pm2_5"]
# pm10 = components["pm10"]

# pm25_index = calculate_sub_index(pm25, PM25_BREAKPOINTS)
# pm10_index = calculate_sub_index(pm10, PM10_BREAKPOINTS)

# indian_aqi = int(max(pm25_index, pm10_index))

# print("\n=============== INDIAN AQI (CPCB) ===============")
# print("AQI Value:", indian_aqi)
# print("Category:", indian_aqi_category(indian_aqi))
