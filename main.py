# -*- coding: utf-8 -*-
import os
import sqlite3
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

DB_PATH = os.getenv("DB_PATH", "./stocks_morocco.db")

app = FastAPI(
    title="Morocco Market API",
    description="API لقراءة بيانات البورصة المغربية من جدول Company فقط.",
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
    تحويل التاريخ من DD/MM/YYYY إلى كائن datetime
    """
    try:
        return datetime.strptime(d, "%d/%m/%Y")
    except:
        return None


def sort_desc_by_date(rows):
    """
    ترتيب السجلات تنازليًا حسب التاريخ (الأحدث → الأقدم)
    """
    def keyfn(r):
        d = parse_date(r["date"])
        return d if d else datetime.min
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
        "db_path": DB_PATH
    }


# ---------------------------- 2) قائمة الشركات ---------------------------- #

@app.get("/company/list")
def list_companies():
    """
    إرجاع قائمة الشركات (symbol + name) مرتبة أبجديًا حسب الاسم
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة.")

    conn = get_conn()
    cur = conn.execute("SELECT DISTINCT symbol, name FROM Company")

    rows = [dict(r) for r in cur.fetchall()]

    # ترتيب أبجدي حسب name
    rows_sorted = sorted(rows, key=lambda x: x["name"])

    return {
        "count": len(rows_sorted),
        "companies": rows_sorted
    }


# ---------------------------- 3) آخر يوم متوفر ---------------------------- #

@app.get("/company/latest")
def latest_day():
    """
    إرجاع جميع السجلات لأحدث تاريخ موجود في قاعدة البيانات
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة")

    conn = get_conn()
    cur = conn.execute("SELECT DISTINCT date FROM Company")
    dates = [r[0] for r in cur.fetchall()]

    if not dates:
        return {"date": None, "rows": []}

    # تحويل وفرز التواريخ
    parsed = [(d, parse_date(d)) for d in dates if parse_date(d)]
    last_date = sorted(parsed, key=lambda x: x[1], reverse=True)[0][0]

    cur = conn.execute(
        "SELECT symbol, name, price, change, volume, date "
        "FROM Company WHERE date=?",
        (last_date,)
    )

    rows = [dict(r) for r in cur.fetchall()]
    rows_sorted = sort_desc_by_date(rows)

    return {"date": last_date, "count": len(rows_sorted), "rows": rows_sorted}


# ---------------------------- 4) حسب رمز معين ---------------------------- #

@app.get("/company/symbol")
def company_by_symbol(
    symbol: str = Query(...),
    date_from: str = None,
    date_to: str = None
):
    """
    إرجاع بيانات رمز معين مع إمكانية تحديد فترة زمنية
    جميع النتائج مرتبة من الأحدث للأقدم
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة.")

    conn = get_conn()

    query = "SELECT * FROM Company WHERE symbol=?"
    params = [symbol]

    if date_from:
        query += " AND date >= ?"
        params.append(date_from)

    if date_to:
        query += " AND date <= ?"
        params.append(date_to)

    cur = conn.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]

    rows_sorted = sort_desc_by_date(rows)

    return {
        "symbol": symbol,
        "count": len(rows_sorted),
        "rows": rows_sorted
    }


# ---------------------------- 5) حسب فترة محددة (week, month...) ---------------------------- #

@app.get("/company/range")
def range_period(
    symbol: str = Query(...),
    period: str = Query(..., description="week, month, 3months, 6months, year, 3years")
):
    """
    إرجاع بيانات رمز معين لفترة محددة
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة.")

    days = period_to_days(period)
    if not days:
        raise HTTPException(400, "الفترة غير صحيحة.")

    today = datetime.today()
    date_limit = today - timedelta(days=days)

    conn = get_conn()
    cur = conn.execute(
        "SELECT * FROM Company WHERE symbol=?",
        (symbol,)
    )

    rows = [dict(r) for r in cur.fetchall()]

    # فلترة حسب التاريخ
    filtered = []
    for r in rows:
        d = parse_date(r["date"])
        if d and d >= date_limit:
            filtered.append(r)

    filtered_sorted = sort_desc_by_date(filtered)

    return {
        "symbol": symbol,
        "period": period,
        "count": len(filtered_sorted),
        "rows": filtered_sorted
    }


# ---------------------------- 6) نفس الفترة لجميع الشركات ---------------------------- #

@app.get("/company/range/all")
def range_all(period: str):
    """
    إرجاع بيانات جميع الشركات لفترة معينة
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة.")

    days = period_to_days(period)
    if not days:
        raise HTTPException(400, "الفترة غير صحيحة.")

    today = datetime.today()
    date_limit = today - timedelta(days=days)

    conn = get_conn()
    cur = conn.execute("SELECT * FROM Company")

    rows = [dict(r) for r in cur.fetchall()]

    # فلترة حسب التاريخ
    filtered = []
    for r in rows:
        d = parse_date(r["date"])
        if d and d >= date_limit:
            filtered.append(r)

    filtered_sorted = sort_desc_by_date(filtered)

    return {
        "period": period,
        "count": len(filtered_sorted),
        "rows": filtered_sorted
    }


# ---------------------------- 7) جميع البيانات ---------------------------- #

@app.get("/company/all")
def all_data():
    """
    إرجاع جميع السجلات لجميع الشركات
    مرتبة من الأحدث للأقدم
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة.")

    conn = get_conn()
    cur = conn.execute("SELECT * FROM Company")

    rows = [dict(r) for r in cur.fetchall()]
    rows_sorted = sort_desc_by_date(rows)

    return {"count": len(rows_sorted), "rows": rows_sorted}
