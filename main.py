from datetime import datetime, timedelta, timezone
import yfinance as yf
import pandas as pd
from pandas import MultiIndex
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def _build_candles(yf_symbol: str, days: int):
    # 1. إنشاء جلسة متصفح (User-Agent) ضرورية جداً لبورصة المغرب
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days + 15)

    # 2. جلب البيانات باستخدام الجلسة
    ticker_obj = yf.Ticker(yf_symbol, session=session)
    df = ticker_obj.history(start=start.date().isoformat(), end=end.date().isoformat(), interval="1d")

    # 3. تسطيح الأعمدة (Flattening) لحل مشكلة الشركات الأمريكية والمغربية
    if isinstance(df.columns, MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if df.empty:
        # محاولة أخيرة بطلب شهر واحد بدون تواريخ محددة
        df = ticker_obj.history(period="1mo")
        if isinstance(df.columns, MultiIndex):
            df.columns = df.columns.get_level_values(0)

    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {yf_symbol}")

    df = df.sort_index()
    candles = []
    for ts, row in df.iterrows():
        candles.append({
            "time": ts.strftime('%Y-%m-%d'),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row.get("Volume", 0) or 0),
        })
    return candles

@app.get("/{ticker}")
def get_stock(ticker: str, days: int = 60):
    t = ticker.strip().upper()
    
    # حل مشكلة الرموز التي تبدأ بـ ^ (ناسداك والمازي)
    # إذا كتب المستخدم IXIC سنضيف نحن ^
    # إذا كتب MASI سنضيف نحن ^
    
    if t in ["IXIC", "GSPC", "DJI", "MASI"]:
        yf_symbol = f"^{t}"
    elif t.startswith("INDEX"): # في حال كتب INDEX_MASI مثلاً
        yf_symbol = f"^{t.split('_')[1]}"
    elif "." not in t and t not in ["MSFT", "AAPL", "NVDA"]:
        yf_symbol = f"{t}.MA"
    else:
        yf_symbol = t

    return {
        "ticker": t,
        "yf_symbol": yf_symbol,
        "candles": _build_candles(yf_symbol, days)
    }
