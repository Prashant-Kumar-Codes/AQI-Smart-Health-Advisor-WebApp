from flask import Flask
from flask_socketio import SocketIO
from flask_mail import Mail
from dotenv import load_dotenv
from datetime import timedelta
import os

socketio = SocketIO()
mail = Mail()
load_dotenv()

def create_app():
    app = Flask(__name__,
                static_folder='static',
                template_folder='templates')
    
    # ========== SESSION CONFIGURATION ==========
    app.secret_key = os.getenv("SECRET_KEY")
    
    # IMPORTANT: Configure session to be permanent and last longer
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Sessions last 7 days
    app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
    app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access to session cookie
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
    #app.config['SESSION_REFRESH_EACH_REQUEST'] = True  # Refresh session on each request
    
    # ========== POSTGRESQL CONFIGURATION ==========
    app.config['POSTGRES_HOST'] = os.getenv("POSTGRES_HOST")
    app.config['POSTGRES_USER'] = os.getenv("POSTGRES_USER", "postgres")
    app.config['POSTGRES_PASSWORD'] = os.getenv("POSTGRES_PASSWORD")
    app.config['POSTGRES_DB'] = os.getenv("POSTGRES_DB")
    app.config['POSTGRES_PORT'] = os.getenv("POSTGRES_PORT")
    
    # ========== MAIL CONFIGURATION ==========
    # Brevo SMTP config
    app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
    app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT", 587))
    app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS", "True") == "True"
    app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
    app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER")
    mail.init_app(app)
    
    # socketio.init_app(app, cors_allowed_origins="*")
    
    # ========== IMPORT BLUEPRINTS ==========
    from app.routes.auth_home import home_auth
    app.register_blueprint(home_auth)
    
    from app.routes.auth_login import login_auth
    app.register_blueprint(login_auth)
    
    from app.routes.auth_checkAqi import checkAqi_auth
    app.register_blueprint(checkAqi_auth)
    
    from app.routes.auth_learnMore import learnMore_auth
    app.register_blueprint(learnMore_auth)
    
    from app.routes.auth_about import about_auth
    app.register_blueprint(about_auth)
    
    from app.routes.auth_ai_advisor import ai_advisor_auth
    app.register_blueprint(ai_advisor_auth)
    
    from app.routes.auth_live_track import live_track_auth
    app.register_blueprint(live_track_auth)
    
    from app.routes.locationService import geocode_blueprint
    app.register_blueprint(geocode_blueprint)
    
    from app.location_api import location_api
    app.register_blueprint(location_api)
    
    return app