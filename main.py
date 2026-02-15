from datetime import datetime, timedelta, timezone
from pandas import MultiIndex
import yfinance as yf
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CasaBourse YFinance API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_candles(yf_symbol: str, days: int):
    """جلب بيانات يومية من yfinance وتحويلها إلى شموع قياسية."""
    if days <= 0:
        raise HTTPException(status_code=400, detail="days must be > 0")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    df = yf.download(
        yf_symbol,
        start=start.date().isoformat(),
        end=end.date().isoformat(),
        interval="1d",
        auto_adjust=False,
        progress=False,
    )
        # إذا رجعت الأعمدة كـ MultiIndex مثل ('Open', 'MSFT') نحولها لأسماء بسيطة
    if isinstance(df.columns, MultiIndex):
        df.columns = [c[0] for c in df.columns]

    # لا توجد أي بيانات
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No data for this ticker")

    cols = list(df.columns)

    # إذا لم تكن أعمدة OHLC موجودة نحاول استعمال Adj Close
    if not all(c in cols for c in ["Open", "High", "Low", "Close"]):
        if "Adj Close" in cols:
            adj = df["Adj Close"]
            df = df.copy()
            df["Open"] = adj
            df["High"] = adj
            df["Low"] = adj
            df["Close"] = adj
        else:
            raise HTTPException(
                status_code=502,
                detail=f"Upstream data missing OHLC columns. Got columns: {cols}",
            )

    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df = df.sort_index()

    candles = []
    for ts, row in df.iterrows():
        dt = ts.to_pydatetime().replace(tzinfo=timezone.utc)
        candles.append(
            {
                "time": dt.isoformat(),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row.get("Volume", 0) or 0),
            }
        )

    if not candles:
        raise HTTPException(status_code=404, detail="No candles parsed")

    return candles


@app.get("/")
def home():
    return {"message": "API بورصة الدار البيضاء تعمل بنجاح!"}


@app.get("/stock/{ticker}")
def get_stock(ticker: str, days: int = 365):
    """
    أمثلة:
    - /stock/MSFT?days=60
    - /stock/SPY?days=365
    """
    t = ticker.strip()

    # MASI → ^MASI (إن وجد في Yahoo؛ غالبًا لا يوجد)
    if t.upper() == "MASI":
        yf_symbol = "^MASI"
    else:
        yf_symbol = t

    candles = _build_candles(yf_symbol, days)

    return {
        "ticker": t.upper(),
        "yf_symbol": yf_symbol,
        "source": "yfinance",
        "days": days,
        "count": len(candles),
        "candles": candles,
    }
