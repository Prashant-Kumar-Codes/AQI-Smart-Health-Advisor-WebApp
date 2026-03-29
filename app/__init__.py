from flask import Flask
from flask_socketio import SocketIO
from flask_mail import Mail
from dotenv import load_dotenv
from datetime import timedelta
import os
from app.config.config import Config

socketio = SocketIO()
mail = Mail()
load_dotenv()

def create_app():
    app = Flask(__name__,
                static_folder='static',
                template_folder='templates')
    
    # ========== SESSION CONFIGURATION ==========
    app.secret_key = os.getenv("SECRET_KEY")
    
    app.config.from_object(Config)

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