import sqlite3
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "stocks_morocco.db"

@app.get("/stocks")
def list_companies():
    """جلب قائمة بأسماء الشركات المتاحة في القاعدة"""
    conn = sqlite3.connect(DB_NAME)
    query = "SELECT name FROM sqlite_master WHERE type='table';"
    tables = pd.read_sql_query(query, conn)
    conn.close()
    return {"companies": tables['name'].tolist()}

@app.get("/data/{symbol}")
def get_stock_data(symbol: str):
    """جلب بيانات شركة معينة لتقديمها لتطبيق فلوتر"""
    try:
        conn = sqlite3.connect(DB_NAME)
        # التأكد من تنظيف اسم الجدول لمنع SQL Injection
        table_name = symbol.replace(" ", "_")
        
        # جلب البيانات وترتيبها من الأقدم للأحدث (مهم جداً للرسم البياني)
        query = f"SELECT * FROM {table_name} ORDER BY Date ASC"
        df = pd.read_sql_query(query, conn)
        conn.close()

        # تحويل البيانات لصيغة الشموع المتوافقة مع فلوتر
        candles = []
        for _, row in df.iterrows():
            candles.append({
                "time": row['Date'],
                "open": row['Open'],
                "high": row['High'],
                "low": row['Low'],
                "close": row['Price']
            })
        
        return {
            "status": "success",
            "symbol": symbol,
            "count": len(candles),
            "candles": candles
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Company {symbol} not found or error occurred.")
