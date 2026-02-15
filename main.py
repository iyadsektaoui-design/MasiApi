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
        # تحديد الفترة
        period = "1mo" if days <= 30 else "1y"
        if days > 365: period = "5y"

        # استخدام Ticker لجلب البيانات (طريقة أكثر استقراراً من download)
        ticker_obj = yf.Ticker(yf_symbol)
        
        # جلب البيانات التاريخية
        df = ticker_obj.history(period=period)

        # 1. حل مشكلة الـ MultiIndex (التسطيح)
        if isinstance(df.columns, MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 2. التحقق من وجود بيانات
        if df.empty:
            # محاولة أخيرة برمز بديل إذا كان مؤشراً
            if yf_symbol == "^MASI":
                df = yf.Ticker("MASI.CAS").history(period="1mo")
                if isinstance(df.columns, MultiIndex):
                    df.columns = df.columns.get_level_values(0)
            
            if df.empty:
                raise ValueError(f"Yahoo Finance returned no data for {yf_symbol}")

        # 3. تنظيف البيانات
        df = df.sort_index()
        # نأخذ فقط عدد الأيام المطلوب من النهاية
        df = df.tail(days)

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

    except Exception as e:
        print(f"Error fetching {yf_symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Error: {str(e)}")

@app.get("/{ticker}")
def get_stock(ticker: str, days: int = 60):
    t = ticker.strip().upper()
    
    # منطق تحويل الرموز
    if t in ["IXIC", "GSPC", "DJI", "MASI"]:
        yf_symbol = f"^{t}"
    elif "." not in t and t not in ["MSFT", "AAPL", "NVDA", "TSLA"]:
        yf_symbol = f"{t}.MA"
    else:
        yf_symbol = t

    data = _build_candles(yf_symbol, days)
    
    return {
        "status": "success",
        "ticker": t,
        "yf_symbol": yf_symbol,
        "count": len(data),
        "data": data
    }
