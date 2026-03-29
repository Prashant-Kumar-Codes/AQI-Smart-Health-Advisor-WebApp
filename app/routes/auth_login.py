from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mail import Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import psycopg2
import random
from app.db import get_db_connection
from app.__init__ import mail


login_auth = Blueprint('login_auth', __name__)

@login_auth.route('/login_signup', methods=['GET'])
def login_signup_page():
    """Display login/signup page and capture redirect parameter"""
    redirect_to = request.args.get('redirect', '')
    default_form = request.args.get('form', 'login')
    
    # CRITICAL: Clear ALL flash messages for this AJAX-based page
    # Flash messages don't work with AJAX forms - we use JSON responses instead
    if '_flashes' in session:
        session.pop('_flashes', None)
    
    # Also clear on render to be absolutely sure
    from flask import get_flashed_messages
    get_flashed_messages()  # This consumes and clears them
    
    return render_template('auth/login_signup.html', redirect_to=redirect_to, default_form=default_form)


@login_auth.route('/verify', methods=['GET'])
def verify_page():
    """Display OTP verification page"""
    # Check if user has verification email in session
    if 'verification_email' not in session:
        flash('Please sign up first to verify your email', 'error')
        return redirect(url_for('login_auth.login_signup_page', form='signup'))
    
    # Calculate remaining time
    email = session['verification_email']
    
    mycon = get_db_connection()
    if not mycon:
        flash('Database connection failed. Please try again later.', 'error')
        return redirect(url_for('home_auth.aqi_homepage'))
        
    cursor = mycon.cursor()
    cursor.execute("SELECT otp_created_at FROM aqi_login_data WHERE email = %s", (email,))
    result = cursor.fetchone()
    cursor.close()
    mycon.close()
    
    remaining = 600  # Default 10 minutes
    if result and result[0]:
        otp_created_at = result[0]
        # Use utcnow() to match DB (UTC)
        elapsed = (datetime.utcnow() - otp_created_at).total_seconds()
        remaining = max(0, 600 - int(elapsed))  # 600 seconds = 10 minutes
    
    return render_template('auth/verify.html', remaining=remaining)


@login_auth.route('/verify', methods=['POST'])
def verify():
    """Handle OTP verification from form submission"""
    try:
        # Get email from session
        email = session.get('verification_email')
        
        if not email:
            flash('Session expired. Please sign up again.', 'error')
            return redirect(url_for('login_auth.login_signup_page', form='signup'))
        
        # Get OTP from form
        otp = request.form.get('otp', '').strip()
        
        if not otp or len(otp) != 6:
            flash('Please enter a valid 6-digit OTP', 'error')
            return redirect(url_for('login_auth.verify_page'))
        
        mycon = get_db_connection()
        if not mycon:
            flash('Database connection failed. Please try again later.', 'error')
            return redirect(url_for('login_auth.verify_page'))
            
        cursor = mycon.cursor()
        cursor.execute(
            "SELECT otp, otp_created_at FROM aqi_login_data WHERE email = %s",
            (email,)
        )
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            mycon.close()
            flash('User not found. Please sign up again.', 'error')
            return redirect(url_for('login_auth.login_signup_page', form='signup'))
        
        stored_otp, otp_created_at = result
        
        # Check if OTP is expired (10 minutes)
        # Use utcnow() to match DB (UTC)
        if datetime.utcnow() - otp_created_at > timedelta(minutes=10):
            cursor.close()
            mycon.close()
            flash('OTP has expired. Please request a new code.', 'error')
            return redirect(url_for('login_auth.verify_page'))
        
        # Verify OTP
        if stored_otp != otp:
            cursor.close()
            mycon.close()
            flash('Invalid OTP. Please try again.', 'error')
            return redirect(url_for('login_auth.verify_page'))
        
        # Mark as verified
        cursor.execute(
            "UPDATE aqi_login_data SET is_verified = TRUE, otp = NULL WHERE email = %s",
            (email,)
        )
        mycon.commit()
        cursor.close()
        mycon.close()
        
        # Clear verification session
        session.pop('verification_email', None)
        session.pop('verification_username', None)
        
        flash('Email verified successfully! You can now log in.', 'success')
        return redirect(url_for('login_auth.login_signup_page'))
        
    except Exception as e:
        print(f"❌ Verification error: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('An error occurred during verification. Please try again.', 'error')
        return redirect(url_for('login_auth.verify_page'))


@login_auth.route('/resend_otp', methods=['POST'])
def resend_otp():
    """Resend OTP to user's email"""
    try:
        email = session.get('verification_email')
        username = session.get('verification_username', 'User')
        
        if not email:
            flash('Session expired. Please sign up again.', 'error')
            return redirect(url_for('login_auth.login_signup_page', form='signup'))
        
        # Generate new OTP
        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        mycon = get_db_connection()
        if not mycon:
            flash('Database connection failed. Please try again later.', 'error')
            return redirect(url_for('login_auth.verify_page'))
            
        cursor = mycon.cursor()
        cursor.execute(
            "UPDATE aqi_login_data SET otp = %s, otp_created_at = NOW() WHERE email = %s",
            (otp, email)
        )
        mycon.commit()
        cursor.close()
        mycon.close()
        
        # Send OTP email
        try:
            send_otp_email(email, otp, username)
            print(f"✓ OTP resent to {email}")
            flash('New OTP sent to your email!', 'success')
        except Exception as e:
            print(f"⚠ Failed to send OTP email: {e}")
            flash('Failed to send email. Please try again.', 'error')
        
        return redirect(url_for('login_auth.verify_page'))
        
    except Exception as e:
        print(f"❌ Resend OTP error: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('login_auth.verify_page'))


@login_auth.route('/login', methods=['POST', 'GET'])
def login():
    """Handle login request with proper redirect"""
    if request.method == 'GET':
        return redirect(url_for('login_auth.login_signup_page'))
    
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        redirect_to = data.get('redirect_to', '').strip()
        
        print(f"🔐 Login attempt: {email}, redirect_to: '{redirect_to}'")
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password required'}), 400
        
        mycon = get_db_connection()
        if not mycon:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 503
            
        cursor = mycon.cursor()
        cursor.execute("SELECT id, username, email, age, gender, city, password, is_verified FROM aqi_login_data WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        mycon.close()
        
        if not user:
            return jsonify({'success': False, 'message': 'Invalid email or password\nPlease Sign Up first'}), 401
        
        user_id, username, user_email, age, gender, city, hashed_password, is_verified = user
        
        if not check_password_hash(hashed_password, password):
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
        
        if not is_verified:
            session['verification_email'] = email
            return jsonify({
                'success': False, 
                'message': 'Please verify your email first',
                'redirect_to_verify': True
            }), 403
        
        # Set session
        session.permanent = True
        session['user_id'] = user_id
        session['username'] = username
        session['user_email'] = user_email
        session['user_age'] = age
        session['user_gender'] = gender
        session['user_city'] = city
        
        print(f"✅ Session created for: {username}")
        print(f'Session Data : {user_id}, {username}, {user_email}, {age}, {gender}, {city}')
        
        # FIXED: Better redirect handling
        redirect_url = '/'  # Default
        
        if redirect_to:
            # Direct page names
            if redirect_to == 'live_track':
                redirect_url = '/live_track'
            elif redirect_to == 'ai_advisor':
                redirect_url = '/ai_advisor'
            elif redirect_to == 'check_aqi':
                redirect_url = '/check_aqi'
            elif redirect_to == 'home':
                redirect_url = '/'
            # If it's already a full path (starts with /)
            elif redirect_to.startswith('/'):
                redirect_url = redirect_to
        
        print(f"✅ Redirecting to: {redirect_url}")
        
        return jsonify({
            'success': True, 
            'message': f'Welcome back, {username}!',
            'redirect': redirect_url,
            'user': {
                'user_id': user_id,
                'username': username,
                'email': user_email,
                'age': age,
                'gender': gender,
                'city': city
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Login failed'}), 500


@login_auth.route('/signup', methods=['POST'])
def signup():
    """Handle signup request"""
    try:
        data = request.get_json()
        
        username = data.get('username')
        email = data.get('email')
        age = data.get('age')
        gender = data.get('gender')
        city = data.get('city')
        password = data.get('password')
        
        if not all([username, email, age, gender, city, password]):
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        
        # Hash password
        hashed_password = generate_password_hash(password)
        
        # Generate OTP
        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        mycon = get_db_connection()
        if not mycon:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 503
            
        cursor = mycon.cursor()
        
        # Check if email already exists
        cursor.execute("SELECT email FROM aqi_login_data WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            mycon.close()
            return jsonify({'success': False, 'message': 'Email already registered'}), 409
        
        # Insert user
        cursor.execute(
            """INSERT INTO aqi_login_data (username, email, age, gender, city, password, otp, otp_created_at, is_verified) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), FALSE)""",
            (username, email, age, gender, city, hashed_password, otp)
        )
        mycon.commit()
        cursor.close()
        mycon.close()
        
        # Store email in session for verify page
        session['verification_email'] = email
        session['verification_username'] = username
        
        # Send OTP email
        try:
            send_otp_email(email, otp, username)
            print(f"✓ OTP sent to {email}")
        except Exception as e:
            print(f"⚠ Failed to send OTP email: {e}")
        
        return jsonify({
            'success': True, 
            'message': 'Registration successful! Please check your email for OTP.'
        }), 201
        
    except Exception as e:
        print(f"❌ Signup error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'An error occurred during registration'}), 500


@login_auth.route('/logout', methods=['POST', 'GET'])
def logout():
    """Handle logout"""
    session.clear()
    return redirect(url_for('login_auth.login_signup_page'))


def send_otp_email(email, otp, username):
    """Send OTP email using Flask-Mail"""
    from flask_mail import Message
    from flask import current_app
    from app import mail
    
    try:
        msg = Message(
            subject="Your OTP for AQI App Verification",
            recipients=[email],
            html=f"""
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
            .greeting {{
                font-size: 16px;
                color: #1f2937;
                margin-bottom: 20px;
            }}
            .otp-display {{
                text-align: center;
                padding: 30px;
                background: linear-gradient(135deg, #f0fdf4, #dcfce7);
                border-radius: 12px;
                margin: 25px 0;
            }}
            .otp-label {{
                font-size: 14px;
                font-weight: 600;
                color: #6b7280;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 15px;
            }}
            .otp-value {{
                font-size: 48px;
                font-weight: 900;
                color: #667eea;
                letter-spacing: 8px;
                margin: 0;
            }}
            .message-box {{
                background-color: #f9fafb;
                border-left: 4px solid #667eea;
                padding: 20px;
                margin: 25px 0;
                border-radius: 8px;
                color: #4b5563;
            }}
            .warning-box {{
                background: linear-gradient(135deg, #fef3c7, #fde68a);
                border-left: 4px solid #f59e0b;
                padding: 20px;
                margin: 25px 0;
                border-radius: 8px;
            }}
            .warning-box p {{
                margin: 0;
                color: #78350f;
                font-weight: 500;
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
                <h1>🔐 Email Verification</h1>
                <p>AQI Smart Health Advisor</p>
            </div>
            <div class="content">
                <div class="greeting">
                    <p>Hello <strong>{username}</strong>,</p>
                    <p>Welcome to AQI Smart Health Advisor! Please use the following one-time password to verify your email address.</p>
                </div>
                
                <div class="otp-display">
                    <div class="otp-label">Your Verification Code</div>
                    <div class="otp-value">{otp}</div>
                </div>
                
                <div class="message-box">
                    This OTP is valid for <strong>10 minutes</strong>. Please enter it in the verification page to complete your registration.
                </div>
                
                <div class="warning-box">
                    <p>⚠️ If you didn't request this verification code, please ignore this email. Your account remains secure.</p>
                </div>
            </div>
            <div class="footer">
                <p><strong>AQI Smart Health Advisor Team</strong></p>
                <p>Stay informed about air quality for better health decisions</p>
            </div>
        </div>
    </body>
    </html>
    """
        )
        mail.send(msg)
    except Exception as e:
        print(f"Error sending email: {e}")
        raise