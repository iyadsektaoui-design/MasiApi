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
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
    ):
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
        "db_path": os.path.abspath(DB_PATH),
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

    # انضمام على مجمّع التاريخ للحصول على أحدث صف لكل رمز
    cur.execute(
        """
        SELECT c.symbol, c.name, c.price, c.change, c.volume, c.date
        FROM Company c
        JOIN (
            SELECT symbol, MAX(date) AS max_date
            FROM Company
            GROUP BY symbol
        ) m ON c.symbol = m.symbol AND c.date = m.max_date
        ORDER BY LOWER(c.name) ASC
        """
    )

    rows = [dict(r) for r in cur.fetchall()]

    return {"count": len(rows), "companies": rows}


# ---------------------------- 3) آخر يوم متوفر ---------------------------- #


@app.get("/company/latest")
def latest_day():
    """
    إرجاع جميع السجلات لأحدث تاريخ موجود في جدول Company
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة")

    conn = get_conn()
    cur = conn.execute("SELECT DISTINCT date FROM Company")
    dates = [r[0] for r in cur.fetchall()]

    if not dates:
        return {"date": None, "rows": []}

    parsed = [(d, parse_date(d)) for d in dates if parse_date(d)]
    if not parsed:
        return {"date": None, "rows": []}
    last_date = sorted(parsed, key=lambda x: x[1], reverse=True)[0][0]

    cur = conn.execute(
        "SELECT symbol, name, price, change, volume, date FROM Company WHERE date=?",
        (last_date,),
    )

    rows = [dict(r) for r in cur.fetchall()]
    rows_sorted = sort_desc_by_date(rows, key_field="date")

    return {"date": last_date, "count": len(rows_sorted), "rows": rows_sorted}


# ---------------------------- 4) حسب رمز معين ---------------------------- #


@app.get("/company/symbol")
def company_by_symbol(
    symbol: str = Query(...),
    date_from: str = None,
    date_to: str = None,
):
    """
    إرجاع بيانات رمز معين مع إمكانية تحديد فترة زمنية
    جميع النتائج مرتبة من الأحدث للأقدم
    ملاحظة: date_from و date_to يجب أن يكونا بصيغة YYYY-MM-DD أو DD/MM/YYYY
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة.")

    conn = get_conn()
    cur = conn.execute("SELECT * FROM Company WHERE symbol=?", (symbol,))
    rows = [dict(r) for r in cur.fetchall()]

    dt_from = parse_date(date_from) if date_from else None
    dt_to = parse_date(date_to) if date_to else None

    filtered = []
    for r in rows:
        d = parse_date(r.get("date"))
        if not d:
            continue
        if dt_from and d < dt_from:
            continue
        if dt_to and d > dt_to:
            continue
        filtered.append(r)

    rows_sorted = sort_desc_by_date(filtered, key_field="date")

    return {"symbol": symbol, "count": len(rows_sorted), "rows": rows_sorted}


# ---------------------------- 5) حسب فترة محددة (week, month...) ---------------------------- #


@app.get("/company/range")
def range_period(
    symbol: str = Query(...),
    period: str = Query(..., description="week, month, 3months, 6months, year, 3years"),
):
    """
    إرجاع بيانات رمز معين لفترة محددة
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة.")

    days = period_to_days(period)
    if not days:
        raise HTTPException(400, "الفترة غير صحيحة.")

    date_limit = datetime.today() - timedelta(days=days)

    conn = get_conn()
    cur = conn.execute("SELECT * FROM Company WHERE symbol=?", (symbol,))
    rows = [dict(r) for r in cur.fetchall()]

    filtered = []
    for r in rows:
        d = parse_date(r.get("date"))
        if d and d >= date_limit:
            filtered.append(r)

    filtered_sorted = sort_desc_by_date(filtered, key_field="date")

    return {"symbol": symbol, "period": period, "count": len(filtered_sorted), "rows": filtered_sorted}


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

    date_limit = datetime.today() - timedelta(days=days)

    conn = get_conn()
    cur = conn.execute("SELECT * FROM Company")
    rows = [dict(r) for r in cur.fetchall()]

    filtered = []
    for r in rows:
        d = parse_date(r.get("date"))
        if d and d >= date_limit:
            filtered.append(r)

    filtered_sorted = sort_desc_by_date(filtered, key_field="date")

    return {"period": period, "count": len(filtered_sorted), "rows": filtered_sorted}


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
    rows_sorted = sort_desc_by_date(rows, key_field="date")

    return {"count": len(rows_sorted), "rows": rows_sorted}


# ==================== نقاط نهاية جديدة للعمل على DailyVariation ==================== #


@app.get("/variation/symbol")
def variation_by_symbol(
    symbol: str = Query(...),
    date_from: str = None,
    date_to: str = None,
):
    """
    إرجاع سجلات DailyVariation لرمز معين مع فلترة اختيارية حسب نطاق تاريخي.
    date_from و date_to يقبلون YYYY-MM-DD أو DD/MM/YYYY
    النتيجة مرتبة من الأحدث للأقدم حسب الحقل timestamp.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة.")

    conn = get_conn()
    cur = conn.execute("SELECT * FROM DailyVariation WHERE symbol=?", (symbol,))
    rows = [dict(r) for r in cur.fetchall()]

    dt_from = parse_date(date_from) if date_from else None
    dt_to = parse_date(date_to) if date_to else None

    filtered = []
    for r in rows:
        ts = parse_timestamp(r.get("timestamp"))
        if not ts:
            continue
        if dt_from and ts < dt_from:
            continue
        if dt_to and ts > dt_to:
            continue
        filtered.append(r)

    filtered_sorted = sort_desc_by_date(filtered, key_field="timestamp")

    return {"symbol": symbol, "count": len(filtered_sorted), "rows": filtered_sorted}


@app.get("/variation/latest")
def variation_latest(symbol: str = None):
    """
    إرجاع أحدث سجلات DailyVariation.
    - إذا لم يُمرَّر symbol: إرجاع كل السجلات التي تملك أحدث timestamp في الجدول (جميع الرموز عند آخر وقت).
    - إذا مرَّر symbol: إرجاع السجلات الخاصة بالرمز عند أحدث timestamp له.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة.")

    conn = get_conn()
    cur = conn.cursor()

    if symbol:
        cur.execute("SELECT MAX(timestamp) FROM DailyVariation WHERE symbol=?", (symbol,))
        row = cur.fetchone()
        max_ts = row[0] if row else None
        if not max_ts:
            return {"symbol": symbol, "timestamp": None, "count": 0, "rows": []}
        cur.execute("SELECT * FROM DailyVariation WHERE symbol=? AND timestamp=?", (symbol, max_ts))
        rows = [dict(r) for r in cur.fetchall()]
        rows_sorted = sort_desc_by_date(rows, key_field="timestamp")
        return {"symbol": symbol, "timestamp": max_ts, "count": len(rows_sorted), "rows": rows_sorted}
    else:
        cur.execute("SELECT MAX(timestamp) FROM DailyVariation")
        row = cur.fetchone()
        max_ts = row[0] if row else None
        if not max_ts:
            return {"timestamp": None, "count": 0, "rows": []}
        cur.execute("SELECT * FROM DailyVariation WHERE timestamp=?", (max_ts,))
        rows = [dict(r) for r in cur.fetchall()]
        rows_sorted = sort_desc_by_date(rows, key_field="timestamp")
        return {"timestamp": max_ts, "count": len(rows_sorted), "rows": rows_sorted}


@app.get("/variation/recent")
def variation_recent(symbol: str = Query(...), limit: int = Query(50, ge=1, le=1000)):
    """
    إرجاع آخر N سجل من جدول DailyVariation لرمز معين (مرتبة نزولًا حسب timestamp).
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة.")

    conn = get_conn()
    cur = conn.execute(
        "SELECT * FROM DailyVariation WHERE symbol=? ORDER BY timestamp DESC LIMIT ?",
        (symbol, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    rows_sorted = sort_desc_by_date(rows, key_field="timestamp")
    return {"symbol": symbol, "limit": limit, "count": len(rows_sorted), "rows": rows_sorted}

# ---------------------------- 3)قائمة الرموز الشركات ---------------------------- #

@app.get("/variation/symbols")
def symbols_list():
    """
    إرجاع قائمة الرموز الشركات
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة.")

    conn = get_conn()
    cur = conn.execute("SELECT DISTINCT symbol FROM Company")
    rows = [dict(r) for r in cur.fetchall()]
    return {"count": len(rows), "symbols": rows}
    
# ==================== OpenAPI export / serve ==================== #


@app.get("/openapi/samples")
def openapi_samples():
    """
    Endpoint that returns sample queries and curl examples to be included in OpenAPI docs.
    """
    samples = {
        "company_list": {
            "description": "Get latest price/date per symbol",
            "curl": "curl -s 'http://localhost:8000/company/list'",
            "example_response": {
                "count": 10,
                "companies": [
                    {
                        "symbol": "ADH",
                        "name": "Addoha",
                        "price": 31.0,
                        "change": "+3.37%",
                        "volume": "12345",
                        "date": "2026-02-18",
                    }
                ],
            },
        },
        "company_latest": {"curl": "curl -s 'http://localhost:8000/company/latest'"},
        "company_symbol": {
            "curl": "curl -s 'http://localhost:8000/company/symbol?symbol=ADH&date_from=2026-01-01&date_to=2026-02-01'"
        },
        "variation_latest": {"curl": "curl -s 'http://localhost:8000/variation/latest'"},
        "variation_recent": {
            "curl": "curl -s 'http://localhost:8000/variation/recent?symbol=ADH&limit=100'"
        },
    }
    return samples


@app.get("/export/openapi")
def export_openapi():
    """
    تصدير ملف OpenAPI JSON كامل للتوثيق
    """
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    with open("openapi.json", "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    return {"status": "generated", "file": "openapi.json", "download_url": "/openapi.json"}


@app.get("/openapi.json")
def serve_openapi_file():
    """
    تنزيل ملف OpenAPI JSON الذي تم توليده
    """
    if not os.path.exists("openapi.json"):
        raise HTTPException(404, "الملف غير موجود. قم بتوليده عبر /export/openapi")
    return FileResponse("openapi.json", media_type="application/json")
