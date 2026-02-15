import yfinance as yf
import pandas as pd
from pandas import MultiIndex
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
import requests
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def _build_candles(yf_symbol: str, days: int):
    # 1. قائمة بمتصفحات مختلفة لتبديل الهوية (لخداع نظام الحماية في ياهو)
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]

    session = requests.Session()
    session.headers.update({
        'User-Agent': random.choice(user_agents),
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Origin': 'https://finance.yahoo.com',
        'Referer': 'https://finance.yahoo.com',
    })

    try:
        # 2. محاولة جلب البيانات بطريقة الـ Period بدلاً من التاريخ المحدد
        ticker_obj = yf.Ticker(yf_symbol, session=session)
        
        # نستخدم 3mo كحد أدنى للمؤشرات لضمان وجود بيانات
        fetch_period = "3mo" if days <= 60 else "1y"
        
        # طلب البيانات مع إيقاف auto_adjust لضمان ثبات الأعمدة
        df = ticker_obj.history(period=fetch_period, interval="1d", auto_adjust=True)

        # 3. تسطيح الأعمدة (Flattening)
        if isinstance(df.columns, MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 4. إذا فشل المؤشر المغربي ^MASI، نجرب الرمز المباشر للبورصة
        if df.empty and "MASI" in yf_symbol:
            df = yf.download("MASI.CAS", period="1mo", session=session, progress=False)
            if isinstance(df.columns, MultiIndex):
                df.columns = df.columns.get_level_values(0)

        if df.empty:
            raise ValueError(f"No data available for {yf_symbol}")

        # 5. تنظيف البيانات واقتطاع المطلوب
        df = df.sort_index().tail(days)
        
        candles = []
        for ts, row in df.iterrows():
            # التأكد من وجود الأعمدة المطلوبة
            if all(col in df.columns for col in ['Open', 'High', 'Low', 'Close']):
                candles.append({
                    "time": ts.strftime('%Y-%m-%d'),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row.get("Volume", 0)) if pd.notna(row.get("Volume")) else 0
                })
        return candles

    except Exception as e:
        raise Exception(f"Yahoo Provider Error: {str(e)}")

@app.get("/{ticker}")
def get_stock(ticker: str, days: int = 60):
    t = ticker.strip().upper()
    
    # تصحيح منطق الرموز
    if t == "MASI":
        yf_symbol = "^MASI"
    elif t in ["IXIC", "GSPC", "DJI"]:
        yf_symbol = f"^{t}"
    elif "." not in t and t not in ["MSFT", "AAPL", "NVDA"]:
        yf_symbol = f"{t}.MA"
    else:
        yf_symbol = t

    try:
        data = _build_candles(yf_symbol, days)
        return {
            "status": "success",
            "ticker": t,
            "yf_symbol": yf_symbol,
            "candles": data
        }
    except Exception as e:
        # عرض الخطأ بشكل أوضح للتشخيص
        return {
            "status": "error",
            "message": str(e),
            "tip": "If this is a Moroccan stock, Yahoo might be blocking the server IP. Try again in a few minutes."
        }
