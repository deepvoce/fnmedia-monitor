import sqlite3
import json
import os
import re
import shutil
import threading
import time
from datetime import datetime, timedelta
from functools import lru_cache
import requests
from flask import Flask, render_template, jsonify, request
from config import Config

app = Flask(__name__)
config = Config()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SRC_DB_PATH = config.FNMEDIA_DB_PATH
TMP_DB_PATH = os.path.join(BASE_DIR, "trimmedia_tmp.db")
DB_EXPIRATION_SECONDS = int(os.environ.get("DB_COPY_TTL", "60"))
_last_copy_time = 0.0
_db_copy_lock = threading.Lock()

def _atomic_copy_database():
    global _last_copy_time
    atomic_tmp_path = TMP_DB_PATH + ".new"
    if not os.path.exists(SRC_DB_PATH):
        print(f"Source DB not found: {SRC_DB_PATH}")
        return False
    if not os.access(SRC_DB_PATH, os.R_OK):
        print(f"Source DB not readable: {SRC_DB_PATH}")
        return False
    try:
        shutil.copy2(SRC_DB_PATH, atomic_tmp_path)
        os.replace(atomic_tmp_path, TMP_DB_PATH)
        _last_copy_time = time.time()
        return True
    except Exception as e:
        print(f"Database copy error: {e}")
        try:
            if os.path.exists(atomic_tmp_path):
                os.remove(atomic_tmp_path)
        except Exception:
            pass
        return False

def get_db_connection():
    is_expired = (time.time() - _last_copy_time) > DB_EXPIRATION_SECONDS
    if not os.path.exists(TMP_DB_PATH) or is_expired:
        with _db_copy_lock:
            is_still_expired = (time.time() - _last_copy_time) > DB_EXPIRATION_SECONDS
            if not os.path.exists(TMP_DB_PATH) or is_still_expired:
                _atomic_copy_database()
    try:
        conn = sqlite3.connect(f"file:{TMP_DB_PATH}?mode=ro", uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        try:
            conn = sqlite3.connect(f"file:{SRC_DB_PATH}?mode=ro", uri=True, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e2:
            print(f"Database fallback error: {e2}")
            return None

def parse_user_agent(ua):
    device = "未知"
    browser = "未知"
    os_info = "未知"
    
    ua = ua or ""
    ua_l = ua.lower()
    
    if "windows" in ua_l:
        os_info = "Windows"
        if "firefox" in ua_l:
            browser = "Firefox"
        elif "edg" in ua_l:
            browser = "Edge"
        elif "chrome" in ua_l:
            browser = "Chrome"
    elif "iphone" in ua_l:
        os_info = "iOS"
        device = "iPhone"
        if "safari" in ua_l and "chrome" not in ua_l:
            browser = "Safari"
        elif "chrome" in ua_l:
            browser = "Chrome"
    elif "ipad" in ua_l:
        os_info = "iOS"
        device = "iPad"
    elif "android" in ua_l:
        os_info = "Android"
        device = "手机"
        if "chrome" in ua_l:
            browser = "Chrome"
    elif "ios" in ua_l:
        os_info = "iOS"
        device = "手机"
        if "safari" in ua_l and "chrome" not in ua_l:
            browser = "Safari"
        elif "chrome" in ua_l:
            browser = "Chrome"
    elif "mac" in ua_l:
        os_info = "macOS"
        if "firefox" in ua_l:
            browser = "Firefox"
        elif "safari" in ua_l and "chrome" not in ua_l:
            browser = "Safari"
        elif "chrome" in ua_l:
            browser = "Chrome"
    elif "linux" in ua_l:
        os_info = "Linux"
    
    if not device or device == "未知":
        if "tv" in ua_l:
            device = "电视"
        elif "mobile" in ua_l:
            device = "手机"
            
    return {"device": device, "browser": browser, "os": os_info}

@lru_cache(maxsize=1000)
def get_ip_info(ip):
    if not ip or ip in ['127.0.0.1', 'localhost', '0.0.0.0']:
        return {"country": "本地", "region": "", "city": "", "isp": "本机", "lat": None, "lon": None}
    
    try:
        if config.IPINFO_TOKEN:
            response = requests.get(f"https://ipinfo.io/{ip}/json?token={config.IPINFO_TOKEN}", timeout=3)
            if response.status_code == 200:
                data = response.json()
                return {
                    "country": data.get("country", ""),
                    "region": data.get("region", ""),
                    "city": data.get("city", ""),
                    "isp": data.get("org", ""),
                    "lat": float(data.get("loc", "0,0").split(",")[0]) if data.get("loc") else None,
                    "lon": float(data.get("loc", "0,0").split(",")[1]) if data.get("loc") else None
                }
        
        response = requests.get(f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,isp,lat,lon", timeout=3)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return {
                    "country": data.get("country", ""),
                    "region": data.get("regionName", ""),
                    "city": data.get("city", ""),
                    "isp": data.get("isp", ""),
                    "lat": data.get("lat"),
                    "lon": data.get("lon")
                }
    except Exception as e:
        print(f"IP info error: {e}")
    
    return {"country": "", "region": "", "city": "", "isp": "", "lat": None, "lon": None}

def parse_nginx_log(log_line):
    # Support Lucky JSON log lines: {"ExtInfo":{...},"level":"info","msg":...}
    log_line = (log_line or "").strip()
    if not log_line:
        return None
    try:
        if log_line.startswith("{") and '"ExtInfo"' in log_line:
            data = json.loads(log_line)
            ext = data.get("ExtInfo") or {}
            return {
                "ip": ext.get("ClientIP", ""),
                "method": ext.get("Method", ""),
                "status": ext.get("Status", ""),
                "size": "",
                "path": ext.get("URL", ""),
                "ua": ext.get("UserAgent", ""),
                "time": "",
            }
    except Exception:
        pass
    pattern = (
        r'(?P<ip>\d+\.\d+\.\d+\.\d+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+'
        r'"(?P<method>\w+)\s+(?P<path>[^ ]+)\s+[^"]+"\s+(?P<status>\d+)\s+'
        r'(?P<size>\d+|-)\s+"(?P<referrer>[^"]*)"\s+"(?P<ua>[^"]*)"'
    )
    match = re.search(pattern, log_line)
    if match:
        return {
            "ip": match.group("ip"),
            "method": match.group("method"),
            "status": match.group("status"),
            "size": match.group("size"),
            "path": match.group("path"),
            "ua": match.group("ua"),
            "time": match.group("time"),
        }
    return None

def parse_log_time(time_str):
    if not time_str:
        return ""
    for fmt in ("%d/%b/%Y:%H:%M:%S %z", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(time_str, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    return time_str

def get_item_hierarchy(conn, item_guid, cache=None):
    if cache is None:
        cache = {}
    if item_guid in cache:
        return cache[item_guid]
    query = """
        WITH RECURSIVE item_hierarchy(guid, title, original_title, parent_guid, level) AS (
            SELECT guid, title, original_title, parent_guid, 0 as level
            FROM item 
            WHERE guid = ?
            UNION ALL
            SELECT i.guid, i.title, i.original_title, i.parent_guid, ih.level + 1
            FROM item i
            INNER JOIN item_hierarchy ih ON i.guid = ih.parent_guid
            WHERE ih.level < 10 AND i.guid IS NOT NULL
        )
        SELECT * FROM item_hierarchy ORDER BY level ASC
    """
    items = conn.execute(query, (item_guid,)).fetchall()
    hierarchy = []
    for item in items:
        hierarchy.append({
            "guid": item["guid"],
            "title": item["title"],
            "original_title": item["original_title"],
            "parent_guid": item["parent_guid"],
            "level": item["level"],
        })
    cache[item_guid] = hierarchy
    return hierarchy

def get_current_playing():
    conn = get_db_connection()
    if not conn:
        return []
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                p.item_guid,
                u.username,
                i.title,
                i.type,
                i.season_number,
                i.episode_number,
                i.parent_guid,
                p.ts,
                p.watched,
                p.resolution,
                p.update_time,
                i.runtime,
                ms.duration as media_duration,
                i.overview,
                i.vote_average,
                i.posters
            FROM item_user_play p
            JOIN user u ON p.user_guid = u.guid
            JOIN item i ON p.item_guid = i.guid
            LEFT JOIN media_stream ms ON p.media_guid = ms.guid AND ms.codec_type = 'video'
            WHERE p.update_time > ?
            AND p.visible = 1
            ORDER BY p.update_time DESC
            LIMIT 20
        """, (now_ms() - 300 * 1000,))
        
        results = []
        hierarchy_cache = {}
        for row in cursor.fetchall():
            hierarchy = get_item_hierarchy(conn, row["item_guid"], hierarchy_cache)
            display_title = row["title"]
            if row["season_number"] and row["episode_number"]:
                display_title = f"S{int(row['season_number']):02d}E{int(row['episode_number']):02d} - {row['title']}"
                if hierarchy:
                    display_title = f"{hierarchy[-1]['title']} - {display_title}"
            elif hierarchy and len(hierarchy) > 1:
                display_title = f"{hierarchy[-1]['title']} - {row['title']}"
            duration = row['media_duration'] or ((row['runtime'] or 0) * 60)
            position = row['ts'] or row['watched'] or 0
            position, duration = normalize_position_duration(position, duration)
            results.append({
                "user": row['username'],
                "title": display_title,
                "type": row['type'],
                "progress": round(min(100.0, (position or 0) / duration * 100), 1) if duration > 0 else 0,
                "position": format_duration(position or 0),
                "duration": format_duration(duration),
                "resolution": row['resolution'] or "",
                "size": "",
                "time": format_timestamp(row['update_time']),
                "overview": row['overview'] or "",
                "rating": row['vote_average'] or 0,
                "poster": ""
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
            p.item_guid,
            u.username,
            i.title,
            i.type,
            i.season_number,
            i.episode_number,
            i.parent_guid,
            p.ts,
            p.watched,
            p.resolution,
            p.create_time,
            p.update_time,
            i.runtime,
            ms.duration as media_duration,
            im.size as file_size,
            i.overview,
            i.vote_average
        FROM item_user_play p
        JOIN user u ON p.user_guid = u.guid
        JOIN item i ON p.item_guid = i.guid
        LEFT JOIN media_stream ms ON p.media_guid = ms.guid AND ms.codec_type = 'video'
        LEFT JOIN item_media im ON p.media_guid = im.guid
    """
    
    params = []
    where_clause = " WHERE p.visible = 1"
    if user_filter:
        where_clause += " AND u.username = ?"
        params.append(user_filter)

    query += where_clause + " ORDER BY p.update_time DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    
    results = []
    hierarchy_cache = {}
    for row in cursor.fetchall():
        hierarchy = get_item_hierarchy(conn, row["item_guid"], hierarchy_cache)
        display_title = row["title"]
        if row["season_number"] and row["episode_number"]:
            display_title = f"S{int(row['season_number']):02d}E{int(row['episode_number']):02d} - {row['title']}"
            if hierarchy:
                display_title = f"{hierarchy[-1]['title']} - {display_title}"
        elif hierarchy and len(hierarchy) > 1:
            display_title = f"{hierarchy[-1]['title']} - {row['title']}"
        duration = row['media_duration'] or ((row['runtime'] or 0) * 60)
        position = row['ts'] or row['watched'] or 0
        position, duration = normalize_position_duration(position, duration)
        results.append({
            "user": row['username'],
            "title": display_title,
            "type": row['type'],
            "category": "",
            "progress": round(min(100.0, (position or 0) / duration * 100), 1) if duration > 0 else 0,
            "position": format_duration(position or 0),
            "duration": format_duration(duration),
            "resolution": row['resolution'] or "",
            "size": format_size(row['file_size']) if row['file_size'] else "",
            "start_time": format_timestamp(row['create_time']),
            "end_time": format_timestamp(row['update_time']),
            "device": "未知",
            "overview": row['overview'] or "",
            "rating": row['vote_average'] or 0
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
        cursor.execute("SELECT COUNT(*) as count FROM user WHERE status = 1 AND guid != 'default-user-template'")
        stats['total_users'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(DISTINCT user_guid) as count FROM item_user_play WHERE visible = 1")
        stats['active_users'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM item_user_play WHERE visible = 1")
        stats['total_plays'] = cursor.fetchone()['count']
        
        today_start = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        cursor.execute(
            "SELECT COUNT(*) as count FROM item_user_play WHERE visible = 1 AND update_time >= ?",
            (today_start,),
        )
        stats['today_plays'] = cursor.fetchone()['count']
        
        cursor.execute("""
            SELECT SUM(watched) as total_watch_time 
            FROM item_user_play 
            WHERE visible = 1 AND update_time >= ?
        """, (today_start,))
        watch_time = cursor.fetchone()['total_watch_time'] or 0
        stats['today_watch_time'] = round(watch_time / 3600, 1)
        
        cursor.execute("""
            SELECT i.type, COUNT(*) as count 
            FROM item_user_play p
            JOIN item i ON p.item_guid = i.guid
            WHERE p.visible = 1 AND p.update_time >= ?
            GROUP BY i.type
        """, (now_ms() - 30 * 24 * 3600 * 1000,))
        stats['type_distribution'] = [{"type": r['type'], "count": r['count']} for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT u.username, COUNT(*) as count 
            FROM item_user_play p
            JOIN user u ON p.user_guid = u.guid
            WHERE p.visible = 1 AND p.update_time >= ?
            GROUP BY u.username
            ORDER BY count DESC
            LIMIT 10
        """, (now_ms() - 7 * 24 * 3600 * 1000,))
        stats['top_users'] = [{"user": r['username'], "count": r['count']} for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT i.title, COUNT(*) as count 
            FROM item_user_play p
            JOIN item i ON p.item_guid = i.guid
            WHERE p.visible = 1 AND p.update_time >= ?
            GROUP BY i.title
            ORDER BY count DESC
            LIMIT 10
        """, (now_ms() - 7 * 24 * 3600 * 1000,))
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
            strftime('%H', datetime(create_time / 1000, 'unixepoch')) as hour,
            COUNT(*) as count
        FROM item_user_play
        WHERE visible = 1 AND update_time >= ?
        GROUP BY hour
        ORDER BY hour
    """, (now_ms() - 7 * 24 * 3600 * 1000,))
    
    hourly = [0] * 24
    for row in cursor.fetchall():
        if row['hour']:
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

def normalize_position_duration(position, duration):
    if not position or not duration:
        return 0, duration or 0
    pos = float(position)
    dur = float(duration)
    # If position looks like ms relative to seconds duration, scale down.
    if dur > 0 and pos > dur * 10:
        pos = pos / 1000.0
    return pos, dur

def format_timestamp(ts):
    if not ts:
        return ""
    try:
        ts_int = int(ts)
        if ts_int > 1_000_000_000_000:
            ts_int = ts_int / 1000
        return datetime.fromtimestamp(ts_int).strftime("%Y-%m-%d %H:%M")
    except:
        return str(ts)

def now_ms():
    return int(time.time() * 1000)

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
    cursor.execute("SELECT DISTINCT username FROM user WHERE status = 1 AND guid != 'default-user-template' ORDER BY username")
    users = [r['username'] for r in cursor.fetchall()]
    conn.close()
    return jsonify(users)

@app.route('/api/logs')
def api_logs():
    if not config.LOG_ENABLED:
        return jsonify([])
    logs = []
    log_dir = config.LOG_PATH
    
    if os.path.exists(log_dir):
        for filename in os.listdir(log_dir):
            if filename.endswith('.log'):
                filepath = os.path.join(log_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()[-200:]
                        last_ts = ""
                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue
                            if re.match(r'^\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}$', line):
                                last_ts = line.replace("/", "-")
                                continue
                            parsed = parse_nginx_log(line)
                            if parsed:
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
                                    "time": parse_log_time(parsed.get("time")) or last_ts
                                })
                except Exception as e:
                    print(f"Log read error: {e}")
    
    logs.sort(key=lambda x: x['time'], reverse=True)
    return jsonify(logs[:100])

@app.route('/api/locations')
def api_locations():
    if not config.LOG_ENABLED:
        return jsonify([])
    logs = []
    log_dir = config.LOG_PATH
    if os.path.exists(log_dir):
        for filename in os.listdir(log_dir):
            if filename.endswith('.log'):
                filepath = os.path.join(log_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()[-500:]
                        last_ts = ""
                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue
                            if re.match(r'^\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}$', line):
                                last_ts = line.replace("/", "-")
                                continue
                            parsed = parse_nginx_log(line)
                            if parsed:
                                logs.append(parsed)
                except Exception as e:
                    print(f"Log read error: {e}")

    # Aggregate by city with geo coordinates
    agg = {}
    for entry in logs:
        ip = entry.get("ip", "")
        if not ip:
            continue
        ip_info = get_ip_info(ip)
        lat = ip_info.get("lat")
        lon = ip_info.get("lon")
        city = ip_info.get("city") or ip_info.get("region") or ip_info.get("country") or "未知"
        if lat is None or lon is None:
            continue
        key = f"{city}:{lat}:{lon}"
        agg[key] = {
            "city": city,
            "lat": lat,
            "lon": lon,
            "count": agg.get(key, {}).get("count", 0) + 1,
            "type": "default"
        }

    return jsonify(list(agg.values()))

@app.route('/api/favorites')
def api_favorites():
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                u.username,
                i.title,
                i.type,
                i.vote_average,
                i.posters,
                f.create_time
            FROM item_user_favorite f
            JOIN user u ON f.user_guid = u.guid
            JOIN item i ON f.item_guid = i.guid
            ORDER BY f.create_time DESC
            LIMIT 100
        """)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "user": row['username'],
                "title": row['title'],
                "type": row['type'],
                "rating": row['vote_average'] or 0,
                "add_time": format_timestamp(row['create_time'])
            })
        return jsonify(results)
    except Exception as e:
        print(f"Favorites error: {e}")
        return jsonify([])
    finally:
        conn.close()

@app.route('/api/downloads')
def api_downloads():
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                u.username,
                d.media_file,
                d.output_file,
                d.resolution,
                d.status,
                d.create_time
            FROM download_task d
            JOIN user u ON d.user_guid = u.guid
            ORDER BY d.create_time DESC
            LIMIT 100
        """)
        
        status_map = {0: "等待中", 1: "下载中", 2: "已完成", 3: "失败"}
        results = []
        for row in cursor.fetchall():
            results.append({
                "user": row['username'],
                "media_file": row['media_file'],
                "output_file": row['output_file'],
                "resolution": row['resolution'],
                "status": status_map.get(row['status'], "未知"),
                "create_time": format_timestamp(row['create_time'])
            })
        return jsonify(results)
    except Exception as e:
        print(f"Downloads error: {e}")
        return jsonify([])
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT, debug=False)
