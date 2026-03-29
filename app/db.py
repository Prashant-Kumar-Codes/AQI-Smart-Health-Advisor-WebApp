import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """Get PostgreSQL connection using DATABASE_URL or individual parameters"""
    try:
        # Try using DATABASE_URL first (preferred for Render compatibility)
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            # Extract connection parameters from DATABASE_URL
            from urllib.parse import urlparse
            parsed = urlparse(database_url)
            conn = psycopg2.connect(
                host     = parsed.hostname,
                port     = parsed.port or 5432,
                user     = parsed.username,
                password = parsed.password,
                database = parsed.path.lstrip('/'),
                # sslmode is required for external connections to Render Postgres
                sslmode  = 'require' if 'render.com' in (parsed.hostname or '') or 'dpg-' in (parsed.hostname or '') else 'prefer'
            )
            print('Database connected successfully - Database Url')
            return conn
    except Exception as e:
        print(f"⚠️  DATABASE_URL parsing failed: {e}. Falling back to individual parameters.")
    
    # Fallback to individual parameters
    try:
        host = os.getenv("POSTGRES_HOST")
        database = os.getenv("POSTGRES_DB") # The user used POSTGRES_DATABASE in their example, but they have POSTGRES_DB in .env
        user = os.getenv("POSTGRES_USER")
        password = os.getenv("POSTGRES_PASSWORD")
        port = int(os.getenv("POSTGRES_PORT", 5432))
        
        # Determine sslmode
        # External hostnames for Render often contain "render.com" or the "dpg-" prefix
        sslmode = 'require' if host and ('render.com' in host or 'dpg-' in host) else 'prefer'
        
        conn = psycopg2.connect(
            host     = host,
            port     = port,
            user     = user,
            password = password,
            database = database,
            sslmode  = sslmode
        )
        print('Database connected successfully - Individual Parameters')
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None # Return None and let the caller handle it or raise inside.
        # But wait, common practice in this app seems to be returning None and then erroring.
        # I'll return None for consistency with previous version, but the user is seeing 
        # 'NoneType' object has no attribute 'cursor' elsewhere so we should probably handle that too.

def get_db_cursor(conn, dict_cursor=False):
    """
    Returns a cursor for the given connection.
    If dict_cursor is True, it returns a RealDictCursor which returns rows as dictionaries.
    """
    if not conn:
        return None
    
    if dict_cursor:
        return conn.cursor(cursor_factory=RealDictCursor)
    return conn.cursor()
