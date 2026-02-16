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
    """جلب السعر مع تعطيل التحقق من شهادة الـ SSL لتففي الخطأ"""
    try:
        # الرابط الرسمي المباشر
        url = f"https://www.casablanca-bourse.com/api/market/{path}" 
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # إضافة verify=False لتجاهل خطأ شهادة الأمان SSL
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        
        # لمنع ظهور رسالة تحذير مزعجة في السجلات (اختياري)
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        data = response.json()
        
        # استخراج السعر بناءً على بنية JSON المتوقعة
        # عادة ما يكون السعر في حقل 'last_price' أو 'price'
        price = data.get('last_price') or data.get('price') or data.get('value')
        print(price)
        if price:
            return float(price)
        return None
        
    except Exception as e:
        print(f"❌ فشل جلب {path}: {str(e)}")
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
