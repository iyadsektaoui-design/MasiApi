from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.getenv("DB_PATH", "./stocks_morocco.db")

app = FastAPI(
    title="Morocco Market API (Company Only)",
    description="API لقراءة بيانات المؤشرات والأسهم من جدول Company فقط.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/health")
def health():
    return {"status": "ok", "db_exists": os.path.exists(DB_PATH)}


@app.get("/company/latest")
def latest_day():
    """إرجاع آخر يوم متوفر بالكامل في جدول Company"""
    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة")

    conn = get_conn()
    cur = conn.execute("SELECT DISTINCT date FROM Company")
    dates = [r[0] for r in cur.fetchall()]
    if not dates:
        return {"date": None, "rows": []}

    # ترتيب التواريخ (قد تكون بصيغة DD/MM/YYYY)
    def parse_date(d):
        try:
            return datetime.strptime(d, "%d/%m/%Y")
        except:
            return datetime.min

    last_date = sorted(dates, key=parse_date)[-1]

    cur = conn.execute(
        "SELECT symbol, name, price, change, volume, date FROM Company WHERE date=? ORDER BY symbol",
        (last_date,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    return {"date": last_date, "count": len(rows), "rows": rows}


@app.get("/company/symbol")
def company_by_symbol(
    symbol: str = Query(...),
    date_from: str = None,
    date_to: str = None
):
    """إرجاع بيانات رمز معين من جدول Company مع إمكانية تحديد فترة زمنية"""

    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة")

    conn = get_conn()

    query = "SELECT symbol, name, price, change, volume, date FROM Company WHERE symbol=?"
    params = [symbol]

    if date_from:
        query += " AND date >= ?"
        params.append(date_from)

    if date_to:
        query += " AND date <= ?"
        params.append(date_to)

    query += " ORDER BY date ASC"

    cur = conn.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]

    return {"symbol": symbol, "count": len(rows), "rows": rows}


@app.get("/company/3years")
def last_3_years(symbol: str = Query(...)):
    """إرجاع بيانات آخر 3 سنوات لرمز معين من جدول Company"""

    if not os.path.exists(DB_PATH):
        raise HTTPException(500, "قاعدة البيانات غير موجودة")

    today = datetime.today()
    three_years_ago = today - timedelta(days=365 * 3)

    # لكن جدولك يُخزّن التاريخ بصيغة DD/MM/YYYY
    date_from = three_years_ago.strftime("%d/%m/%Y")

    conn = get_conn()
    cur = conn.execute(
        """
        SELECT symbol, name, price, change, volume, date
        FROM Company
        WHERE symbol = ?
        ORDER BY date ASC
        """,
        (symbol,)
    )

    rows = [dict(r) for r in cur.fetchall()]

    # فلترة التواريخ بعد الجلب (لأن المقارنة النصية غير دقيقة)
    def is_after_3y(rec):
        try:
            d = datetime.strptime(rec["date"], "%d/%m/%Y")
            return d >= three_years_ago
        except:
            return False

    filtered = [r for r in rows if is_after_3y(r)]

    return {
        "symbol": symbol,
        "date_from": date_from,
        "count": len(filtered),
        "rows": filtered
    }
