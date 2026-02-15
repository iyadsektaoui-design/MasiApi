from datetime import datetime, timedelta, timezone
from pandas import MultiIndex
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CasaBourse YFinance API", version="0.1.0")

# إعدادات الـ CORS للسماح بالوصول من أي مكان
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _build_candles(yf_symbol: str, days: int):
    """جلب بيانات من yfinance وتسطيح الأعمدة المتداخلة (MultiIndex)."""
    if days <= 0:
        raise HTTPException(status_code=400, detail="days must be > 0")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    # تحميل البيانات من ياهو فاينانس
    df = yf.download(
        yf_symbol,
        start=start.date().isoformat(),
        end=end.date().isoformat(),
        interval="1d",
        auto_adjust=False,
        progress=False,
    )

    # --- حل مشكلة الـ MultiIndex (التسطيح) ---
    if isinstance(df.columns, MultiIndex):
        # نأخذ المستوى الأول فقط (مثل Close) ونلغي المستوى الثاني (مثل MSFT)
        df.columns = df.columns.get_level_values(0)
    # ---------------------------------------

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for {yf_symbol}")

    required = ["Open", "High", "Low", "Close"]
    if not all(c in df.columns for c in required):
        raise HTTPException(
            status_code=502,
            detail=f"Missing OHLC columns. Available: {list(df.columns)}",
        )

    df = df.dropna(subset=required)
    df = df.sort_index()

    candles = []
    for ts, row in df.iterrows():
        dt_str = ts.strftime('%Y-%m-%d')
        candles.append({
            "time": dt_str,
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row.get("Volume", 0) or 0),
        })

    return candles

@app.get("/")
def home():
    return {"message": "API بورصة الدار البيضاء تعمل بنجاح!"}

@app.get("/stock/{ticker}")
def get_stock(ticker: str, days: int = 365):
    t = ticker.strip().upper()

    # تحويل الرموز لتتوافق مع بورصة الدار البيضاء في ياهو
    if t == "MASI":
        yf_symbol = "^MASI"
    elif "." not in t:
        # إذا لم يكن من الأسهم الأمريكية الكبرى، أضف لاحقة المغرب
        if t in ["MSFT", "AAPL", "GOOGL", "TSLA"]:
            yf_symbol = t
        else:
            yf_symbol = f"{t}.MA"
    else:
        yf_symbol = t

    candles = _build_candles(yf_symbol, days)

    return {
        "ticker": t,
        "yf_symbol": yf_symbol,
        "count": len(candles),
        "candles": candles,
    }

# مسار ليعمل الرابط مباشرة https://masiapi.onrender.com/MASI
@app.get("/{ticker}")
def get_stock_direct(ticker: str, days: int = 60):
    return get_stock(ticker, days)
