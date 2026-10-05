"""Environment-driven configuration for the local organizer."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///organizer.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('APP_ENV') == 'production'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    MAX_CONTENT_LENGTH = 1024 * 1024
    # Comma-separated roots approved by the machine owner. Defaults to isolated demo.
    ORGANIZER_ROOTS = [Path(p).expanduser().resolve() for p in
                       os.getenv('ORGANIZER_ROOTS', str(ROOT / 'demo_files' / 'sample_downloads')).split(',') if p]
    PROTECTED_PATHS = [ROOT / 'app', ROOT / 'instance', ROOT / 'tests', ROOT / '.git', ROOT / '.venv']
    MAX_SCAN_FILES = 5000
    PREVIEW_TTL_SECONDS = 1800
