import sqlite3
import requests
import re
import json
from datetime import datetime

# إيقاف تحذيرات SSL
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_build_id():
    """استخراج buildId الديناميكي من موقع البورصة"""
    try:
        url = "https://www.casablanca-bourse.com/fr/live-market/indices"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        # البحث عن buildId داخل كود الصفحة
        match = re.search(r'"buildId":"(.*?)"', response.text)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"❌ فشل استخراج buildId: {e}")
    return None

def get_official_price(build_id, path):
    """جلب البيانات باستخدام الرابط الذي اقترحته أنت"""
    try:
        # الرابط الصحيح الذي يعمل في موقع البورصة
        url = f"https://www.casablanca-bourse.com/_next/data/{build_id}/fr/live-market/{path}.json"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        
        data = response.json()
        
        # استخراج السعر من هيكل JSON الخاص بـ Next.js
        # الهيكل عادة: pageProps -> data -> last_value أو ما يشابهه
        page_props = data.get('pageProps', {})
        stock_data = page_props.get('data', {})
        
        # محاولة إيجاد السعر في عدة حقول محتملة
        price = stock_data.get('last_value') or stock_data.get('last_price') or stock_data.get('close')
        
        return float(price) if price else None
    except Exception as e:
        print(f"❌ خطأ في تحليل بيانات {path}: {e}")
        return None

def update_database():
    build_id = get_build_id()
    if not build_id:
        print("🚫 لا يمكن الاستمرار بدون buildId")
        return

    print(f"🔍 تم العثور على Build ID: {build_id}")

    conn = sqlite3.connect('stocks_morocco.db')
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')

    # تأكد من تطابق المسارات مع موقع البورصة
    SYMBOLS = {
        "MASI": "indices/MASI",
        "MSI20": "indices/MSI20",
        "Alliances": "stocks/ADI",
        "Maroc_Telecom": "stocks/IAM"
    }

    for table_name, path in SYMBOLS.items():
        price = get_official_price(build_id, path)
        if price:
            cursor.execute(f"SELECT 1 FROM {table_name} WHERE Date = ?", (today,))
            if cursor.fetchone() is None:
                cursor.execute(f"INSERT INTO {table_name} (Date, Price, Open, High, Low) VALUES (?, ?, ?, ?, ?)",
                               (today, price, price, price, price))
                print(f"✅ {table_name} تم تحديثه: {price}")
            else:
                print(f"ℹ️ {table_name} موجود مسبقاً")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_database()
