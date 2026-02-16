import sqlite3
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "stocks_morocco.db"

@app.get("/data/{symbol}")
def get_stock_data(symbol: str, days: Optional[int] = Query(None, description="عدد الأيام الأخيرة المطلوبة")):
    """
    جلب بيانات شركة معينة مع إمكانية تحديد عدد الأيام الأخيرة.
    مثال: /data/Alliances?days=60
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        table_name = symbol.replace(" ", "_")
        
        # إذا طلب المستخدم عدداً معيناً من الأيام، نستخدم LIMIT مع ترتيب تنازلي أولاً لجلب الأحدث
        if days:
            query = f"SELECT * FROM {table_name} ORDER BY Date DESC LIMIT {days}"
        else:
            # إذا لم يحدد، نجلب كل البيانات
            query = f"SELECT * FROM {table_name} ORDER BY Date DESC"
            
        df = pd.read_sql_query(query, conn)
        conn.close()

        # بما أننا جلبنا الأحدث (DESC)، نحتاج لقلب القائمة (Reverse) 
        # لكي يظهر الرسم البياني في فلوتر من الأقدم للأحدث بشكل صحيح
        df = df.iloc[::-1]

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
            "requested_days": days if days else "all",
            "count": len(candles),
            "candles": candles
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"خطأ: التأكد من اسم الشركة أو قاعدة البيانات. {str(e)}")
