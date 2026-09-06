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

APP_VERSION = "v2.1"
_START_TIME = time.time()


# ========== 缓存层 ==========
_log_cache = {"data": None, "time": 0, "lock": threading.Lock()}
_locations_cache = {"data": None, "time": 0, "lock": threading.Lock()}
_stats_cache = {"data": None, "time": 0, "lock": threading.Lock()}
_cache_ttl = int(os.environ.get("CACHE_TTL", "30"))  # API响应缓存秒数

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
        # 优先用 SQLite backup API：对 WAL 模式下的热库也能拿到一致快照，
        # 直接 copy 文件可能复制到半写入状态
        src = sqlite3.connect(f"file:{SRC_DB_PATH}?mode=ro", uri=True)
        dst = sqlite3.connect(atomic_tmp_path)
        try:
            with dst:
                src.backup(dst)
        finally:
            src.close()
            dst.close()
        os.replace(atomic_tmp_path, TMP_DB_PATH)
        _last_copy_time = time.time()
        return True
    except Exception as e:
        print(f"SQLite backup failed, fallback to file copy: {e}")
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
            response = requests.get(f"https://ipinfo.io/{ip}/json?token={config.IPINFO_TOKEN}", timeout=2)
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
        
        response = requests.get(f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,isp,lat,lon", timeout=2)
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


# 访客日志里跳过静态资源请求，只保留有分析价值的页面/API 访问
def _is_noise_path(path):
    p = path or ""
    return p.startswith("/static/") or p == "/favicon.ico"


def tail_lines(filepath, max_bytes=256 * 1024):
    """只读取文件末尾 max_bytes 字节并按行返回，避免大日志文件整读进内存"""
    try:
        size = os.path.getsize(filepath)
        with open(filepath, "rb") as f:
            if size > max_bytes:
                f.seek(-max_bytes, os.SEEK_END)
            data = f.read()
        lines = data.decode("utf-8", errors="ignore").splitlines()
        # 首行可能被截断，丢弃
        if size > max_bytes and lines:
            lines = lines[1:]
        return lines
    except Exception as e:
        print(f"Log tail read error: {e}")
        return []


# ========== 批量层级查询（替代逐条递归） ==========
def get_items_hierarchy_batch(conn, item_guids):
    """一次性批量查询所有 item 的层级关系，大幅减少递归调用"""
    if not item_guids:
        return {}
    
    placeholders = ",".join(["?"] * len(item_guids))
    all_rows = conn.execute(f"""
        WITH RECURSIVE item_hierarchy(guid, title, original_title, parent_guid, level, root_guid) AS (
            SELECT guid, title, original_title, parent_guid, 0 as level, guid as root_guid
            FROM item
            WHERE guid IN ({placeholders})
            UNION ALL
            SELECT i.guid, i.title, i.original_title, i.parent_guid, ih.level + 1, ih.root_guid
            FROM item i
            INNER JOIN item_hierarchy ih ON i.guid = ih.parent_guid
            WHERE ih.level < 10 AND i.guid IS NOT NULL
        )
        SELECT root_guid, guid, title, original_title, parent_guid, level
        FROM item_hierarchy
        ORDER BY root_guid, level ASC
    """, tuple(item_guids)).fetchall()
    
    result = {guid: [] for guid in item_guids}
    current_guid = None
    for row in all_rows:
        if row["root_guid"] != current_guid:
            current_guid = row["root_guid"]
        result[current_guid].append({
            "guid": row["guid"],
            "title": row["title"],
            "original_title": row["original_title"],
            "parent_guid": row["parent_guid"],
            "level": row["level"],
        })
    
    return result

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
        
        rows = cursor.fetchall()
        if not rows:
            return []
        
        # 批量获取层级关系（优化）
        item_guids = [row["item_guid"] for row in rows]
        hierarchy_map = get_items_hierarchy_batch(conn, item_guids)
        
        results = []
        for row in rows:
            hierarchy = hierarchy_map.get(row["item_guid"], [])
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
    
    rows = cursor.fetchall()
    if not rows:
        conn.close()
        return []
    
    # 批量获取层级关系（优化）
    item_guids = list(set(row["item_guid"] for row in rows))
    hierarchy_map = get_items_hierarchy_batch(conn, item_guids)
    
    results = []
    for row in rows:
        hierarchy = hierarchy_map.get(row["item_guid"], [])
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
    # 检查缓存
    with _stats_cache["lock"]:
        if _stats_cache["data"] and (time.time() - _stats_cache["time"]) < _cache_ttl:
            return _stats_cache["data"]

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
            SELECT i.guid, i.title, i.type, COUNT(*) as count
            FROM item_user_play p
            JOIN item i ON p.item_guid = i.guid
            WHERE p.visible = 1 AND p.update_time >= ?
            GROUP BY i.guid
            ORDER BY count DESC
            LIMIT 10
        """, (now_ms() - 7 * 24 * 3600 * 1000,))
        # 剧集按 guid 分组后，用剧集名作前缀，避免不同剧的同名集（如"第1集"）被合并
        top_rows = cursor.fetchall()
        hierarchy_map = get_items_hierarchy_batch(
            conn, [r['guid'] for r in top_rows]) if top_rows else {}
        top_content = []
        for r in top_rows:
            title = r['title']
            hierarchy = hierarchy_map.get(r['guid'], [])
            if hierarchy and len(hierarchy) > 1:
                root = hierarchy[-1]['title']
                if root and root != title:
                    title = f"{root} · {title}"
            top_content.append({"title": title, "count": r['count']})
        stats['top_content'] = top_content

        # 播放时长分布（近7天，按单次观看秒数分桶）
        week_ago = now_ms() - 7 * 24 * 3600 * 1000
        cursor.execute("""
            SELECT
                SUM(CASE WHEN watched < 1800 THEN 1 ELSE 0 END) as b0,
                SUM(CASE WHEN watched >= 1800 AND watched < 3600 THEN 1 ELSE 0 END) as b1,
                SUM(CASE WHEN watched >= 3600 AND watched < 7200 THEN 1 ELSE 0 END) as b2,
                SUM(CASE WHEN watched >= 7200 AND watched < 14400 THEN 1 ELSE 0 END) as b3,
                SUM(CASE WHEN watched >= 14400 THEN 1 ELSE 0 END) as b4
            FROM item_user_play
            WHERE visible = 1 AND update_time >= ?
        """, (week_ago,))
        row = cursor.fetchone()
        stats['duration_distribution'] = [
            {"label": "<30m", "value": row['b0'] or 0},
            {"label": "30-60m", "value": row['b1'] or 0},
            {"label": "1-2h", "value": row['b2'] or 0},
            {"label": "2-4h", "value": row['b3'] or 0},
            {"label": ">4h", "value": row['b4'] or 0},
        ]

        # 近7天逐日趋势（播放次数 / 活跃用户 / 观看小时），供统计卡 sparkline 使用
        cursor.execute("""
            SELECT
                date(update_time / 1000, 'unixepoch', 'localtime') AS day,
                COUNT(*) as plays,
                COUNT(DISTINCT user_guid) as active,
                SUM(watched) as watch_sec
            FROM item_user_play
            WHERE visible = 1 AND update_time >= ?
            GROUP BY day
        """, (now_ms() - 7 * 24 * 3600 * 1000,))
        by_day = {r['day']: r for r in cursor.fetchall()}
        today_start_sec = int(datetime.now().replace(hour=0, minute=0, second=0,
                                                     microsecond=0).timestamp())
        trend = []
        for d in range(6, -1, -1):
            day_str = datetime.fromtimestamp(today_start_sec - d * 86400).strftime("%Y-%m-%d")
            rec = by_day.get(day_str)
            trend.append({
                "plays": rec['plays'] if rec else 0,
                "active": rec['active'] if rec else 0,
                "hours": round((rec['watch_sec'] or 0) / 3600, 1) if rec else 0,
            })
        stats['daily_trend'] = trend

        # 近7天累计用户数趋势（供"总用户"卡片 sparkline）
        cursor.execute("""
            SELECT date(create_time / 1000, 'unixepoch', 'localtime') AS day, COUNT(*) as c
            FROM user
            WHERE create_time IS NOT NULL
            GROUP BY day
        """)
        created_by_day = {r['day']: r['c'] for r in cursor.fetchall()}
        base = stats['total_users'] - sum(
            c for day, c in created_by_day.items()
            if day and day >= datetime.fromtimestamp(today_start_sec - 6 * 86400).strftime("%Y-%m-%d"))
        users_trend = []
        for d in range(6, -1, -1):
            day_str = datetime.fromtimestamp(today_start_sec - d * 86400).strftime("%Y-%m-%d")
            base += created_by_day.get(day_str, 0)
            users_trend.append(max(0, base))
        stats['users_trend'] = users_trend

    except Exception as e:
        print(f"Stats error: {e}")
    
    conn.close()
    
    # 写入缓存
    with _stats_cache["lock"]:
        _stats_cache["data"] = stats
        _stats_cache["time"] = time.time()
    
    return stats

def get_hourly_stats():
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            strftime('%H', datetime(create_time / 1000, 'unixepoch', 'localtime')) as hour,
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
    return render_template('index.html', version=APP_VERSION,
                           refresh_interval=config.REFRESH_INTERVAL)

@app.route('/api/system')
def api_system():
    """系统状态（供前端"系统状态"卡片展示真实数据）"""
    db_size = os.path.getsize(TMP_DB_PATH) if os.path.exists(TMP_DB_PATH) else 0
    return jsonify({
        "version": APP_VERSION,
        "db_size": format_size(db_size),
        "db_last_sync": int(_last_copy_time),
        "uptime_sec": int(time.time() - _START_TIME),
        "log_enabled": config.LOG_ENABLED,
        "refresh_interval": config.REFRESH_INTERVAL,
        "total_plays": get_stats().get('total_plays', 0),
    })

@app.route('/api/stats')
def api_stats():
    if request.args.get('nocache'):
        with _stats_cache["lock"]:
            _stats_cache["data"] = None
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

@app.route('/api/heatmap')
def api_heatmap():
    conn = get_db_connection()
    if not conn:
        return jsonify([[0]*24 for _ in range(7)])
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            CAST(strftime('%w', datetime(create_time / 1000, 'unixepoch', 'localtime')) AS INTEGER) as dow,
            CAST(strftime('%H', datetime(create_time / 1000, 'unixepoch', 'localtime')) AS INTEGER) as hour,
            COUNT(*) as count
        FROM item_user_play
        WHERE visible = 1 AND update_time >= ?
        GROUP BY dow, hour
    """, (now_ms() - 7 * 24 * 3600 * 1000,))
    # SQLite %w: 0=Sunday ... 6=Saturday. Convert to Monday-first (0=Monday ... 6=Sunday)
    matrix = [[0]*24 for _ in range(7)]
    for row in cursor.fetchall():
        sqlite_dow = row['dow']
        # Convert Sunday=0 to Monday-first index: Sun(0)->6, Mon(1)->0, Tue(2)->1, ..., Sat(6)->5
        monday_first = (sqlite_dow - 1) % 7 if sqlite_dow is not None else 0
        hour = row['hour']
        if hour is not None and 0 <= hour < 24:
            matrix[monday_first][hour] = row['count']
    conn.close()
    return jsonify(matrix)

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
    if request.args.get('nocache'):
        with _log_cache["lock"]:
            _log_cache["data"] = None
    # 检查缓存
    with _log_cache["lock"]:
        if _log_cache["data"] and (time.time() - _log_cache["time"]) < _cache_ttl:
            return jsonify(_log_cache["data"])
    
    if not config.LOG_ENABLED:
        return jsonify([])
    logs = []
    log_dir = config.LOG_PATH
    
    if os.path.exists(log_dir):
        for filename in os.listdir(log_dir):
            if filename.endswith('.log'):
                filepath = os.path.join(log_dir, filename)
                try:
                    lines = tail_lines(filepath)[-200:]
                    last_ts = ""
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        if re.match(r'^\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}$', line):
                            last_ts = line.replace("/", "-")
                            continue
                        parsed = parse_nginx_log(line)
                        if parsed and not _is_noise_path(parsed['path']):
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
    result = logs[:100]
    
    # 写入缓存
    with _log_cache["lock"]:
        _log_cache["data"] = result
        _log_cache["time"] = time.time()
    
    return jsonify(result)

@app.route('/api/locations')
def api_locations():
    if request.args.get('nocache'):
        with _locations_cache["lock"]:
            _locations_cache["data"] = None
    # 检查缓存
    with _locations_cache["lock"]:
        if _locations_cache["data"] and (time.time() - _locations_cache["time"]) < _cache_ttl:
            return jsonify(_locations_cache["data"])
    
    if not config.LOG_ENABLED:
        return jsonify([])
    logs = []
    log_dir = config.LOG_PATH
    if os.path.exists(log_dir):
        for filename in os.listdir(log_dir):
            if filename.endswith('.log'):
                filepath = os.path.join(log_dir, filename)
                try:
                    lines = tail_lines(filepath)[-500:]
                    last_ts = ""
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        if re.match(r'^\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}$', line):
                            last_ts = line.replace("/", "-")
                            continue
                        parsed = parse_nginx_log(line)
                        if parsed and not _is_noise_path(parsed['path']):
                            logs.append(parsed)
                except Exception as e:
                    print(f"Log read error: {e}")

    # 去重 IP 查找（减少重复请求）
    ip_cache = {}
    for entry in logs:
        ip = entry.get("ip", "")
        if not ip:
            continue
        if ip not in ip_cache:
            ip_cache[ip] = get_ip_info(ip)
    
    # Aggregate by city with geo coordinates
    agg = {}
    for entry in logs:
        ip = entry.get("ip", "")
        if not ip:
            continue
        ip_info = ip_cache.get(ip, {})
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

    result = list(agg.values())
    
    # 写入缓存
    with _locations_cache["lock"]:
        _locations_cache["data"] = result
        _locations_cache["time"] = time.time()
    
    return jsonify(result)

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
