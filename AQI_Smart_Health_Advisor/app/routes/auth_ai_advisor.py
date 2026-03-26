from .extensions import *
import json
import requests
from .locationService import location_service
import psycopg2
from app.db import get_db_connection

ai_advisor_auth = Blueprint('ai_advisor_auth', __name__)

# Gemini API Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyC8R96XiTZ1U90D5N-YztBh9VpZQbuWoNE')
#GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# Initialize Gemini client
gemini_available = True
try:
    # Test if requests is available
    import requests
    print("✅ Gemini API initialized successfully")
except ImportError:
    print("⚠️ Warning: requests package not installed. Install it with: pip install requests")
    gemini_available = False
except Exception as e:
    print(f"⚠️ Warning: Gemini client initialization failed: {e}")
    gemini_available = False


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


@ai_advisor_auth.route('/ai_advisor', methods=['GET'])
def ai_advisor():
    """AI Advisor page route - No login required to view page"""
    return render_template('auth/ai_advisor.html')


@ai_advisor_auth.route('/api/aqi/ai-personalized-advice', methods=['POST'])
def get_ai_personalized_advice():
    """Get personalized AI advice using Gemini - Login required"""
    try:
        # CHECK IF USER IS LOGGED IN
        if 'user_id' not in session:
            print("⚠️ User not logged in - returning 401")
            return jsonify({
                'error': 'Please log in to access AI Advisor',
                'redirect': '/login'
            }), 401
        
        data = request.get_json()
                
        print("=" * 60)
        print("🔥 Received AI advice request")
        print("=" * 60)
        print("Request data:", json.dumps(data, indent=2))
        
        # Extract all data from request
        aqi = data.get('aqi', 0)
        aqi_category = data.get('aqi_category', 'Unknown')
        pollutants = data.get('pollutants', {})
        dominant_pollutant = data.get('dominant_pollutant')
        weather = data.get('weather', {})
        city_name = data.get('city_name', 'Unknown')
        location = data.get('location', 'unknown location')
        
        # ✅ VERIFY LOCATION USING CENTRALIZED SERVICE
        print("\n🔍 Verifying location with centralized service...")
        location_data = location_service.geocode_location(city_name)
        
        if not location_data['success']:
            print(f"❌ Location verification failed: {location_data['error']}")
            return jsonify({'error': location_data['error']}), 400
        
        verified_city = location_data['display_name']
        verified_lat = location_data['lat']
        verified_lon = location_data['lon']
        
        print(f"✅ Location verified: {verified_city} ({verified_lat:.4f}, {verified_lon:.4f})")
        
        # User profile data
        age = data.get('age')
        age_group = data.get('age_group')
        gender = data.get('gender')
        time_outside = data.get('time_outside')
        conditions = data.get('conditions', [])
        question = data.get('question', '')
        
        print(f"📊 AQI: {aqi}, Category: {aqi_category}, Location: {verified_city}")
        print(f"👤 User: Age={age}, AgeGroup={age_group}, Gender={gender}")
        print(f"⏰ Time outside: {time_outside}")
        print(f"🏥 Conditions: {conditions}")
        print(f"❓ Question: {question}")
        
        # Build comprehensive prompt for AI
        system_instruction = """You are an expert air quality health advisor with deep knowledge of environmental health, respiratory medicine, and pollution science. 

Your role is to provide clear, actionable, and personalized health advice based on current air quality conditions. 

CRITICAL INSTRUCTION: When users mention they MUST work outside or HAVE TO be outside, provide PRACTICAL protective measures for working outdoors, NOT advice to stay indoors. Focus on HOW to protect themselves while working outside.

RESPONSE FORMAT:
Structure your response in numbered sections with clear headers:

1. **Current Air Quality Assessment**
Brief analysis of the air quality situation (2-3 sentences)

2. **Health Impact for You**
Specific health implications based on user's profile (2-3 sentences)

3. **Essential Protection for Outdoor Work**
(Use this section if user mentions working/being outside)
- Specific masks and protective equipment
- Timing strategies for outdoor work
- Practical health monitoring tips

4. **Work Schedule Recommendations**
When to schedule breaks and safer work hours (1-2 sentences)

5. **Additional Safety Measures**
- Hydration and nutrition tips
- Emergency signs to watch for
- Post-work recovery measures

Keep each section concise and actionable. Use simple language. Be empathetic but direct. ALWAYS provide solutions for outdoor work when user indicates they must be outside."""

        # Build user prompt with comprehensive data - USE VERIFIED CITY NAME
        user_prompt = f"""LOCATION & AIR QUALITY DATA:
- Location: {verified_city}
- Current AQI: {aqi} ({aqi_category})
"""
        
        # Add pollutant information
        if pollutants:
            user_prompt += "\nPOLLUTANT LEVELS:\n"
            if pollutants.get('pm25') and pollutants.get('pm25') is not None:
                user_prompt += f"- PM2.5: {pollutants['pm25']:.1f} µg/m³\n"
            if pollutants.get('pm10') and pollutants.get('pm10') is not None:
                user_prompt += f"- PM10: {pollutants['pm10']:.1f} µg/m³\n"
            if pollutants.get('o3') and pollutants.get('o3') is not None:
                user_prompt += f"- Ozone (O₃): {pollutants['o3']:.1f} ppb\n"
            if pollutants.get('no2') and pollutants.get('no2') is not None:
                user_prompt += f"- Nitrogen Dioxide (NO₂): {pollutants['no2']:.1f} ppb\n"
            if pollutants.get('so2') and pollutants.get('so2') is not None:
                user_prompt += f"- Sulfur Dioxide (SO₂): {pollutants['so2']:.1f} ppb\n"
            if pollutants.get('co') and pollutants.get('co') is not None:
                user_prompt += f"- Carbon Monoxide (CO): {pollutants['co']:.1f} ppm\n"
        
        if dominant_pollutant:
            user_prompt += f"\nDominant Pollutant: {dominant_pollutant.upper()}\n"
        
        # Add weather information
        if weather:
            user_prompt += "\nWEATHER CONDITIONS:\n"
            if weather.get('temperature') and weather.get('temperature') is not None:
                user_prompt += f"- Temperature: {weather['temperature']:.1f}°C\n"
            if weather.get('humidity') and weather.get('humidity') is not None:
                user_prompt += f"- Humidity: {weather['humidity']:.1f}%\n"
            if weather.get('wind_speed') and weather.get('wind_speed') is not None:
                user_prompt += f"- Wind Speed: {weather['wind_speed']:.1f} m/s\n"
            if weather.get('conditions'):
                user_prompt += f"- Conditions: {weather['conditions']}\n"
        
        # Add user profile
        user_prompt += "\nUSER PROFILE:\n"
        
        if age:
            user_prompt += f"- Age: {age} years old\n"
        elif age_group:
            age_descriptions = {
                'child': 'Child (0-12 years)',
                'teen': 'Teenager (13-19 years)',
                'adult': 'Adult (20-60 years)',
                'senior': 'Senior (60+ years)'
            }
            user_prompt += f"- Age Group: {age_descriptions.get(age_group, age_group)}\n"
        
        if gender and gender != 'prefer-not-to-say':
            user_prompt += f"- Gender: {gender.capitalize()}\n"
        
        if time_outside:
            user_prompt += f"- Daily time spent outside: {time_outside} hours\n"
        
        if conditions and 'none' not in conditions:
            user_prompt += f"- Health Conditions: {', '.join(conditions)}\n"
        else:
            user_prompt += "- Health Conditions: None reported\n"
        
        # Add specific question if provided
        if question:
            user_prompt += f"\nUSER'S SPECIFIC QUESTION:\n{question}\n"
            # Detect if user MUST work outside
            work_keywords = ['work', 'job', 'have to', 'must', 'need to', 'required']
            if any(keyword in question.lower() for keyword in work_keywords):
                user_prompt += "\nIMPORTANT: User indicates they MUST be outside. Provide PRACTICAL protective measures for outdoor work, not advice to avoid going outside.\n"
        
        user_prompt += "\nProvide personalized health advice following the structured format above. Be practical and solution-oriented."
        
        print("\n📄 Generated prompt length:", len(user_prompt))
        
        # Call Gemini API
        try:
            if not gemini_available:
                print("⚠️ Gemini API not available, using fallback")
                raise ImportError("Gemini API not initialized")
            
            print(f"🤖 Calling Gemini API (Model: gemini-2.5-flash)")
            
            # Prepare Gemini API request
            headers = {
                'Content-Type': 'application/json'
            }
            
            payload = {
                "system_instruction": {
                    "parts": [
                        {"text": system_instruction}
                    ]
                },
                "contents": [
                    {
                        "parts": [
                            {"text": user_prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "topP": 0.9,
                    "maxOutputTokens": 1200
                }
            }
            
            # Make API request with timeout
            response = requests.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            # Check if request was successful
            if response.status_code != 200:
                print(f"❌ Gemini API Error: Status {response.status_code}")
                print(f"Response: {response.text}")
                raise Exception(f"Gemini API returned status {response.status_code}")
            
            # Parse response
            response_data = response.json()
            
            # Extract advice from Gemini response
            if 'candidates' in response_data and len(response_data['candidates']) > 0:
                advice = response_data['candidates'][0]['content']['parts'][0]['text'].strip()
            else:
                print(f"❌ Unexpected Gemini response format: {response_data}")
                raise Exception("Invalid response format from Gemini")
            
            print(f"✅ AI Advice generated successfully")
            print(f"📄 Response length: {len(advice)} characters")
            print(f"🔍 AI Response Content: {advice}")
            print(f"\nFull API Response: {json.dumps(response_data, indent=2)}")
            print("=" * 60)
            
            return jsonify({
                'advice': advice,
                'aqi': aqi,
                'category': aqi_category,
                'location': verified_city
            }), 200
            
        except Exception as e:
            print(f"❌ Gemini API Error: {e}")
            import traceback
            traceback.print_exc()
            
            print("📄 Falling back to rule-based advice")
            # Fallback to enhanced rule-based advice
            return get_enhanced_fallback_advice(
                aqi, aqi_category, pollutants, age, age_group, 
                gender, time_outside, conditions, question, verified_city, weather
            )
            
    except Exception as e:
        print(f"❌ ERROR in get_ai_personalized_advice: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to generate personalized advice'}), 500


def get_enhanced_fallback_advice(aqi, aqi_category, pollutants, age, age_group, gender, time_outside, conditions, question, city_name, weather):
    """Enhanced fallback advice when AI API is unavailable"""
    
    print(f"🔧 Generating fallback advice for AQI: {aqi}")
    
    # Determine if user MUST work outside
    must_work_outside = False
    if question:
        work_keywords = ['work', 'job', 'have to', 'must', 'need to', 'required', 'working']
        must_work_outside = any(keyword in question.lower() for keyword in work_keywords)
    
    # Determine user vulnerability level
    is_vulnerable = False
    vulnerability_factors = []
    
    if age:
        if age < 18:
            is_vulnerable = True
            vulnerability_factors.append("young age")
        elif age > 60:
            is_vulnerable = True
            vulnerability_factors.append("senior age")
    elif age_group in ['child', 'teen', 'senior']:
        is_vulnerable = True
        vulnerability_factors.append(age_group)
    
    if conditions and 'none' not in conditions:
        is_vulnerable = True
        vulnerability_factors.extend(conditions)
    
    # Build structured advice
    advice = f"**1. Current Air Quality Assessment**\n\n"
    
    if aqi <= 50:
        advice += f"The air quality in {city_name} is excellent with an AQI of {aqi}. This is ideal for all outdoor activities including work. "
    elif aqi <= 100:
        advice += f"The air quality in {city_name} is moderate with an AQI of {aqi}. Outdoor work is generally safe with basic precautions. "
    elif aqi <= 150:
        advice += f"The air quality in {city_name} is unhealthy for sensitive groups with an AQI of {aqi}. Outdoor workers should take protective measures. "
    elif aqi <= 200:
        advice += f"The air quality in {city_name} is unhealthy with an AQI of {aqi}. All outdoor workers need significant protection. "
    elif aqi <= 300:
        advice += f"The air quality in {city_name} is very unhealthy with an AQI of {aqi}. Outdoor work poses serious health risks. "
    else:
        advice += f"⚠️ HAZARDOUS AIR QUALITY in {city_name} with an AQI of {aqi}. Emergency conditions - outdoor work extremely dangerous. "
    
    if pollutants.get('pm25'):
        advice += f"PM2.5 levels: {pollutants['pm25']:.1f} µg/m³. "
    
    advice += "\n\n**2. Health Impact for You**\n\n"
    
    if is_vulnerable:
        if aqi <= 100:
            advice += f"With {', '.join(vulnerability_factors)}, you should monitor for symptoms but can work outdoors safely. "
        elif aqi <= 150:
            advice += f"Your profile ({', '.join(vulnerability_factors)}) puts you at higher risk. Take extra precautions while working outside. "
        elif aqi <= 200:
            advice += f"Given {', '.join(vulnerability_factors)}, outdoor work poses significant risks including respiratory distress. "
        else:
            advice += f"⚠️ CRITICAL RISK with {', '.join(vulnerability_factors)}. Outdoor work strongly discouraged unless absolutely necessary. "
    else:
        if aqi <= 150:
            advice += "For healthy individuals, outdoor work is manageable with proper protection. "
        elif aqi <= 200:
            advice += "Even healthy workers will experience respiratory discomfort and reduced stamina. "
        else:
            advice += "Serious health risks for all outdoor workers. "
    
    # CRITICAL: If user must work outside, provide PROTECTIVE measures, not avoidance advice
    if must_work_outside:
        advice += "\n\n**3. Essential Protection for Outdoor Work**\n\n"
        
        if aqi <= 100:
            advice += "- No special masks required, but stay hydrated\n"
            advice += "- Take regular breaks in shaded areas\n"
            advice += "- Monitor for any unusual symptoms\n"
        elif aqi <= 150:
            advice += "- MANDATORY: Wear N95 or N99 respirator masks throughout work\n"
            advice += "- Replace masks every 4-6 hours or when breathing becomes difficult\n"
            advice += "- Take 10-minute breaks every hour indoors if possible\n"
            if 'asthma' in conditions or 'breathing' in conditions:
                advice += "- Keep your rescue inhaler easily accessible\n"
        elif aqi <= 200:
            advice += "- CRITICAL: Use N95/N99 respirators - surgical masks are NOT sufficient\n"
            advice += "- Fit-test your mask properly before starting work\n"
            advice += "- Take 15-minute breaks every 45 minutes in clean air environment\n"
            advice += "- Wear protective eyewear if available (pollution irritates eyes)\n"
            advice += "- Drink water every 30 minutes even if not thirsty\n"
        else:
            advice += "- ESSENTIAL: N99 or P100 respirator masks only - lower grades insufficient\n"
            advice += "- Minimize physical exertion - work at slower pace\n"
            advice += "- Take 20-minute breaks every 30-40 minutes in filtered air space\n"
            advice += "- Full protective gear: mask, goggles, long sleeves\n"
            advice += "- Have emergency contact readily available\n"
        
        advice += "\n\n**4. Work Schedule Recommendations**\n\n"
        
        if aqi <= 150:
            advice += "Early morning (6-8 AM) typically has better air quality. Try to schedule heavy work during these hours. "
        elif aqi <= 200:
            advice += "Work only during early morning (6-7:30 AM) when possible. Avoid afternoon hours (2-6 PM) when pollution peaks. Take longer breaks during peak pollution times. "
        else:
            advice += "If outdoor work cannot be avoided, work in very short shifts (30-45 minutes max) with extended breaks in clean air environment. Early morning hours only. "
        
        advice += "\n\n**5. Additional Safety Measures**\n\n"
        
        if aqi <= 150:
            advice += "- Drink 3-4 liters of water during work shift\n"
            advice += "- Eat antioxidant-rich foods (fruits, vegetables)\n"
            advice += "- Shower immediately after work to remove particles\n"
            advice += "- Monitor for: persistent cough, chest tightness, shortness of breath\n"
        else:
            advice += "- Increase water intake to 4-5 liters during work\n"
            advice += "- Consider vitamin C supplements (consult doctor)\n"
            advice += "- Change clothes and shower immediately after work\n"
            advice += "- Use air purifier at home for recovery\n"
            advice += "- STOP WORK IMMEDIATELY if you experience: severe breathlessness, chest pain, dizziness, or severe headache\n"
            advice += "- Seek medical attention if symptoms persist after work\n"
        
        if conditions and 'none' not in conditions:
            advice += f"- Extra caution: Your conditions ({', '.join(conditions)}) require closer health monitoring\n"
    
    else:
        # Standard advice for those not required to work outside
        advice += "\n\n**3. Recommended Actions**\n\n"
        
        if aqi <= 50:
            advice += "- Enjoy outdoor activities without restrictions\n"
            advice += "- No special precautions needed\n"
        elif aqi <= 100:
            advice += "- Normal outdoor activities acceptable\n"
            advice += "- Sensitive groups should watch for symptoms\n"
        elif aqi <= 150:
            advice += "- Limit prolonged outdoor exposure\n"
            advice += "- Wear N95 mask if going outside\n"
            advice += "- Keep windows closed during peak hours\n"
        elif aqi <= 200:
            advice += "- Minimize outdoor time\n"
            advice += "- N95/KN95 masks mandatory when outside\n"
            advice += "- Stay indoors as much as possible\n"
        else:
            advice += "- STAY INDOORS\n"
            advice += "- Avoid all outdoor activities\n"
            advice += "- Use air purifiers indoors\n"
    
    print(f"✅ Fallback advice generated, length: {len(advice)}")
    
    return jsonify({
        'advice': advice,
        'aqi': aqi,
        'category': aqi_category,
        'location': city_name,
        'fallback': True
    }), 200


@ai_advisor_auth.route('/api/user/check', methods=['GET'])
def check_user_logged_in():
    """Check if user is logged in and return user data from session"""
    if 'user_id' in session:
        user_id = session.get('user_id')
        #checking in termianl
        print('\nSession Details of user_id', user_id,'\n')
        
        try:
            # Fetch user data from database
            conn = get_db_connection()
            if not conn:
                return jsonify({'logged_in': False, 'error': 'Database connection failed'}), 500
            cursor = conn.cursor()
            print('cursor is created successfully')
            cursor.execute("SELECT username, email, age, gender, city FROM login_data WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user:
                user_data = {
                    'logged_in': True,
                    'user_id': user_id,
                    'username': user[0],
                    'email': user[1],
                    'age': user[2],
                    'gender': user[3],
                    'city': user[4]
                }
                print(f"✅ User logged in: {user_data}")
                return jsonify(user_data), 200
            else:
                print(f"⚠️ User ID {user_id} not found in database")
                return jsonify({'logged_in': False}), 401
                
        except Exception as e:
            print(f"❌ Database error: {e}")
            flash('Cannot fetch user data from database', 'danger')
            return jsonify({'logged_in': False, 'error': 'Database error'}), 500
    
    print("⚠️ User not logged in")
    return jsonify({'logged_in': False}), 401


@ai_advisor_auth.route('/api/user/city', methods=['GET'])
def get_user_city():
    """Get user's city from session"""
    if 'user_id' in session:
        user_city = session.get('user_city')
        
        if user_city:
            print(f"✅ User city from session: {user_city}")
            return jsonify({'city': user_city}), 200
        
        # Try to fetch from database
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT city FROM login_data WHERE id = %s", (session.get('user_id'),))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result and result[0]:
                return jsonify({'city': result[0]}), 200
            else:
                print("⚠️ No city found for user")
                return jsonify({'city': None}), 200
                
        except Exception as e:
            print(f"❌ Database error: {e}")
            return jsonify({'city': None, 'error': 'Database error'}), 500
    
    print("⚠️ User not logged in - no city")
    return jsonify({'error': 'Not logged in'}), 401