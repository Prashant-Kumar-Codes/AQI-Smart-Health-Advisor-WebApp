import os
import requests
from flask import session
from datetime import datetime
from app.db import get_db_cursor

# Gemini API Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyC8R96XiTZ1U90D5N-YztBh9VpZQbuWoNE')
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


def get_user_profile_from_login_data(user_id, db):
    """
    Retrieve user profile from login_data table
    
    Args:
        user_id: User ID from session
        db: Database connection
        
    Returns:
        dict: User profile data or None
    """
    try:
        cursor = get_db_cursor(db, dict_cursor=True)
        
        query = """
        SELECT username, email, age, gender, city
        FROM login_data
        WHERE id = %s AND is_verified = TRUE
        """
        
        cursor.execute(query, (user_id,))
        profile = cursor.fetchone()
        cursor.close()
        
        if profile:
            print(f"✅ Basic profile loaded: {profile.get('username')} (age: {profile.get('age')}, city: {profile.get('city')})")
        
        return profile
        
    except Exception as e:
        print(f"❌ Error fetching user profile: {e}")
        return None


def get_user_health_profile(email, db):
    """
    Retrieve user health profile from user_health_profile table
    Uses only fields that have data (NULL fields are ignored)
    
    Args:
        email: User email from login_data
        db: Database connection
        
    Returns:
        dict: Health profile data (only non-NULL fields) or None
    """
    try:
        cursor = get_db_cursor(db, dict_cursor=True)
        
        query = """
        SELECT 
            current_problems,
            chronic_conditions,
            physical_activity_level,
            pollution_sensitivity,
            respiratory_risk,
            immunity_level,
            daily_outdoor_hours,
            peak_exposure_time,
            smoking_level,
            mask_usage_level,
            additional_notes
        FROM user_health_profile
        WHERE email = %s
        """
        
        cursor.execute(query, (email,))
        health_profile = cursor.fetchone()
        cursor.close()
        
        if not health_profile:
            print(f"ℹ️ No health profile found for {email}")
            return None
        
        # Filter out NULL values - only keep fields that have data
        filtered_profile = {}
        for key, value in health_profile.items():
            if value is not None and value != '':
                filtered_profile[key] = value
        
        if filtered_profile:
            print(f"✅ Health profile loaded with {len(filtered_profile)} fields")
            print(f"   Available fields: {', '.join(filtered_profile.keys())}")
        else:
            print(f"ℹ️ Health profile exists but all fields are empty")
            return None
        
        return filtered_profile
        
    except Exception as e:
        print(f"❌ Error fetching health profile: {e}")
        return None


def build_user_context_string(login_profile, health_profile=None):
    """
    Build comprehensive context string from both profiles
    Only includes data that is present
    
    Args:
        login_profile: User profile from login_data
        health_profile: Health profile (filtered, only non-NULL fields)
        
    Returns:
        str: Formatted context string for AI
    """
    if not login_profile and not health_profile:
        return "General user (no profile data)"
    
    context_parts = []
    
    # ========== BASIC INFO FROM LOGIN_DATA ==========
    if login_profile:
        if login_profile.get('username'):
            context_parts.append(f"User: {login_profile['username']}")
        
        # Demographics with risk assessment
        if login_profile.get('age'):
            age = login_profile['age']
            context_parts.append(f"Age: {age} years")
            
            # Add age-based sensitivity notes
            if age < 5:
                context_parts.append("(Infant/Toddler - VERY HIGH sensitivity to pollution)")
            elif age < 18:
                context_parts.append("(Child/Teen - HIGH sensitivity, developing lungs)")
            elif age >= 60:
                context_parts.append("(Senior - INCREASED vulnerability)")
        
        if login_profile.get('gender'):
            context_parts.append(f"Gender: {login_profile['gender']}")
        
        if login_profile.get('city'):
            context_parts.append(f"Home City: {login_profile['city']}")
    
    # ========== HEALTH DATA FROM USER_HEALTH_PROFILE (IF AVAILABLE) ==========
    if health_profile:
        # Current health problems
        if health_profile.get('current_problems'):
            context_parts.append(f"Current Issues: {health_profile['current_problems']}")
        
        # Chronic conditions
        if health_profile.get('chronic_conditions'):
            context_parts.append(f"Chronic Conditions: {health_profile['chronic_conditions']}")
        
        # Activity level (1-10 scale)
        if health_profile.get('physical_activity_level'):
            level = health_profile['physical_activity_level']
            if level <= 3:
                context_parts.append(f"Activity Level: Low ({level}/10) - Mostly sedentary")
            elif level <= 6:
                context_parts.append(f"Activity Level: Moderate ({level}/10)")
            else:
                context_parts.append(f"Activity Level: High ({level}/10) - Very active")
        
        # Pollution sensitivity (1-10 scale)
        if health_profile.get('pollution_sensitivity'):
            sensitivity = health_profile['pollution_sensitivity']
            if sensitivity <= 3:
                context_parts.append(f"Pollution Sensitivity: Low ({sensitivity}/10)")
            elif sensitivity <= 6:
                context_parts.append(f"Pollution Sensitivity: Moderate ({sensitivity}/10)")
            else:
                context_parts.append(f"Pollution Sensitivity: HIGH ({sensitivity}/10) - Very sensitive")
        
        # Respiratory risk (1-10 scale)
        if health_profile.get('respiratory_risk'):
            risk = health_profile['respiratory_risk']
            if risk >= 7:
                context_parts.append(f"Respiratory Risk: HIGH ({risk}/10) - Significant vulnerability")
            else:
                context_parts.append(f"Respiratory Risk: {risk}/10")
        
        # Immunity level (1-10 scale)
        if health_profile.get('immunity_level'):
            immunity = health_profile['immunity_level']
            if immunity <= 4:
                context_parts.append(f"Immunity: Weak ({immunity}/10)")
            else:
                context_parts.append(f"Immunity: {immunity}/10")
        
        # Outdoor exposure
        if health_profile.get('daily_outdoor_hours'):
            hours = health_profile['daily_outdoor_hours']
            context_parts.append(f"Daily Outdoor Exposure: {hours} hours")
        
        # Peak exposure time
        if health_profile.get('peak_exposure_time'):
            context_parts.append(f"Typically outside during: {health_profile['peak_exposure_time']}")
        
        # Smoking (0-10 scale)
        if health_profile.get('smoking_level'):
            smoking = health_profile['smoking_level']
            if smoking == 0:
                context_parts.append("Non-smoker")
            elif smoking <= 3:
                context_parts.append(f"Light smoker ({smoking}/10)")
            elif smoking <= 6:
                context_parts.append(f"Moderate smoker ({smoking}/10)")
            else:
                context_parts.append(f"Heavy smoker ({smoking}/10) - HIGH RISK")
        
        # Mask usage (0-10 scale)
        if health_profile.get('mask_usage_level'):
            mask = health_profile['mask_usage_level']
            if mask == 0:
                context_parts.append("No mask usage")
            elif mask <= 4:
                context_parts.append(f"Limited mask use ({mask}/10)")
            else:
                context_parts.append(f"Good mask usage ({mask}/10)")
        
        # Additional notes
        if health_profile.get('additional_notes'):
            context_parts.append(f"Notes: {health_profile['additional_notes']}")
    
    return " | ".join(context_parts)


def generate_personalized_recommendation(aqi_value, aqi_category, location, login_profile=None,
                                        health_profile=None, pollutants=None, weather=None, 
                                        dominant_pollutant=None):
    """
    Generate personalized AI health recommendation using Gemini
    
    Args:
        aqi_value: Current AQI value
        aqi_category: AQI category (Good, Moderate, etc.)
        location: Location name
        login_profile: User profile from login_data
        health_profile: Health profile from user_health_profile (filtered)
        pollutants: Dictionary of pollutant concentrations
        weather: Weather data dictionary
        dominant_pollutant: Primary pollutant affecting AQI
        
    Returns:
        dict: Response with recommendation and metadata
    """
    try:
        has_profile = bool(login_profile or health_profile)
        print(f"🤖 Generating {'personalized' if has_profile else 'general'} recommendation...")
        
        # Build user context from BOTH profiles
        user_context = build_user_context_string(login_profile, health_profile)
        
        # Build pollutant information
        pollutant_info = ""
        if pollutants:
            pollutant_details = []
            if pollutants.get('pm25'):
                pollutant_details.append(f"PM2.5: {pollutants['pm25']:.1f} µg/m³")
            if pollutants.get('pm10'):
                pollutant_details.append(f"PM10: {pollutants['pm10']:.1f} µg/m³")
            if pollutants.get('o3'):
                pollutant_details.append(f"Ozone: {pollutants['o3']:.1f} µg/m³")
            if pollutants.get('no2'):
                pollutant_details.append(f"NO2: {pollutants['no2']:.1f} µg/m³")
            
            if pollutant_details:
                pollutant_info = f"\nKey Pollutants: {', '.join(pollutant_details)}"
        
        if dominant_pollutant:
            pollutant_info += f"\nDominant Pollutant: {dominant_pollutant.upper()}"
        
        # Build weather information
        weather_info = ""
        if weather:
            weather_details = []
            if weather.get('temperature'):
                weather_details.append(f"Temperature: {weather['temperature']:.1f}°C")
            if weather.get('humidity'):
                weather_details.append(f"Humidity: {weather['humidity']:.0f}%")
            if weather.get('wind_speed'):
                weather_details.append(f"Wind: {weather['wind_speed']:.1f} m/s")
            
            if weather_details:
                weather_info = f"\nWeather: {', '.join(weather_details)}"
        
        # Create comprehensive prompt for Gemini
        system_instruction = """You are an expert air quality health advisor with medical knowledge.

Provide personalized, actionable health recommendations in a clear, structured format.

FORMAT YOUR RESPONSE EXACTLY AS FOLLOWS:

**🌍 Current Situation** (2-3 sentences)
Brief assessment of air quality and immediate health implications for this location.

**⚠️ Your Risk Level** (2-3 sentences)  
Specific risks based on user's profile (age, health conditions, activity level, etc.). Be direct about vulnerability.

**💡 Recommended Actions** (4-7 bullet points)
• Use bullet points (•)
• Specific, actionable steps tailored to user's profile
• Mask recommendations (consider their current mask usage level if known)
• Indoor air quality tips
• Activity modifications based on their activity level
• Consider their outdoor exposure time if known

**🏥 Health Precautions** (2-3 sentences)
Medical advice, symptoms to watch for, when to seek help. Consider their health conditions if known.

IMPORTANT:
- If user has respiratory conditions or high sensitivity: be MORE cautious
- If user is a child/senior: emphasize age-specific risks
- If user is active outdoors: give specific exercise timing advice
- If user is a smoker: be MORE urgent about precautions
- KEEP IT: Concise (15-20 sentences total), practical, and personalized"""

        user_prompt = f"""📍 Location: {location}
🌡️ Current AQI: {aqi_value} ({aqi_category})
{pollutant_info}
{weather_info}

👤 User Profile: {user_context}

Provide personalized air quality health advice for this specific user. Consider ALL their profile details."""

        # Prepare Gemini API request
        headers = {
            'Content-Type': 'application/json'
        }
        
        payload = {
            "system_instruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [{
                "parts": [{"text": user_prompt}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1024
            }
        }
        
        # Make API request to Gemini
        print(f"📡 Calling Gemini API...")
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers=headers,
            json=payload,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if 'candidates' in result and len(result['candidates']) > 0:
                recommendation_text = result['candidates'][0]['content']['parts'][0]['text']
                
                print(f"✅ Gemini API response received ({len(recommendation_text)} chars)")
                
                return {
                    'success': True,
                    'recommendation': recommendation_text,
                    'personalized': has_profile,
                    'has_health_profile': bool(health_profile),
                    'source': 'gemini_api',
                    'timestamp': datetime.now().isoformat()
                }
            else:
                print("⚠️ Gemini API returned empty response")
                raise Exception("Empty API response")
        else:
            print(f"❌ Gemini API error: {response.status_code}")
            print(f"   Response: {response.text}")
            raise Exception(f"API error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Gemini API failed: {e}")
        print("   Falling back to template-based recommendations...")
        
        # Use fallback recommendations
        fallback_text = get_fallback_recommendation(
            aqi_value, 
            aqi_category, 
            login_profile, 
            health_profile
        )
        
        return {
            'success': True,
            'recommendation': fallback_text,
            'personalized': has_profile,
            'has_health_profile': bool(health_profile),
            'source': 'fallback',
            'timestamp': datetime.now().isoformat()
        }


def get_fallback_recommendation(aqi_value, aqi_category, login_profile=None, health_profile=None):
    """
    Provide fallback recommendation when Gemini API is unavailable
    Uses profile data if available
    
    Args:
        aqi_value: Current AQI value
        aqi_category: AQI category
        login_profile: User profile from login_data
        health_profile: Health profile from user_health_profile
        
    Returns:
        str: Formatted recommendation text
    """
    # Build personalization context
    age_warning = ""
    age_advice = ""
    health_advice = ""
    
    if login_profile and login_profile.get('age'):
        age = login_profile['age']
        name = login_profile.get('username', 'User')
        
        if age < 5:
            age_warning = f"\n\n⚠️ **Important for {name}**: Infants and toddlers are extremely sensitive to air pollution. Extra precautions are critical."
            age_advice = "\n• Keep infants indoors during poor air quality\n• Use air purifiers in nursery\n• Avoid stroller walks when AQI > 100"
        elif age < 18:
            age_warning = f"\n\n⚠️ **Important for {name}**: Children and teenagers have developing respiratory systems and are more vulnerable to air pollution."
            age_advice = "\n• Limit outdoor sports when AQI > 100\n• Ensure school has good ventilation\n• Monitor for coughing or breathing difficulties"
        elif age >= 60:
            age_warning = f"\n\n⚠️ **Important for {name}**: Seniors face higher risk from poor air quality due to potentially weakened immune systems."
            age_advice = "\n• Have emergency medications readily available\n• Monitor symptoms closely\n• Stay in contact with healthcare provider during high AQI days"
    
    # Add health-specific advice if health profile exists
    if health_profile:
        health_notes = []
        
        if health_profile.get('chronic_conditions'):
            health_notes.append(f"⚕️ With {health_profile['chronic_conditions']}, you're in a high-risk group")
        
        if health_profile.get('respiratory_risk') and health_profile['respiratory_risk'] >= 7:
            health_notes.append("🫁 Your high respiratory risk means extra caution is needed")
        
        if health_profile.get('smoking_level') and health_profile['smoking_level'] > 0:
            health_notes.append("🚬 Smoking combined with air pollution greatly increases health risks")
        
        if health_profile.get('pollution_sensitivity') and health_profile['pollution_sensitivity'] >= 7:
            health_notes.append("⚠️ Your high pollution sensitivity means you'll feel effects earlier than most")
        
        if health_notes:
            health_advice = "\n\n" + "\n".join(health_notes)
    
    # Location-specific note
    location_note = ""
    if login_profile and login_profile.get('city'):
        location_note = f"\n\n📍 As a resident of {login_profile['city']}, monitor local air quality trends regularly."
    
    # Category-based recommendations
    if aqi_value <= 50:
        return f"""**🌍 Current Situation**
Air quality is excellent (AQI: {aqi_value}). The air is clean and poses minimal health risk to everyone, including sensitive individuals.

**⚠️ Your Risk Level**
No risk for any age group or health condition. Perfect conditions for all activities.

**💡 Recommended Actions**
• Enjoy unlimited outdoor activities
• Great time for exercise, sports, and recreation
• Open windows for fresh air circulation
• No protective equipment needed

**🏥 Health Precautions**
This is ideal air quality. Make the most of this clean air day! No special health precautions needed.{age_warning}{health_advice}{location_note}"""

    elif aqi_value <= 100:
        return f"""**🌍 Current Situation**
Air quality is acceptable (AQI: {aqi_value}). Most people can engage in normal outdoor activities. Very sensitive individuals may experience slight discomfort.

**⚠️ Your Risk Level**
Low risk for general population. Unusually sensitive people or those with respiratory conditions should monitor for symptoms.

**💡 Recommended Actions**
• Continue normal outdoor activities
• Sensitive individuals: Watch for any unusual symptoms
• Keep windows open for ventilation
• No masks needed for most people{age_advice}

**🏥 Health Precautions**
Generally safe conditions. Seek medical attention if experiencing persistent respiratory discomfort.{age_warning}{health_advice}{location_note}"""

    elif aqi_value <= 150:
        return f"""**🌍 Current Situation**
Air quality is unhealthy for sensitive groups (AQI: {aqi_value}). Children, elderly, and people with respiratory/heart conditions should take precautions.

**⚠️ Your Risk Level**
Moderate to high risk for sensitive individuals including children, seniors, and those with health conditions. General population at lower risk.

**💡 Recommended Actions**
• Limit prolonged outdoor exertion
• Wear N95/KN95 masks if spending extended time outside
• Keep windows closed during peak pollution hours
• Use air purifiers indoors if available
• Consider rescheduling strenuous outdoor activities
• Stay hydrated{age_advice}

**🏥 Health Precautions**
Monitor for symptoms like coughing, throat irritation, or breathing difficulties. Seek medical care if symptoms persist or worsen.{age_warning}{health_advice}{location_note}"""

    elif aqi_value <= 200:
        return f"""**🌍 Current Situation**
Air quality is unhealthy (AQI: {aqi_value}). Everyone may begin experiencing health effects. Sensitive groups at serious risk.

**⚠️ Your Risk Level**
Significant risk for all age groups, especially children, seniors, and those with pre-existing conditions. Health impacts possible for general population.

**💡 Recommended Actions**
• Minimize ALL outdoor activities
• Wear N95/KN95 masks when outside is necessary
• Keep all windows and doors closed
• Run air purifiers continuously if available
• Postpone outdoor exercise and sports
• Stay well-hydrated
• Limit physical exertion even indoors{age_advice}

**🏥 Health Precautions**
Avoid unnecessary outdoor exposure. Seek immediate medical attention if experiencing chest pain, severe headaches, or respiratory distress. Have emergency contacts ready.{age_warning}{health_advice}{location_note}"""

    elif aqi_value <= 300:
        return f"""**🌍 Current Situation**
Air quality is very unhealthy (AQI: {aqi_value}). HEALTH ALERT - Everyone at risk of serious health effects. This is a public health concern.

**⚠️ Your Risk Level**
HIGH RISK for all individuals regardless of age or health status. Serious health impacts likely for sensitive groups.

**💡 Recommended Actions**
• Stay indoors at all times
• Wear N95/KN95 masks even for brief outdoor exposure
• Seal windows and doors completely
• Run air purifiers on maximum settings
• Avoid ANY physical exertion
• Keep emergency medications accessible
• Monitor air quality updates every hour
• Have emergency medical contacts ready{age_advice}

**🏥 Health Precautions**
THIS IS A HEALTH EMERGENCY. Seek IMMEDIATE medical care if experiencing: breathing difficulties, chest pain, severe headaches, dizziness, or confusion. Call emergency services if needed.{age_warning}{health_advice}{location_note}"""

    else:  # Hazardous (>300)
        return f"""**🌍 Current Situation**
🚨 HAZARDOUS AIR QUALITY EMERGENCY (AQI: {aqi_value}) 🚨
SEVERE HEALTH CRISIS. Everyone faces extremely serious health risks. This is a life-threatening situation.

**⚠️ Your Risk Level**
EXTREME DANGER for ALL age groups. Life-threatening conditions for everyone, especially vulnerable populations.

**💡 Recommended Actions**
• DO NOT go outside under ANY circumstances
• Seal all windows and doors with tape if possible
• Run multiple air purifiers continuously
• Wear N95/KN95 masks EVEN INDOORS if air quality is poor inside
• Have emergency medical contacts programmed in phone
• Follow official evacuation orders immediately if issued
• Keep first aid kit and medications accessible
• Stay tuned to emergency broadcasts
• DO NOT exercise or exert yourself AT ALL{age_advice}

**🏥 Health Precautions**
🚨 PUBLIC HEALTH CRISIS: Seek IMMEDIATE EMERGENCY MEDICAL ATTENTION for ANY respiratory symptoms, chest pain, confusion, or severe headaches. Call emergency services (ambulance) immediately. Follow local emergency guidelines. Consider evacuation if health deteriorates or if officially advised.{age_warning}{health_advice}{location_note}

**This is a medical emergency. Your life and health are at serious risk.**"""


# ============================================================================
# Flask Integration Function
# ============================================================================

def handle_personalized_recommendation_request(request_data, db_connection):
    """
    Handle Flask request for personalized recommendation
    Fetches BOTH login_data and user_health_profile (if available)
    
    Args:
        request_data: Request JSON data
        db_connection: PostgreSQL database connection
        
    Returns:
        tuple: (response_dict, status_code)
    """
    try:
        aqi_value = request_data.get('aqi', 0)
        aqi_category = request_data.get('category', 'Unknown')
        location = request_data.get('location', 'Unknown Location')
        pollutants = request_data.get('pollutants', {})
        weather = request_data.get('weather', {})
        dominant_pollutant = request_data.get('dominant_pollutant')
        
        # Get user profiles if logged in
        login_profile = None
        health_profile = None
        user_id = session.get('user_id')
        
        if user_id:
            print(f"👤 User ID {user_id} is logged in - fetching profiles...")
            
            # Get basic profile from login_data
            login_profile = get_user_profile_from_login_data(user_id, db_connection)
            
            if login_profile and login_profile.get('email'):
                # Get extended health profile if available
                health_profile = get_user_health_profile(login_profile['email'], db_connection)
            
            if not login_profile and not health_profile:
                print(f"⚠️ No profiles found for user ID: {user_id}")
        else:
            print("ℹ️ No user logged in - using general recommendations")
        
        # Generate personalized recommendation using BOTH profiles
        result = generate_personalized_recommendation(
            aqi_value=aqi_value,
            aqi_category=aqi_category,
            location=location,
            login_profile=login_profile,
            health_profile=health_profile,
            pollutants=pollutants,
            weather=weather,
            dominant_pollutant=dominant_pollutant
        )
        
        return result, 200
        
    except Exception as e:
        print(f"❌ Error generating recommendation: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'error': 'Failed to generate recommendation',
            'recommendation': 'Unable to generate personalized advice at this time. Please try again.',
            'personalized': False,
            'has_health_profile': False,
            'source': 'error',
            'timestamp': datetime.now().isoformat()
        }, 500