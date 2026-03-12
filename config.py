import os

class Config:
    FNMEDIA_DB_PATH = os.environ.get('FNMEDIA_DB_PATH', '/app/database/fnmedia.db')
    LOG_PATH = os.environ.get('LOG_PATH', '/app/logs')
    PORT = int(os.environ.get('PORT', 5000))
    IPINFO_TOKEN = os.environ.get('IPINFO_TOKEN', '')
    REFRESH_INTERVAL = int(os.environ.get('REFRESH_INTERVAL', 30))
