import sqlite3
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "stocks_morocco.db"

# لاحظ هنا المسار أصبح /{symbol} مباشرة ليتوافق مع رابطك الذي يعمل
@app.get("/{symbol}")
def get_stock_data(symbol: str, days: int = Query(None)):
    try:
        conn = sqlite3.connect(DB_NAME)
        # تحويل اسم الشركة ليتوافق مع اسم الجدول (تبديل المسافات بشرطات سفلية)
        table_name = symbol.replace(" ", "_")
        
        # 1. بناء الاستعلام مع ترتيب تنازلي لجلب الأحدث أولاً
        query = f"SELECT * FROM {table_name} ORDER BY Date DESC"
        
        # 2. تطبيق الـ LIMIT فقط إذا تم إرسال الرقم في الرابط
        if days is not None and days > 0:
            query += f" LIMIT {days}"
            
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            return {"status": "error", "message": "لم يتم العثور على بيانات لهذه الشركة"}

        # 3. قلب البيانات لتصبح من الأقدم للأحدث (ضروري جداً للرسم البياني)
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
        return {"status": "error", "message": str(e)}
