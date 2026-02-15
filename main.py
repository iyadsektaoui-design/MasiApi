import yfinance as yf
import pandas as pd
from pandas import MultiIndex
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def _build_candles(yf_symbol: str, days: int):
    try:
        # الحل: حذفنا الـ session تماماً كما طلبت الرسالة
        ticker_obj = yf.Ticker(yf_symbol)
        
        # نستخدم period لجلب البيانات
        fetch_period = "3mo" if days <= 60 else "1y"
        
        # جلب البيانات (المكتبة ستستخدم curl_cffi داخلياً إذا كانت مثبتة)
        df = ticker_obj.history(period=fetch_period, interval="1d", auto_adjust=True)

        # تسطيح الأعمدة (Flattening)
        if isinstance(df.columns, MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if df.empty:
            # محاولة بديلة لـ MASI إذا فشل الرمز الأول
            if "MASI" in yf_symbol:
                df = yf.Ticker("MASI.CAS").history(period="1mo")
                if isinstance(df.columns, MultiIndex):
                    df.columns = df.columns.get_level_values(0)
            
            if df.empty:
                raise ValueError(f"No data returned for {yf_symbol}")

        # تنظيف واقتطاع البيانات
        df = df.sort_index().tail(days)
        
        candles = []
        for ts, row in df.iterrows():
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
        raise Exception(f"Data Fetch Error: {str(e)}")

@app.get("/{ticker}")
def get_stock(ticker: str, days: int = 60):
    t = ticker.strip().upper()
    
    # تحويل الرموز (Logic Fix)
    if t == "MASI":
        yf_symbol = "^MASI"
    elif t in ["IXIC", "GSPC", "DJI"]:
        yf_symbol = f"^{t}"
    elif "." not in t and t not in ["MSFT", "AAPL", "NVDA", "TSLA"]:
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
        return {
            "status": "error",
            "message": str(e)
        }
