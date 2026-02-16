import sqlite3
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "stocks_morocco.db"

@app.get("/data/{symbol}")
def get_stock_data(symbol: str, days: int = Query(None)):
    try:
        conn = sqlite3.connect(DB_NAME)
        table_name = symbol.replace(" ", "_")
        
        # التأكد من جلب البيانات تنازلياً للحصول على الأحدث أولاً
        query = f"SELECT * FROM {table_name} ORDER BY Date DESC"
        
        # إضافة LIMIT مباشرة في استعلام SQL إذا وُجد متغير days
        if days is not None and days > 0:
            query += f" LIMIT {days}"
            
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            return {"status": "error", "message": "No data found"}

        # قلب البيانات لتصبح من الأقدم للأحدث للرسم البياني
        df = df.iloc[::-1]

        candles = []
        for _, row in df.iterrows():
            candles.append({
                "time": row['Date'],
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Price'])
            })
        
        return {
            "status": "success",
            "symbol": symbol,
            "count": len(candles),
            "candles": candles
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
