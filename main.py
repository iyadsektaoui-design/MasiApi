# -*- coding: utf-8 -*-
import os
import io
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# =========================
# إعدادات عامة
# =========================
DB_PATH = os.getenv("DB_PATH", "./stocks_morocco.db")
DB_REMOTE_URL = os.getenv("DB_REMOTE_URL")  # إن زُوِّد، سننزّل القاعدة عند التشغيل

app = FastAPI(
    title="Masi / MSI20 API",
    description="واجهة REST لقراءة البيانات من stocks_morocco.db (Company + stock_history)",
    version="1.0.0",
)

# السماح بالوصول من أيّ أصل (يمكنك ضبطها لاحقاً)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# أدوات مساعدة للقاعدة
# =========================
def get_conn() -> sqlite3.Connection:
    # نصنع اتصالاً عند كل طلب لضمان الأمان في بيئات الويب
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)
    )
    return cur.fetchone() is not None

def list_tables(conn: sqlite3.Connection) -> List[str]:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [r[0] for r in cur.fetchall()]

def parse_possible_date(s: str) -> datetime:
    """
    يقبل صيغاً شائعة للتاريخ/الوقت ويحوّلها إلى datetime:
    - DD/MM/YYYY
    - YYYY-MM-DD
    - YYYY-MM-DD HH:MM[:SS]
    """
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"تنسيق تاريخ غير مدعوم: {s}")

def get_latest_company_date(conn: sqlite3.Connection) -> Optional[str]:
    """
    لأن عمود date في Company قد يكون بصيغة نصية (مثل DD/MM/YYYY)،
    سنجلب القيم المميّزة ونختار الأحدث فعلياً.
    """
    if not table_exists(conn, "Company"):
        return None
    cur = conn.execute("SELECT DISTINCT date FROM Company")
    dates = [r[0] for r in cur.fetchall() if r[0]]
    if not dates:
        return None
    def key_fn(ds: str):
        try:
            return parse_possible_date(ds)
        except Exception:
            return datetime.min
    return max(dates, key=key_fn)

def download_db_if_needed():
    """
    إذا لم تكن القاعدة موجودة محلياً و DB_REMOTE_URL معيّن، نزّل القاعدة.
    """
    if os.path.exists(DB_PATH):
        return
    if not DB_REMOTE_URL:
        return
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    resp = requests.get(DB_REMOTE_URL, timeout=60)
    resp.raise_for_status()
    with open(DB_PATH, "wb") as f:
        f.write(resp.content)

@app.on_event("startup")
def on_startup():
    try:
        download_db_if_needed()
    except Exception as e:
        # لا نوقِف التطبيق؛ لكن سنفيد برسالة واضحة عند أول نداء
        print("DB download failed:", e)

# =========================
# مسارات عامة
# =========================
@app.get("/health")
def health():
    return {"status": "ok", "db_path": DB_PATH, "exists": os.path.exists(DB_PATH)}

@app.get("/info")
def info():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير موجودة على المسار المحدد.")
    with get_conn() as conn:
        tabs = list_tables(conn)
        out: Dict[str, Any] = {"db_path": DB_PATH, "tables": tabs, "counts": {}}
        for t in tabs:
            try:
                cur = conn.execute(f"SELECT COUNT(*) FROM {t}")
                out["counts"][t] = cur.fetchone()[0]
            except Exception:
                out["counts"][t] = None
        return out

@app.get("/symbols")
def symbols():
    """
    يُرجع قائمة بالرموز المتوفرة (من stock_history إن وجد، وإلا من Company).
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير موجودة.")
    with get_conn() as conn:
        syms = set()
        if table_exists(conn, "stock_history"):
            cur = conn.execute("SELECT DISTINCT symbol FROM stock_history")
            syms |= {r[0] for r in cur.fetchall() if r[0]}
        if table_exists(conn, "Company"):
            cur = conn.execute("SELECT DISTINCT symbol FROM Company")
            syms |= {r[0] for r in cur.fetchall() if r[0]}
        return {"count": len(syms), "symbols": sorted(syms)}

# =========================
# Company endpoints (لقطات يومية)
# =========================
@app.get("/company/latest")
def company_latest():
    """
    يُرجِع لقطات آخر يوم متوفر في جدول Company.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير موجودة.")
    with get_conn() as conn:
        if not table_exists(conn, "Company"):
            raise HTTPException(status_code=404, detail="جدول Company غير موجود.")
        last_date = get_latest_company_date(conn)
        if not last_date:
            return {"date": None, "rows": []}
        cur = conn.execute(
            "SELECT symbol, name, price, change, volume, date FROM Company WHERE date = ? ORDER BY symbol ASC",
            (last_date,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        return {"date": last_date, "rows": rows, "count": len(rows)}

@app.get("/company")
def company(
    symbol: Optional[str] = None,
    date: Optional[str] = None,
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    """
    قراءة جدول Company مع فِلترة اختيارية بالرمز/التاريخ.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير موجودة.")
    with get_conn() as conn:
        if not table_exists(conn, "Company"):
            raise HTTPException(status_code=404, detail="جدول Company غير موجود.")
        clauses, args = [], []
        if symbol:
            clauses.append("symbol = ?")
            args.append(symbol)
        if date:
            # نقبل أي صيغة طالما متطابقة مع ما هو مخزّن نصياً
            clauses.append("date = ?")
            args.append(date)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT symbol, name, price, change, volume, date
            FROM Company
            {where}
            ORDER BY date DESC, symbol ASC
            LIMIT ? OFFSET ?
        """
        args.extend([limit, offset])
        cur = conn.execute(sql, args)
        rows = [dict(r) for r in cur.fetchall()]
        return {"count": len(rows), "rows": rows}

@app.get("/indices/latest")
def indices_latest():
    """
    يُرجع آخر لقطات للمؤشرين MASI و MSI20.
    يحاول أولاً من Company (آخر يوم)، وإن لم يوجد في Company يحاول من stock_history بأحدث time.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير موجودة.")
    result: Dict[str, Any] = {}
    with get_conn() as conn:
        # المحاولة 1: من Company
        if table_exists(conn, "Company"):
            last_date = get_latest_company_date(conn)
            if last_date:
                cur = conn.execute(
                    "SELECT symbol, name, price, change, volume, date FROM Company WHERE date=? AND symbol IN ('MASI','MSI20')",
                    (last_date,),
                )
                rows = [dict(r) for r in cur.fetchall()]
                if rows:
                    result["source"] = "Company"
                    result["date_or_time"] = last_date
                    result["rows"] = rows
                    return result

        # المحاولة 2: من stock_history
        if table_exists(conn, "stock_history"):
            cur = conn.execute("""
                SELECT symbol, time, open, high, low, close
                FROM stock_history
                WHERE symbol IN ('MASI','MSI20')
                ORDER BY time DESC
                LIMIT 2
            """)
            rows = [dict(r) for r in cur.fetchall()]
            if rows:
                result["source"] = "stock_history"
                result["date_or_time"] = rows[0]["time"]
                result["rows"] = rows
                return result

    raise HTTPException(status_code=404, detail="تعذر إيجاد بيانات المؤشرين.")

# =========================
# stock_history endpoints (OHLC)
# =========================
@app.get("/history")
def history(
    symbol: str = Query(..., description="الرمز المطلوب (إلزامي)"),
    time_from: Optional[str] = Query(None, description="بداية النطاق (يدعم DD/MM/YYYY أو ISO)"),
    time_to: Optional[str] = Query(None, description="نهاية النطاق (يدعم DD/MM/YYYY أو ISO)"),
    order: str = Query("asc", pattern="^(?i)(asc|desc)$"),
    limit: int = Query(500, ge=1, le=10000),
    offset: int = Query(0, ge=0),
):
    """
    يسحب سلسلة OHLC من stock_history حسب نطاق زمني واختيارات ترتيب/ترقيم صفحات.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير موجودة.")
    with get_conn() as conn:
        if not table_exists(conn, "stock_history"):
            raise HTTPException(status_code=404, detail="جدول stock_history غير موجود.")
        clauses, args = ["symbol = ?"], [symbol]
        if time_from:
            # نقبل صيغاً متعددة، لكن بما أن العمود نص، نفترض تخزينه بصيغة ISO أو ثابتة.
            clauses.append("time >= ?")
            # نطبع كما أُرسلت (لا نحاول تحويلها خوفاً من مخالفة التنسيق التخزيني)
            args.append(time_from)
        if time_to:
            clauses.append("time <= ?")
            args.append(time_to)
        where = " WHERE " + " AND ".join(clauses)
        order_dir = "ASC" if order.lower() == "asc" else "DESC"
        sql = f"""
            SELECT symbol, time, open, high, low, close
            FROM stock_history
            {where}
            ORDER BY time {order_dir}
            LIMIT ? OFFSET ?
        """
        args.extend([limit, offset])
        cur = conn.execute(sql, args)
        rows = [dict(r) for r in cur.fetchall()]
        return {"count": len(rows), "rows": rows}

@app.get("/history/{symbol}/latest")
def history_latest(symbol: str):
    """
    يُرجع آخر سجل OHLC لرمز معيّن من stock_history.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير موجودة.")
    with get_conn() as conn:
        if not table_exists(conn, "stock_history"):
            raise HTTPException(status_code=404, detail="جدول stock_history غير موجود.")
        cur = conn.execute(
            "SELECT symbol, time, open, high, low, close FROM stock_history WHERE symbol=? ORDER BY time DESC LIMIT 1",
            (symbol,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="لا توجد بيانات لهذا الرمز.")
        return dict(row)
``
