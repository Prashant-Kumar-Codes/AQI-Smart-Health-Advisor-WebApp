from flask import Blueprint, render_template, request, session, flash, redirect, url_for, jsonify
import mysql.connector
from flask_mail import Message
from app import mail
from datetime import datetime, timedelta
import random

auth = Blueprint('auth', __name__)

# Database connection
mycon_obj = mysql.connector.connect(
    host='localhost',
    user='root',
    password='admin123',
    database='college_placement_database'
)

cursor_auth = mycon_obj.cursor(dictionary=True)

# Constants
OTP_EXPIRY = 60
RESEND_INTERVAL = 60
STALE_ACCOUNT_SECONDS = 3600

# Cleanup function
def cleanup_stale_unverified():
    cutoff = datetime.now() - timedelta(seconds=STALE_ACCOUNT_SECONDS)
    try:
        cursor_auth.execute(
            "DELETE FROM login_data WHERE is_verified=0 AND otp_created_at IS NOT NULL AND otp_created_at < %s",
            (cutoff,)
        )
        mycon_obj.commit()
    except Exception:
        pass

def parse_db_datetime(val):
    """Return a datetime from DB value (handles str or datetime)."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(val.split('.')[0], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

# Main route - render SPA
@auth.route('/login-signup', methods=['GET'])
def login_signup_page():
    """Render the single-page auth application"""
    return render_template('auth/login.html')

# Signup route (API endpoint)
@auth.route('/signup', methods=['POST'])
def signup():
    try:
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', '').strip()

        # Validate inputs
        if not all([username, email, password, role]):
            flash("All fields are required.", "danger")
            return redirect(url_for('auth.login_signup_page'))

        if role not in ['student', 'mentor', 'placement', 'industry']:
            flash("Invalid role selected.", "danger")
            return redirect(url_for('auth.login_signup_page'))

        # Check if email already exists
        cursor_auth.execute('SELECT email, is_verified FROM login_data WHERE email=%s', (email,))
        existing_user = cursor_auth.fetchone()

        if existing_user:
            if existing_user['is_verified'] == 0:
                # Delete unverified account and allow re-signup
                cursor_auth.execute("DELETE FROM login_data WHERE email=%s", (email,))
                mycon_obj.commit()
                flash('Previous attempt was incomplete. Please try again.', "info")
            else:
                flash("Email already registered. Please login.", "warning")
                return redirect(url_for('auth.login_signup_page'))

        # Generate OTP
        otp = str(random.randint(100000, 999999))
        now = datetime.utcnow()

        try:
            # Send OTP
            msg = Message(
                'Your OTP Verification Code',
                sender='pkthisisfor1234@gmail.com',
                recipients=[email]
            )
            msg.body = f'Your OTP is {otp}\n\nThis OTP will expire in 60 seconds.'
            mail.send(msg)

            # Insert into database
            cursor_auth.execute(
                "INSERT INTO login_data (username, email, password, role, otp, otp_created_at, is_verified) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (username, email, password, role, otp, now, 0)
            )
            mycon_obj.commit()

            session['user_email'] = email
            flash("OTP sent to your email. Please verify.", "success")
            return redirect(url_for('auth.verify'))

        except Exception as e:
            flash(f"Error sending OTP: {str(e)}", "danger")
            return redirect(url_for('auth.login_signup_page'))

    except Exception as e:
        flash(f"Signup error: {str(e)}", "danger")
        return redirect(url_for('auth.login_signup_page'))


# Login route (API endpoint)
@auth.route('/login', methods=['POST'])
def login():
    try:
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        print(email, password)

        if not email or not password:
            flash("Email and password are required.", "danger")
            return redirect(url_for('auth.login_signup_page'))

        # Check if user exists and password matches
        cursor_auth.execute(
            "SELECT * FROM login_data WHERE email=%s AND password=%s",
            (email, password)
        )
        user = cursor_auth.fetchone()

        print(user)

        if user:
            if user['is_verified'] == 1:
                session['user_email'] = user['email']
                session['user_role'] = user['role']
                session['user'] = user['username']

                print(session['user'])

                try:
                    if user['unique_id'] == 'null':
                        print('\ninside try --\n', user['user'])
                        unique_id = user['user'][0:3] + str(random.randint(10000,99999))
                        cursor_auth.execute(
                            "INSERT INTO login_data SET unique_id = %s where email = %s",
                            (unique_id,user['email'])
                        )
                        session['unique_id'] = unique_id

                        print(session['unique_id'])

                    else:
                        session['unique_id'] = user['unique_id']
                except:
                    flash('unique_id cannot be provided','danger')

                flash("Login successful!", "success")

                # Redirect based on role
                if user['role'] == 'student':
                    return render_template('auth/dashboard.html')
                    #return redirect(url_for('auth.dashboard'))
                elif user['role'] == 'mentor':
                    return redirect(url_for('auth.mentor_dashboard'))
                elif user['role'] == 'placement':
                    return redirect(url_for('auth.placement_dashboard'))
                elif user['role'] == 'industry':
                    return redirect(url_for('auth.industry_dashboard'))
                else:
                    flash('Invalid role. Contact support.', 'warning')
                    return redirect(url_for('auth.login_signup_page'))
            else:
                flash("Please verify your account first.", "warning")
                session['user_email'] = email
                return redirect(url_for('auth.verify'))
        else:
            flash("Invalid email or password.", "danger")
            return redirect(url_for('auth.login_signup_page'))

    except Exception as e:
        flash(f"Login error: {str(e)}", "danger")
        return redirect(url_for('auth.login_signup_page'))

# Verify route
@auth.route('/verify', methods=['GET', 'POST'])
def verify():
    email = session.get('user_email')
    if not email:
        flash("Session expired. Please sign up again.", "danger")
        cleanup_stale_unverified()
        return redirect(url_for('auth.login_signup_page'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip()
        if not entered_otp:
            flash("Please enter the OTP.", "danger")
            return redirect(url_for('auth.verify'))

        cursor_auth.execute("SELECT * FROM login_data WHERE email=%s", (email,))
        user = cursor_auth.fetchone()

        if not user or not user.get('otp') or not user.get('otp_created_at'):
            flash("Invalid OTP or session. Please request a new one.", "danger")
            return redirect(url_for('auth.resend_otp'))

        try:
            # Parse OTP creation time
            otp_created_at = user['otp_created_at']
            if isinstance(otp_created_at, str):
                otp_created_at = datetime.strptime(otp_created_at, "%Y-%m-%d %H:%M:%S")

            expiry_time = otp_created_at + timedelta(seconds=60)

            if datetime.utcnow() > expiry_time:
                flash("OTP expired. Please request a new one.", "warning")
                return redirect(url_for('auth.resend_otp'))

            if user['otp'] == entered_otp:
                cursor_auth.execute(
                    "UPDATE login_data SET is_verified = 1, otp = NULL, otp_created_at = NULL WHERE email = %s",
                    (email,)
                )
                mycon_obj.commit()
                flash("Account verified successfully! You can now log in.", "success")
                session.pop('user_email', None)


                return redirect(url_for('auth.login_signup_page'))
            else:
                flash("Invalid OTP. Please try again.", "danger")
                return redirect(url_for('auth.verify'))

        except Exception as e:
            flash("An error occurred. Please try again.", "danger")
            return redirect(url_for('auth.verify'))
    


    # GET request - show verify page
    remaining = 0
    try:
        cursor_auth.execute("SELECT otp_created_at FROM login_data WHERE email=%s", (email,))
        data = cursor_auth.fetchone()
        if data and data['otp_created_at']:
            otp_created_at = data['otp_created_at']
            if isinstance(otp_created_at, str):
                otp_created_at = datetime.strptime(otp_created_at, "%Y-%m-%d %H:%M:%S")

            expiry_time = otp_created_at + timedelta(seconds=60)
            remaining = max(0, int((expiry_time - datetime.utcnow()).total_seconds()))
    except Exception:
        remaining = 0
        cleanup_stale_unverified()

    return render_template('auth/verify.html', remaining=remaining)

# Resend OTP route
@auth.route('/resend_otp', methods=['POST'])
def resend_otp():
    email = session.get('user_email')
    if not email:
        flash("Session expired. Please sign up again.", "danger")
        return redirect(url_for('auth.login_signup_page'))

    cursor_auth.execute("SELECT otp_created_at FROM login_data WHERE email=%s", (email,))
    data = cursor_auth.fetchone()

    if data and data['otp_created_at']:
        otp_created_at = data['otp_created_at']
        if isinstance(otp_created_at, str):
            otp_created_at = datetime.strptime(otp_created_at, "%Y-%m-%d %H:%M:%S")

        resend_time = otp_created_at + timedelta(seconds=60)
        if datetime.utcnow() < resend_time:
            flash("Please wait before requesting a new OTP.", "warning")
            return redirect(url_for('auth.verify'))

    # Generate and save new OTP
    otp = str(random.randint(100000, 999999))
    otp_created_at = datetime.utcnow()
    try:
        cursor_auth.execute(
            "UPDATE login_data SET otp=%s, otp_created_at=%s WHERE email=%s",
            (otp, otp_created_at, email)
        )
        mycon_obj.commit()

        msg = Message(
            'Your New OTP Code',
            sender='pkthisisfor1234@gmail.com',
            recipients=[email]
        )
        msg.body = f'Your new OTP is {otp}'
        mail.send(msg)

        flash("New OTP sent successfully!", "success")
    except Exception as e:
        flash("Failed to send new OTP. Please try again.", "danger")

    return redirect(url_for('auth.verify'))

# Logout route
@auth.route('/logout')
def logout():
    session.pop('user_email', None)
    session.pop('user_role', None)
    flash("Logged out successfully.", "info")
    return redirect(url_for('auth.login_signup_page'))

# Placeholder dashboard routes
@auth.route('/student_dashboard')
def student_dashboard():
    if 'user_email' not in session:
        return redirect(url_for('auth.login_signup_page'))
    print('Current session user is : ', session['user_email'], session['user_role'])
    # return render_template('auth/student_dashboard.html', unique_id = session['unique_id'], username = session['user'], email = session['user_email'])
    return render_template('auth/student_dashboard.html', username = session['user'], email = session['user_email'])

@auth.route('/mentor_dashboard')
def mentor_dashboard():
    if 'user_email' not in session:
        return redirect(url_for('auth.login_signup_page'))
    return render_template('dashboards/mentor_dashboard.html')

@auth.route('/placement_dashboard')
def placement_dashboard():
    if 'user_email' not in session:
        return redirect(url_for('auth.login_signup_page'))
    return render_template('dashboards/placement_dashboard.html')

@auth.route('/industry_dashboard')
def industry_dashboard():
    if 'user_email' not in session:
        return redirect(url_for('auth.login_signup_page'))
    return render_template('dashboards/industry_dashboard.html')
