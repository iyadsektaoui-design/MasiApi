import yfinance as yf
import pandas as pd
from pandas import MultiIndex
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
import requests

app = FastAPI(title="CasaBourse AI API")

# إعدادات CORS للسماح بالاتصال من تطبيقات الويب
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _build_candles(yf_symbol: str, days: int):
    try:
        # 1. إنشاء جلسة متصفح حقيقية لتجاوز حظر ياهو للبيانات الدولية
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Connection': 'keep-alive'
        })

        # 2. إعداد الكائن واستخدام فترات زمنية ثابتة (أكثر استقراراً للمؤشرات)
        ticker_obj = yf.Ticker(yf_symbol, session=session)
        
        # نختار فترة تغطي عدد الأيام المطلوب
        if days <= 30:
            period = "1mo"
        elif days <= 250:
            period = "1y"
        else:
            period = "5y"

        # جلب البيانات
        df = ticker_obj.history(period=period, interval="1d")

        # 3. حل مشكلة الـ MultiIndex (تسطيح الأعمدة المتداخلة)
        if isinstance(df.columns, MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 4. معالجة حالات البيانات الفارغة (خاصة بمؤشر MASI)
        if df.empty:
            if "MASI" in yf_symbol:
                # محاولة الرمز البديل للمغرب
                df = yf.Ticker("MASI.CAS", session=session).history(period="1mo")
                if isinstance(df.columns, MultiIndex):
                    df.columns = df.columns.get_level_values(0)
            
            if df.empty:
                raise ValueError(f"No data returned for {yf_symbol}")

        # 5. تنظيف وترتيب البيانات
        df = df.sort_index()
        df = df.tail(days) # نأخذ فقط الأيام المطلوبة من النهاية

        candles = []
        for ts, row in df.iterrows():
            # التعامل مع القيم المفقودة في الحجم (Volume) خاصة للمؤشرات
            vol = float(row["Volume"]) if "Volume" in row and pd.notna(row["Volume"]) else 0
            
            candles.append({
                "time": ts.strftime('%Y-%m-%d'),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": vol
            })
        
        return candles

    except Exception as e:
        print(f"Error for {yf_symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"status": "online", "message": "API is running. Use /{ticker} to get data."}

@app.get("/{ticker}")
def get_stock(ticker: str, days: int = 60):
    t = ticker.strip().upper()
    
    # منطق تحويل الرموز الذكي:
    # 1. إذا كان الرمز مؤشراً معروفاً
    if t in ["MASI", "IXIC", "GSPC", "DJI", "FTSE"]:
        yf_symbol = f"^{t}"
    
    # 2. إذا كان يحتوي بالفعل على نقطة أو يبدأ بـ ^
    elif "." in t or t.startswith("^"):
        yf_symbol = t
        
    # 3. إذا كان سهماً عالمياً مشهوراً لا يحتاج لاحقة
    elif t in ["MSFT", "AAPL", "GOOGL", "TSLA", "NVDA", "BTC-USD"]:
        yf_symbol = t
        
    # 4. أي شيء آخر نعتبره سهماً مغربياً
    else:
        yf_symbol = f"{t}.MA"

    data = _build_candles(yf_symbol, days)
    
    return {
        "ticker": t,
        "yf_symbol": yf_symbol,
        "count": len(data),
        "candles": data
    }
