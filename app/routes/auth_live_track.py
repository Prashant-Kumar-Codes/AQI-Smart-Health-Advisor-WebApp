from .extensions import *
from datetime import datetime, timedelta
from flask_mail import Message
import os
import json

live_track_auth = Blueprint('live_track_auth', '__name__')

# Gemini API Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyC8R96XiTZ1U90D5N-YztBh9VpZQbuWoNE')
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# Initialize Gemini client
gemini_available = True
try:
    import requests
    print("✓ Gemini API initialized successfully for live tracker")
except ImportError:
    print("⚠ Warning: requests package not installed")
    gemini_available = False
except Exception as e:
    print(f"⚠ Warning: Gemini client initialization failed: {e}")
    gemini_available = False


@live_track_auth.route('/live_track', methods=['GET'])
def live_track():
    """Live Tracker page route - Login required to use functionality"""
    return render_template('auth/live_track.html')


@live_track_auth.route('/api/live-tracker/alert', methods=['POST'])
def create_alert():
    """Create and send an alert for location/AQI change"""
    try:
        # CHECK IF USER IS LOGGED IN
        if 'user_id' not in session:
            print("⚠ User not logged in - returning 401")
            return jsonify({
                'error': 'Please log in to use Live Tracking',
                'redirect': '/login'
            }), 401
        
        user_id = session['user_id']
        user_email = session.get('user_email', 'user@example.com')
        
        data = request.get_json()
        
        print("=" * 60)
        print("📍 Received live tracker alert request")
        print("=" * 60)
        print("Request data:", json.dumps(data, indent=2))
        
        # Extract data
        alert_type = data.get('type', 'unknown')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        aqi = data.get('aqi', 0)
        aqi_category = data.get('aqi_category', 'Unknown')
        pollutants = data.get('pollutants', {})
        city_name = data.get('city_name', 'Unknown')
        dominant_pollutant = data.get('dominant_pollutant')
        send_email = data.get('send_email', False)
        
        print(f"📊 Alert Type: {alert_type}")
        print(f"📍 Location: {city_name} ({latitude}, {longitude})")
        print(f"💨 AQI: {aqi} ({aqi_category})")
        print(f"📧 Send Email: {send_email}")
        
        # Generate AI recommendations
        recommendations = generate_recommendations(aqi, aqi_category, pollutants, dominant_pollutant)
        
        # Generate alert message
        if alert_type == 'initial':
            message = f"Live tracking started in {city_name}. Current air quality: {aqi_category} (AQI: {aqi})."
        elif alert_type == 'location_change':
            message = f"You've moved to a new location: {city_name}. Air quality here: {aqi_category} (AQI: {aqi})."
        elif alert_type == 'aqi_change':
            message = f"Significant air quality change detected in {city_name}. Current AQI: {aqi} ({aqi_category})."
        else:
            message = f"Air quality update for {city_name}: AQI {aqi} ({aqi_category})."
        
        # Create alert object
        alert_timestamp = datetime.now()
        alert = {
            'id': f"{user_id}_{int(alert_timestamp.timestamp())}",
            'user_id': user_id,
            'type': alert_type,
            'timestamp': alert_timestamp.isoformat(),
            'location': city_name,
            'latitude': latitude,
            'longitude': longitude,
            'aqi': aqi,
            'aqi_category': aqi_category,
            'message': message,
            'recommendations': recommendations,
            'pollutants': pollutants
        }
        
        # Store alert in database
        store_alert_in_db(user_email, alert, recommendations)
        
        # Send email alert if requested and AQI > 50
        if send_email and aqi > 50:
            try:
                send_email_alert(user_email, alert)
                print(f"✓ Email sent to {user_email}")
            except Exception as e:
                print(f"⚠ Failed to send email: {e}")
                import traceback
                traceback.print_exc()
                # Don't fail the request if email fails
        
        print("=" * 60)
        
        return jsonify(alert), 200
        
    except Exception as e:
        print(f"❌ ERROR in create_alert: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to create alert'}), 500


@live_track_auth.route('/api/live-tracker/alerts', methods=['GET'])
def get_alerts():
    """Get all alerts for the current user from database"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        
        user_email = session.get('user_email')
        
        if not user_email:
            return jsonify({'alerts': []}), 200
        
        # Get alerts from database
        alerts = get_alerts_from_db(user_email)
        
        print(f"📜 Retrieved {len(alerts)} alerts for user {user_email}")
        
        return jsonify({'alerts': alerts}), 200
        
    except Exception as e:
        print(f"❌ ERROR in get_alerts: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to retrieve alerts'}), 500


@live_track_auth.route('/api/live-tracker/alerts/clear', methods=['POST'])
def clear_alerts():
    """Clear all alerts for the current user from database"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        
        user_email = session.get('user_email')
        
        if user_email:
            clear_alerts_from_db(user_email)
            print(f"🗑️ Cleared alerts for user {user_email}")
        
        return jsonify({'message': 'Alerts cleared'}), 200
        
    except Exception as e:
        print(f"❌ ERROR in clear_alerts: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to clear alerts'}), 500


def generate_recommendations(aqi, aqi_category, pollutants, dominant_pollutant):
    """Generate top 3 recommendations based on AQI using AI"""
    
    print(f"🤖 Generating AI recommendations for AQI: {aqi}")
    
    # Try to use Gemini API
    if gemini_available:
        try:
            system_instruction = """You are a professional air quality health advisor with expertise in environmental health and respiratory medicine.

Generate exactly 3 concise, actionable health recommendations for the current air quality conditions.

RULES:
- Each recommendation must be ONE clear sentence
- Keep each recommendation under 20 words
- Focus on immediate, practical protective actions
- Use professional but accessible language
- Be specific and actionable
- Number them 1, 2, 3

Examples of good recommendations:
1. Limit outdoor activities to less than 30 minutes and avoid strenuous exercise
2. Wear an N95 or KN95 mask when going outside for adequate protection
3. Keep windows closed and run air purifiers with HEPA filters indoors"""
            
            user_prompt = f"""Current Air Quality Conditions:
- AQI Level: {aqi} ({aqi_category})
- Primary Pollutant: {dominant_pollutant or 'Not specified'}
"""
            
            if pollutants.get('pm25'):
                user_prompt += f"- PM2.5 Concentration: {pollutants['pm25']:.1f} µg/m³\n"
            if pollutants.get('pm10'):
                user_prompt += f"- PM10 Concentration: {pollutants['pm10']:.1f} µg/m³\n"
            if pollutants.get('o3'):
                user_prompt += f"- Ozone (O₃) Level: {pollutants['o3']:.1f} ppb\n"
            
            user_prompt += "\nGenerate 3 specific health recommendations. Number them 1, 2, 3."
            
            print(f"🔹 Calling Gemini API (gemini-1.5-flash) for recommendations")
            
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
                    "maxOutputTokens": 250
                }
            }
            
            # Make API request
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
            
            # Extract recommendations from Gemini response
            if 'candidates' in response_data and len(response_data['candidates']) > 0:
                ai_response = response_data['candidates'][0]['content']['parts'][0]['text'].strip()
            else:
                print(f"❌ Unexpected Gemini response format: {response_data}")
                raise Exception("Invalid response format from Gemini")
            
            print(f"🤖 AI Response:\n{ai_response}")
            
            # Parse numbered recommendations
            recommendations = []
            for line in ai_response.split('\n'):
                line = line.strip()
                # Remove number prefix (1., 2., 3., 1), 2), etc.)
                if line and (line[0].isdigit() or line.startswith('-')):
                    clean_line = line.lstrip('0123456789.-) ').strip()
                    if clean_line and len(clean_line) > 10:  # Ensure meaningful content
                        recommendations.append(clean_line)
            
            # Ensure we have exactly 3 recommendations
            if len(recommendations) >= 3:
                recommendations = recommendations[:3]
                print(f"✓ AI recommendations successfully generated:")
                for i, rec in enumerate(recommendations, 1):
                    print(f"  {i}. {rec}")
                return recommendations
            else:
                print(f"⚠ AI returned only {len(recommendations)} recommendations, expected 3")
                print(f"⚠ FAILURE: Unable to get proper AI advice - using fallback")
                
        except Exception as e:
            print(f"❌ Gemini API error: {e}")
            print(f"⚠ FAILURE: Error in getting AI advice - using fallback")
            import traceback
            traceback.print_exc()
    else:
        print("⚠ FAILURE: Gemini API not initialized - using fallback")
    
    # Fallback to rule-based recommendations
    recommendations = get_fallback_recommendations(aqi, aqi_category, dominant_pollutant)
    print(f"✓ Using fallback recommendations:")
    for i, rec in enumerate(recommendations, 1):
        print(f"  {i}. {rec}")
    return recommendations


def get_fallback_recommendations(aqi, aqi_category, dominant_pollutant):
    """Rule-based recommendations when AI is unavailable"""
    
    recommendations = []
    
    if aqi <= 50:
        recommendations = [
            "Air quality is excellent - enjoy outdoor activities without restrictions",
            "Perfect conditions for exercise and spending time outside",
            "Consider opening windows to ventilate your indoor spaces naturally"
        ]
    elif aqi <= 100:
        recommendations = [
            "Air quality is acceptable for most outdoor activities",
            "Sensitive individuals should watch for symptoms and limit prolonged exertion",
            "Monitor air quality if you have respiratory or heart conditions"
        ]
    elif aqi <= 150:
        recommendations = [
            "Limit prolonged outdoor activities, especially for sensitive groups",
            "Wear an N95 mask if you need to spend extended time outside",
            "Keep windows closed and use air purifiers with HEPA filters indoors"
        ]
    elif aqi <= 200:
        recommendations = [
            "Avoid prolonged outdoor activities and stay indoors when possible",
            "Wear N95 or KN95 masks whenever you go outside for protection",
            "Run HEPA air purifiers continuously and seal windows and doors"
        ]
    elif aqi <= 300:
        recommendations = [
            "Stay indoors and avoid going outside unless absolutely necessary",
            "Use N95 or N99 respirators for any unavoidable outdoor exposure",
            "Create a clean air room with multiple HEPA air purifiers running"
        ]
    else:  # Hazardous
        recommendations = [
            "EMERGENCY: Remain indoors at all times - do not go outside",
            "Seal all windows and doors and run air purifiers on maximum settings",
            "Monitor your health closely and have emergency contacts readily available"
        ]
    
    return recommendations[:3]


def store_alert_in_db(user_email, alert, recommendations):
    """Store alert in PostgreSQL database"""
    try:
        from app.db import get_db_connection
        conn = get_db_connection()
        if not conn:
            return
        cursor = conn.cursor()
        
        # Store with expiry time (30 minutes after creation)
        expiry_time = datetime.now() + timedelta(minutes=30)
        
        # Convert recommendations list to JSON string
        recommendations_json = json.dumps(recommendations)
        
        # Convert pollutants dict to JSON string
        pollutants_json = json.dumps(alert.get('pollutants', {}))
        
        query = """
        INSERT INTO tracking_alerts 
        (user_email, alert_type, timestamp, location, latitude, longitude, 
         aqi, aqi_category, message, recommendations, pollutants, expiry_time)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            user_email,
            alert['type'],
            datetime.fromisoformat(alert['timestamp']),
            alert['location'],
            alert['latitude'],
            alert['longitude'],
            alert['aqi'],
            alert['aqi_category'],
            alert['message'],
            recommendations_json,
            pollutants_json,
            expiry_time
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✓ Alert stored in database (expires at {expiry_time})")
        
    except Exception as e:
        print(f"❌ Error storing alert in database: {e}")
        import traceback
        traceback.print_exc()


def get_alerts_from_db(user_email):
    """Retrieve active alerts from database and clean up expired ones"""
    try:
        from app.db import get_db_connection
        conn = get_db_connection()
        if not conn:
            return []
        cursor = conn.cursor()
        
        # First, delete expired alerts
        delete_query = "DELETE FROM tracking_alerts WHERE expiry_time < NOW()"
        cursor.execute(delete_query)
        conn.commit()
        
        # Get active alerts
        query = """
        SELECT alert_type, timestamp, location, latitude, longitude,
               aqi, aqi_category, message, recommendations, pollutants
        FROM tracking_alerts
        WHERE user_email = %s AND expiry_time >= NOW()
        ORDER BY timestamp DESC
        LIMIT 50
        """
        
        cursor.execute(query, (user_email,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        alerts = []
        for row in rows:
            try:
                alerts.append({
                    'type': row[0],
                    'timestamp': row[1].isoformat(),
                    'location': row[2],
                    'latitude': row[3],
                    'longitude': row[4],
                    'aqi': row[5],
                    'aqi_category': row[6],
                    'message': row[7],
                    'recommendations': json.loads(row[8]) if row[8] else [],
                    'pollutants': json.loads(row[9]) if row[9] else {}
                })
            except Exception as e:
                print(f"Error parsing alert row: {e}")
                continue
        
        return alerts
        
    except Exception as e:
        print(f"❌ Error retrieving alerts from database: {e}")
        import traceback
        traceback.print_exc()
        return []


def clear_alerts_from_db(user_email):
    """Clear all alerts for user from database"""
    try:
        from app.db import get_db_connection
        conn = get_db_connection()
        if not conn:
            return
        cursor = conn.cursor()
        
        query = "DELETE FROM tracking_alerts WHERE user_email = %s"
        cursor.execute(query, (user_email,))
        conn.commit()
        
        deleted_count = cursor.rowcount
        cursor.close()
        conn.close()
        
        print(f"✓ Deleted {deleted_count} alerts from database")
        
    except Exception as e:
        print(f"❌ Error clearing alerts from database: {e}")
        import traceback
        traceback.print_exc()


def send_email_alert(recipient_email, alert):
    """Send email alert to user using Flask-Mail"""
    
    print(f"📧 Preparing email for {recipient_email}")
    
    # Create HTML email body
    html_body = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #1f2937;
                margin: 0;
                padding: 0;
                background-color: #f3f4f6;
            }}
            .email-wrapper {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 40px 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0 0 10px 0;
                font-size: 28px;
                font-weight: 700;
            }}
            .header p {{
                margin: 0;
                font-size: 16px;
                opacity: 0.95;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .info-row {{
                display: flex;
                justify-content: space-between;
                padding: 12px 0;
                border-bottom: 1px solid #e5e7eb;
            }}
            .info-label {{
                font-weight: 600;
                color: #6b7280;
            }}
            .info-value {{
                color: #1f2937;
                font-weight: 500;
            }}
            .aqi-display {{
                text-align: center;
                padding: 30px;
                background: linear-gradient(135deg, #f0fdf4, #dcfce7);
                border-radius: 12px;
                margin: 25px 0;
            }}
            .aqi-value {{
                font-size: 48px;
                font-weight: 900;
                color: {'#10b981' if alert['aqi'] <= 100 else '#f59e0b' if alert['aqi'] <= 200 else '#ef4444'};
                margin: 0 0 10px 0;
            }}
            .aqi-category {{
                font-size: 20px;
                font-weight: 700;
                color: #047857;
            }}
            .message-box {{
                background-color: #f9fafb;
                border-left: 4px solid #667eea;
                padding: 20px;
                margin: 25px 0;
                border-radius: 8px;
            }}
            .recommendations {{
                background: linear-gradient(135deg, #fef3c7, #fde68a);
                border-left: 4px solid #f59e0b;
                padding: 25px;
                margin: 25px 0;
                border-radius: 8px;
            }}
            .recommendations h3 {{
                color: #92400e;
                margin: 0 0 15px 0;
                font-size: 18px;
            }}
            .recommendations ul {{
                margin: 0;
                padding-left: 20px;
            }}
            .recommendations li {{
                color: #78350f;
                margin: 10px 0;
                line-height: 1.6;
            }}
            .pollutants {{
                margin: 25px 0;
            }}
            .pollutants h3 {{
                color: #1f2937;
                font-size: 18px;
                margin: 0 0 15px 0;
            }}
            .pollutant-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
            }}
            .pollutant-item {{
                background: #f9fafb;
                padding: 12px;
                border-radius: 8px;
                border: 1px solid #e5e7eb;
            }}
            .pollutant-name {{
                font-size: 12px;
                color: #6b7280;
                font-weight: 600;
                text-transform: uppercase;
            }}
            .pollutant-value {{
                font-size: 18px;
                color: #1f2937;
                font-weight: 700;
                margin-top: 4px;
            }}
            .footer {{
                text-align: center;
                padding: 30px;
                background-color: #f9fafb;
                color: #6b7280;
                font-size: 14px;
            }}
            .footer p {{
                margin: 5px 0;
            }}
        </style>
    </head>
    <body>
        <div class="email-wrapper">
            <div class="header">
                <h1>🚨 Air Quality Alert</h1>
                <p>{alert['location']}</p>
            </div>
            <div class="content">
                <div class="info-row">
                    <span class="info-label">Alert Type</span>
                    <span class="info-value">{alert['type'].replace('_', ' ').title()}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Time</span>
                    <span class="info-value">{datetime.fromisoformat(alert['timestamp']).strftime('%B %d, %Y at %I:%M %p')}</span>
                </div>
                
                <div class="aqi-display">
                    <div class="aqi-value">{alert['aqi']}</div>
                    <div class="aqi-category">{alert['aqi_category']}</div>
                </div>
                
                <div class="message-box">
                    {alert['message']}
                </div>
"""
    
    if alert['pollutants']:
        html_body += '<div class="pollutants"><h3>Pollutant Levels</h3><div class="pollutant-grid">'
        if alert['pollutants'].get('pm25'):
            html_body += f"""
                <div class="pollutant-item">
                    <div class="pollutant-name">PM2.5</div>
                    <div class="pollutant-value">{alert['pollutants']['pm25']:.1f} µg/m³</div>
                </div>
            """
        if alert['pollutants'].get('pm10'):
            html_body += f"""
                <div class="pollutant-item">
                    <div class="pollutant-name">PM10</div>
                    <div class="pollutant-value">{alert['pollutants']['pm10']:.1f} µg/m³</div>
                </div>
            """
        if alert['pollutants'].get('o3'):
            html_body += f"""
                <div class="pollutant-item">
                    <div class="pollutant-name">Ozone (O₃)</div>
                    <div class="pollutant-value">{alert['pollutants']['o3']:.1f} ppb</div>
                </div>
            """
        if alert['pollutants'].get('no2'):
            html_body += f"""
                <div class="pollutant-item">
                    <div class="pollutant-name">NO₂</div>
                    <div class="pollutant-value">{alert['pollutants']['no2']:.1f} ppb</div>
                </div>
            """
        html_body += '</div></div>'
    
    if alert['recommendations']:
        html_body += """
                <div class="recommendations">
                    <h3>🛡️ Important Health Recommendations</h3>
                    <ul>
        """
        for rec in alert['recommendations']:
            html_body += f"<li>{rec}</li>"
        html_body += """
                    </ul>
                </div>
        """
    
    html_body += """
                <div class="footer">
                    <p><strong>AQI Live Tracker</strong></p>
                    <p>Automated air quality monitoring and health advisory system</p>
                    <p style="margin-top: 15px; font-size: 12px;">Stay safe and monitor air quality regularly</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Create and send message using Flask-Mail
    try:
        msg = Message(
            subject=f"🚨 Air Quality Alert - AQI {alert['aqi']} in {alert['location']}",
            recipients=[recipient_email],
            html=html_body
        )
        
        mail.send(msg)
        print(f"✓ Email sent successfully to {recipient_email}")
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        import traceback
        traceback.print_exc()
        raise