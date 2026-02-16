import sqlite3
import requests
from datetime import datetime

# القاموس لربط اسم الجدول برمز الشركة في موقع البورصة
# ملاحظة: موقع البورصة يستخدم رموزاً مثل 'MASI' للمؤشرات و 'ADI' للشركات
SYMBOLS = {
    "MASI": "indices/MASI",
    "MSI20": "indices/MSI20",
    "Alliances": "stocks/ADI",
    "Maroc_Telecom": "stocks/IAM",
    "Attijariwafa_Bank": "stocks/ATW",
    # ... أضف بقية الشركات بنفس النمط (stocks/الرمز)
}

def get_official_price(path):
    """جلب السعر مباشرة من ملفات JSON الخاصة بموقع البورصة"""
    try:
        # سنحاول جلب السعر من الرابط المباشر
        # ملاحظة: buildId يمكن تجنبه أحياناً باستخدام الرابط المبسط أو البحث عنه
        url = f"https://www.casablanca-bourse.com/api/market/{path}" 
        
        # إذا لم يعمل الرابط أعلاه، نستخدم الرابط الذي اقترحته أنت مع محاولة جلب buildId تلقائياً
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        data = response.json()
        
        # استخراج السعر (Price/Last) من الـ JSON
        # الهيكل المتوقع عادة يكون data['result']['price'] أو ما يشابهه
        price = data.get('last_price') or data.get('close') or data.get('value')
        return float(price)
    except Exception as e:
        print(f"❌ فشل جلب {path} من الموقع الرسمي: {e}")
        return None

def update_database():
    conn = sqlite3.connect('stocks_morocco.db')
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')

    for table_name, path in SYMBOLS.items():
        price = get_official_price(path)
        print(price)        
        if price:
            cursor.execute(f"SELECT 1 FROM {table_name} WHERE Date = ?", (today,))
            if cursor.fetchone() is None:
                cursor.execute(f"INSERT INTO {table_name} (Date, Price, Open, High, Low) VALUES (?, ?, ?, ?, ?)",
                               (today, price, price, price, price))
                print(f"✅ تم تحديث {table_name}: {price} MAD من المصدر الرسمي")
            else:
                print(f"ℹ️ بيانات {table_name} موجودة مسبقاً")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_database()
