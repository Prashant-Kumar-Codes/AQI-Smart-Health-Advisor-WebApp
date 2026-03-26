import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """
    Creates and returns a PostgreSQL database connection using psycopg2.
    """
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            database=os.getenv("POSTGRES_DB", "aqi_app_db"),
            port=os.getenv("POSTGRES_PORT", "5432")
        )
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return None

def get_db_cursor(conn, dict_cursor=False):
    """
    Returns a cursor for the given connection.
    If dict_cursor is True, it returns a RealDictCursor which returns rows as dictionaries.
    """
    if dict_cursor:
        return conn.cursor(cursor_factory=RealDictCursor)
    return conn.cursor()
