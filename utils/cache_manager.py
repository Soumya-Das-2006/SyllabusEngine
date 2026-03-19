"""
cache_manager.py — Offline-first cache layer.
Uses SQLite via a simple key/value store distinct from the main DB.
"""
import json
import sqlite3
import os
import time
import hashlib
from datetime import datetime, timedelta
from functools import wraps

_CACHE_DB = os.path.join(os.path.dirname(__file__), '..', 'instance', 'cache.db')


def _get_conn():
    os.makedirs(os.path.dirname(_CACHE_DB), exist_ok=True)
    conn = sqlite3.connect(_CACHE_DB, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache_store (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            created_at REAL NOT NULL,
            ttl_sec    REAL NOT NULL DEFAULT 86400
        )
    """)
    conn.commit()
    return conn


def save_cache(key: str, data, ttl_sec: int = 86400) -> None:
    """Persist data under key. TTL defaults to 24 h."""
    conn = _get_conn()
    try:
        serialized = json.dumps(data, default=str)
        conn.execute(
            "INSERT OR REPLACE INTO cache_store (key, value, created_at, ttl_sec) VALUES (?,?,?,?)",
            (key, serialized, time.time(), ttl_sec)
        )
        conn.commit()
    finally:
        conn.close()


def get_cache(key: str):
    """Return cached value or None if missing / expired."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT value, created_at, ttl_sec FROM cache_store WHERE key=?", (key,)
        ).fetchone()
        if not row:
            return None
        value, created_at, ttl_sec = row
        if time.time() - created_at > ttl_sec:
            conn.execute("DELETE FROM cache_store WHERE key=?", (key,))
            conn.commit()
            return None
        return json.loads(value)
    finally:
        conn.close()


def delete_cache(key: str) -> None:
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM cache_store WHERE key=?", (key,))
        conn.commit()
    finally:
        conn.close()


def make_cache_key(*parts) -> str:
    raw = ":".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()


def is_low_bandwidth() -> bool:
    """
    Heuristic: attempt a lightweight HEAD to a known fast endpoint.
    Returns True when on slow / no connectivity or when low_data_mode
    flag is set in the cache.
    """
    forced = get_cache("low_data_mode_forced")
    if forced:
        return True

    import socket
    try:
        socket.setdefaulttimeout(1.5)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return False
    except OSError:
        return True


def set_low_data_mode(enabled: bool) -> None:
    if enabled:
        save_cache("low_data_mode_forced", True, ttl_sec=60 * 60 * 24 * 365)
    else:
        delete_cache("low_data_mode_forced")


def cached_api_call(key: str, fn, ttl_sec: int = 3600, low_bw_fallback=None):
    """
    Try cache first. If miss and not low-bandwidth, call fn() and store result.
    If low-bandwidth and no cache, return low_bw_fallback.
    """
    cached = get_cache(key)
    if cached is not None:
        return cached, True   # (data, from_cache)

    if is_low_bandwidth():
        return low_bw_fallback, False

    result = fn()
    if result:
        save_cache(key, result, ttl_sec)
    return result, False
