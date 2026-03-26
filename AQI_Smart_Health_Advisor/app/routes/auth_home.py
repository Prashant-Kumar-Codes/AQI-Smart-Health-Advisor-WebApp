from .extensions import *
from app.db import get_db_connection

home_auth = Blueprint('home_auth', __name__)

def get_active_user_count():
    """
    Fetch the total number of registered users from the database
    Returns: Integer count of users
    """
    try:
        conn = get_db_connection()
        if not conn:
            return 0
        cursor_home_auth = conn.cursor()
        # Fixed SQL query - removed space in table name
        query = 'SELECT COUNT(id) FROM login_data;'
        cursor_home_auth.execute(query)
        result = cursor_home_auth.fetchone()
        cursor_home_auth.close()
        conn.close()
        
        # Extract count from result tuple
        user_count = result[0] if result else 0
        return user_count
    except Exception as e:
        print(f"Error fetching user count: {e}")
        return 0  # Return 0 if there's an error

def format_user_count(count):
    """
    Format the user count for display (e.g., 1234 -> "1.2K+")
    """
    if count >= 1000:
        return f"{count / 1000:.1f}K+"
    return str(count)

@home_auth.route('/aqi_homepage', methods=['GET'])
def aqi_homepage():
    # Get the actual count
    user_count = get_active_user_count()
    # Format it for display
    formatted_count = format_user_count(user_count)
    
    # Pass the formatted count to template
    return render_template('auth/homepage.html', active_users=formatted_count)