# -*- coding: utf-8 -*-
import os
import sqlite3
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
import json

DB_PATH = os.getenv("DB_PATH", "./stocks_morocco.db")

app = FastAPI(
    title="Morocco Market API",
    description="API لقراءة بيانات البورصة المغربية من جدول Company و DailyVariation.",
    version="2.0.0"
)

# السماح بالوصول من أي origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------- أدوات مشتركة ---------------------------- #

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def parse_date(d: str):
    """
    تحويل التاريخ إلى كائن datetime.
    ندعم عدة صيغ شائعة:
    - YYYY-MM-DD
    - YYYY-MM-DD HH:MM:SS
    - DD/MM/YYYY
    - DD/MM/YYYY HH:MM:SS
    إرجاع None إن لم نستطع التحويل.
    """
    if not d:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(d, fmt)
        except Exception:
            continue
    return None


def parse_timestamp(ts: str):
    """
    تحويل حقل timestamp من جدول DailyVariation إلى datetime.
    ندعم صيغ ISO مع أو بدون وقت، و ISO T، وأيضاً dd/mm/YYYY إذا وجد.
    """
    if not ts:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(ts, fmt)
        except Exception:
            continue
    return None


def sort_desc_by_date(rows, key_field="date"):
    """
    ترتيب السجلات تنازليًا حسب حقل تاريخ/توقيت محدد (افتراضي 'date').
    يحاول تحويل الحقل إلى datetime بمساعدة parse_date / parse_timestamp.
    """
    def keyfn(r):
        val = r.get(key_field)
        if key_field == "timestamp":
            dt = parse_timestamp(val)
        else:
            dt = parse_date(val)
        return dt if dt else datetime.min
    return sorted(rows, key=keyfn, reverse=True)


def period_to_days(period: str):
    """
    تحويل الفترة النصية إلى عدد أيام
    """
    mapping = {
        "week": 7,
        "month": 30,
        "3months": 90,
        "6months": 180,
        "year": 365,
        "3years": 365 * 3
    }
    return mapping.get(period.lower())


# ---------------------------- 1) Health ---------------------------- #

@app.get("/health")
def health():
    return {
        "status": "ok",
        "db_exists": os.path.exists(DB_PATH),
        "db_path": os.path.abspath(DB_PATH)
    }


# ---------------------------- 2) قائمة الشركات (مع aggregation) ---------------------------- #

@app.get("/company/list")
def list_companies():
    """
    إرجاع قائمة الشركات (symbol + name) مرتبة أبجديًا حسب الاسم
    بالإضافة لآخر سعر وآخر تاريخ متوفر لكل رمز (aggregation).
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة.")

    conn = get_conn()
    cur = conn.cursor()

    # نستخدم انضمام على مجمّع التاريخ للحصول على أحدث صف لكل رمز
    cur.execute("""
        SELECT c.symbol, c.name, c.price, c.change, c.volume, c.date
        FROM Company c
        JOIN (
            SELECT symbol, MAX(date) AS max_date
            FROM Company
            GROUP BY symbol
        ) m ON c.symbol = m.symbol AND c.date = m.max_date
        ORDER BY LOWER(c.name) ASC
    """)

    rows = [dict(r) for r in cur.fetchall()]

    return {
        "count": len(rows),
        "companies": rows
   *
