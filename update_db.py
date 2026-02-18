# -*- coding: utf-8 -*-
import os
import sqlite3
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "stocks_morocco.db")

URL = "https://scanner.tradingview.com/morocco/scan"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json"
}

def make_session():
    s = requests.Session()
    retries = Retry(total=5, backoff_factor=0.6, status_forcelist=(429, 500, 502, 503, 504))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.headers.update(HEADERS)
    return s

def ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS "Company" (
            "symbol" TEXT NOT NULL,
            "name"   TEXT,
            "price"  REAL,
            "open"   REAL,
            "high"   REAL,
            "low"    REAL,
            "change" TEXT,
            "volume" TEXT,
            "date"   TEXT NOT NULL,
            PRIMARY KEY ("symbol", "date")
        )
    """)
    
    # إنشاء فهرس على التاريخ لتسريع البحث
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_company_date ON Company(date)
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS "DailyVariation" (
            "symbol" TEXT, 
            "timestamp" TEXT, 
            "price" REAL, 
            "change" TEXT,
            PRIMARY KEY ("symbol", "timestamp")
        )
    """)

def safe_float(val):
    try: return float(val) if val is not None else 0.0
    except: return 0.0

def update_data():
    session = make_session()
    payload = {
        "filter": [],
        "options": {"lang": "en"},
        "markets": ["morocco"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "close", "change", "volume", "description", "open", "high", "low"],
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, 150]
    }

    try:
        resp = session.post(URL, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception as e:
        print(f"❌ خطأ اتصال: {e}")
        return

    print(f"📂 يتم الحفظ في: {DB_PATH}")
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    ensure_tables(con)

    # استخدام صيغة صريحة للتاريخ (YYYY-MM-DD)
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"📅 تاريخ اليوم: {current_date}")

    # حذف سجلات اليوم لضمان التحديث النظيف
    cur.execute("DELETE FROM Company WHERE date = ?", (current_date,))
    deleted = cur.rowcount
    print(f"🗑️  تم حذف {deleted} سجل قديم")

    batch_data = []
    
    for item in data:
        d = item.get("d", [])
        if len(d) < 8: continue

        symbol = (d[0] or "").strip()
        if not symbol: continue

        price  = safe_float(d[1])
        change = f"{safe_float(d[2]):+.2f}%"
        volume = str(int(safe_float(d[3])))
        name   = (d[4] or "").strip() or symbol
        open_p = safe_float(d[5])
        high_p = safe_float(d[6])
        low_p  = safe_float(d[7])

        # التأكد من أن التاريخ بصيغة نظيفة (بدون مسافات)
        batch_data.append((
            symbol.strip(), 
            name.strip(), 
            price, 
            open_p, 
            high_p, 
            low_p, 
            change.strip(), 
            volume.strip(), 
            current_date  # التاريخ بصيغة YYYY-MM-DD فقط
        ))

    # إدراج جميع البيانات دفعة واحدة
    try:
        cur.executemany("""
            INSERT INTO Company (symbol, name, price, open, high, low, change, volume, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch_data)
        print(f"✅ تم إدراج {len(batch_data)} سجل في جدول Company")
    except Exception as e:
        print(f"❌ خطأ في الإدراج: {e}")
        con.rollback()
        con.close()
        return

    # إدراج في جدول التذبذب
    variation_count = 0
    for item in data:
        d = item.get("d", [])
        if len(d) < 8: continue
        
        symbol = (d[0] or "").strip()
        if not symbol: continue
            
        price = safe_float(d[1])
        change = f"{safe_float(d[2]):+.2f}%"
        
        try:
            cur.execute("""
                INSERT INTO DailyVariation (symbol, timestamp, price, change)
                VALUES (?, ?, ?, ?)
            """, (symbol.strip(), current_ts, price, change.strip()))
            variation_count += 1
        except:
            pass

    con.commit()

    # اختبار البحث بالتاريخ
    print(f"\n{'='*60}")
    print(f"🔍 اختبار البحث بالتاريخ: {current_date}")
    print(f"{'='*60}")
    
    cur.execute("SELECT COUNT(*) FROM Company WHERE date = ?", (current_date,))
    count_today = cur.fetchone()[0]
    print(f"📊 عدد السجلات لتاريخ {current_date}: {count_today}")
    
    if count_today > 0:
        cur.execute("""
            SELECT symbol, name, price, change, date 
            FROM Company 
            WHERE date = ? 
            LIMIT 3
        """, (current_date,))
        
        print(f"\n📋 أول 3 سجلات:")
        for row in cur.fetchall():
            print(f"   {row[0]} | {row[1][:30]} | {row[2]} | {row[3]} | [{row[4]}]")
    
    # عرض جميع التواريخ المتاحة
    cur.execute("SELECT DISTINCT date FROM Company ORDER BY date DESC LIMIT 5")
    dates = cur.fetchall()
    print(f"\n📅 آخر 5 تواريخ في قاعدة البيانات:")
    for d in dates:
        cur.execute("SELECT COUNT(*) FROM Company WHERE date = ?", (d[0],))
        cnt = cur.fetchone()[0]
        print(f"   {d[0]} -> {cnt} سجل")
    
    con.close()
    
    print(f"\n{'='*60}")
    print(f"✅ تم تحديث {len(batch_data)} شركة")
    print(f"✅ تم إضافة {variation_count} سجل تذبذب")
    print(f"\n💡 للبحث في DB Browser استخدم:")
    print(f"   WHERE date = '{current_date}'")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    update_data()
