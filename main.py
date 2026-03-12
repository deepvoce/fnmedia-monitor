import sqlite3
import json
import os
import re
from datetime import datetime, timedelta
from functools import lru_cache
import requests
from flask import Flask, render_template, jsonify, request
from config import Config

app = Flask(__name__)
config = Config()

def get_db_connection():
    try:
        conn = sqlite3.connect(config.FNMEDIA_DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def parse_user_agent(ua):
    device = "未知"
    browser = "未知"
    os_info = "未知"
    
    ua = ua or ""
    
    if "Windows" in ua:
        os_info = "Windows"
        if "Firefox" in ua:
            browser = "Firefox"
        elif "Edg" in ua:
            browser = "Edge"
        elif "Chrome" in ua:
            browser = "Chrome"
    elif "Mac" in ua:
        os_info = "macOS"
        if "Firefox" in ua:
            browser = "Firefox"
        elif "Safari" in ua and "Chrome" not in ua:
            browser = "Safari"
        elif "Chrome" in ua:
            browser = "Chrome"
    elif "Linux" in ua:
        os_info = "Linux"
    elif "Android" in ua:
        os_info = "Android"
        device = "手机"
        if "Chrome" in ua:
            browser = "Chrome"
    elif "iPhone" in ua:
        os_info = "iOS"
        device = "iPhone"
        if "Safari" in ua and "Chrome" not in ua:
            browser = "Safari"
        elif "Chrome" in ua:
            browser = "Chrome"
    elif "iPad" in ua:
        os_info = "iOS"
        device = "iPad"
    
    if not device or device == "未知":
        if "TV" in ua or "tv" in ua:
            device = "电视"
        elif "Mobile" in ua:
            device = "手机"
            
    return {"device": device, "browser": browser, "os": os_info}

@lru_cache(maxsize=1000)
def get_ip_info(ip):
    if not ip or ip in ['127.0.0.1', 'localhost', '0.0.0.0']:
        return {"country": "本地", "region": "", "city": "", "isp": "本机"}
    
    try:
        if config.IPINFO_TOKEN:
            response = requests.get(f"https://ipinfo.io/{ip}/json?token={config.IPINFO_TOKEN}", timeout=3)
            if response.status_code == 200:
                data = response.json()
                return {
                    "country": data.get("country", ""),
                    "region": data.get("region", ""),
                    "city": data.get("city", ""),
                    "isp": data.get("org", "")
                }
        
        response = requests.get(f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,isp", timeout=3)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return {
                    "country": data.get("country", ""),
                    "region": data.get("regionName", ""),
                    "city": data.get("city", ""),
                    "isp": data.get("isp", "")
                }
    except Exception as e:
        print(f"IP info error: {e}")
    
    return {"country": "", "region": "", "city": "", "isp": ""}

def parse_nginx_log(log_line):
    pattern = r'(\d+\.\d+\.\d+\.\d+).*?"(\w+) /.*?" (\d+) (\d+) "([^"]*)" "([^"]*)"'
    match = re.search(pattern, log_line)
    if match:
        ip = match.group(1)
        method = match.group(2)
        status = match.group(3)
        size = match.group(4)
        path = match.group(5)
        ua = match.group(6)
        return {"ip": ip, "method": method, "status": status, "size": size, "path": path, "ua": ua}
    return None

def get_current_playing():
    conn = get_db_connection()
    if not conn:
        return []
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                u.username,
                m.title,
                m.type,
                pl.current_position,
                pl.total_duration,
                m.resolution,
                m.file_size,
                pl.updated_at
            FROM play_log pl
            JOIN user u ON pl.user_id = u.id
            JOIN media m ON pl.media_id = m.id
            WHERE pl.updated_at > datetime('now', '-5 minutes')
            ORDER BY pl.updated_at DESC
            LIMIT 20
        """)
        
        results = []
        for row in cursor.fetchall():
            progress = (row['current_position'] / row['total_duration'] * 100) if row['total_duration'] else 0
            results.append({
                "user": row['username'],
                "title": row['title'],
                "type": row['type'],
                "progress": round(progress, 1),
                "position": format_duration(row['current_position']),
                "duration": format_duration(row['total_duration']),
                "resolution": row['resolution'] or "",
                "size": format_size(row['file_size']),
                "time": row['updated_at']
            })
        return results
    except Exception as e:
        print(f"Error getting current playing: {e}")
        return []
    finally:
        conn.close()

def get_play_history(limit=100, user_filter=None):
    conn = get_db_connection()
    if not conn:
        return []
    
    cursor = conn.cursor()
    query = """
        SELECT 
            u.username,
            m.title,
            m.type,
            m.category,
            pl.current_position,
            pl.total_duration,
            m.resolution,
            m.file_size,
            pl.created_at,
            pl.updated_at
        FROM play_log pl
        JOIN user u ON pl.user_id = u.id
        JOIN media m ON pl.media_id = m.id
    """
    
    if user_filter:
        query += f" WHERE u.username = '{user_filter}'"
    
    query += " ORDER BY pl.updated_at DESC LIMIT ?"
    
    cursor.execute(query, (limit,))
    
    results = []
    for row in cursor.fetchall():
        progress = (row['current_position'] / row['total_duration'] * 100) if row['total_duration'] else 0
        results.append({
            "user": row['username'],
            "title": row['title'],
            "type": row['type'],
            "category": row['category'] or "",
            "progress": round(progress, 1),
            "position": format_duration(row['current_position']),
            "duration": format_duration(row['total_duration']),
            "resolution": row['resolution'] or "",
            "size": format_size(row['file_size']),
            "start_time": row['created_at'],
            "end_time": row['updated_at'],
            "device": "手机"
        })
    conn.close()
    return results

def get_stats():
    conn = get_db_connection()
    if not conn:
        return {}
    
    cursor = conn.cursor()
    stats = {}
    
    try:
        cursor.execute("SELECT COUNT(*) as count FROM user")
        stats['total_users'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM play_log WHERE updated_at > datetime('now', '-24 hours')")
        stats['active_users'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM play_log")
        stats['total_plays'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM play_log WHERE created_at > datetime('now', '-24 hours')")
        stats['today_plays'] = cursor.fetchone()['count']
        
        cursor.execute("""
            SELECT SUM(total_duration - current_position) as total 
            FROM play_log 
            WHERE updated_at > datetime('now', '-24 hours')
        """)
        row = cursor.fetchone()
        stats['today_watch_time'] = round((row['total'] or 0) / 3600, 1)
        
        cursor.execute("""
            SELECT m.type, COUNT(*) as count 
            FROM play_log pl
            JOIN media m ON pl.media_id = m.id
            WHERE pl.created_at > datetime('now', '-30 days')
            GROUP BY m.type
        """)
        stats['type_distribution'] = [{"type": r['type'], "count": r['count']} for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT u.username, COUNT(*) as count 
            FROM play_log pl
            JOIN user u ON pl.user_id = u.id
            WHERE pl.created_at > datetime('now', '-7 days')
            GROUP BY u.username
            ORDER BY count DESC
            LIMIT 10
        """)
        stats['top_users'] = [{"user": r['username'], "count": r['count']} for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT m.title, COUNT(*) as count 
            FROM play_log pl
            JOIN media m ON pl.media_id = m.id
            WHERE pl.created_at > datetime('now', '-7 days')
            GROUP BY m.title
            ORDER BY count DESC
            LIMIT 10
        """)
        stats['top_content'] = [{"title": r['title'], "count": r['count']} for r in cursor.fetchall()]
        
    except Exception as e:
        print(f"Stats error: {e}")
    
    conn.close()
    return stats

def get_hourly_stats():
    conn = get_db_connection()
    if not conn:
        return []
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            strftime('%H', created_at) as hour,
            COUNT(*) as count
        FROM play_log
        WHERE created_at > datetime('now', '-7 days')
        GROUP BY hour
        ORDER BY hour
    """)
    
    hourly = [0] * 24
    for row in cursor.fetchall():
        hourly[int(row['hour'])] = row['count']
    
    conn.close()
    return hourly

def format_duration(seconds):
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def format_size(bytes_val):
    if not bytes_val:
        return ""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f}TB"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats')
def api_stats():
    return jsonify(get_stats())

@app.route('/api/current')
def api_current():
    return jsonify(get_current_playing())

@app.route('/api/history')
def api_history():
    user_filter = request.args.get('user', None)
    limit = request.args.get('limit', 100, type=int)
    return jsonify(get_play_history(limit, user_filter))

@app.route('/api/hourly')
def api_hourly():
    return jsonify(get_hourly_stats())

@app.route('/api/users')
def api_users():
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT username FROM user ORDER BY username")
    users = [r['username'] for r in cursor.fetchall()]
    conn.close()
    return jsonify(users)

@app.route('/api/logs')
def api_logs():
    logs = []
    log_dir = config.LOG_PATH
    
    if os.path.exists(log_dir):
        for filename in os.listdir(log_dir):
            if filename.endswith('.log'):
                filepath = os.path.join(log_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()[-50:]
                        for line in lines:
                            parsed = parse_nginx_log(line)
                            if parsed and '/api/' in parsed['path']:
                                ip_info = get_ip_info(parsed['ip'])
                                ua_info = parse_user_agent(parsed['ua'])
                                logs.append({
                                    "ip": parsed['ip'],
                                    "country": ip_info.get('country', ''),
                                    "region": ip_info.get('region', ''),
                                    "city": ip_info.get('city', ''),
                                    "isp": ip_info.get('isp', ''),
                                    "device": ua_info.get('device', ''),
                                    "browser": ua_info.get('browser', ''),
                                    "os": ua_info.get('os', ''),
                                    "path": parsed['path'],
                                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                })
                except Exception as e:
                    print(f"Log read error: {e}")
    
    logs.sort(key=lambda x: x['time'], reverse=True)
    return jsonify(logs[:100])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT, debug=False)
