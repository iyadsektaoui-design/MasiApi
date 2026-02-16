import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# قاموس لربط أسماء جداولك برموزها في جوجل
# أضف بقية الشركات الـ 20 هنا بنفس النمط
SYMBOLS = {
    "Alliances": "ADI",
    "Maroc_Telecom": "IAM",
    "Douja_Prom_Addoha": "ADH"
}

def get_price(symbol):
    try:
        url = f"https://www.google.com/finance/quote/{symbol}:INDEXMAR"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        price = soup.find("div", {"class": "YMlS7e"}).text.replace(",", "").replace("MAD", "").strip()
        return float(price)
    except:
        return None

def update_database():
    conn = sqlite3.connect('stocks_morocco.db')
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')

    for table_name, google_symbol in SYMBOLS.items():
        price = get_price(google_symbol)
        if price:
            # التأكد من عدم تكرار اليوم
            cursor.execute(f"SELECT * FROM {table_name} WHERE Date = ?", (today,))
            if cursor.fetchone() is None:
                # إضافة السعر الجديد (سنعتبر الـ Open/High/Low هو نفس سعر الإغلاق لتبسيط التحديث الآلي)
                cursor.execute(f"INSERT INTO {table_name} (Date, Price, Open, High, Low) VALUES (?, ?, ?, ?, ?)",
                               (today, price, price, price, price))
                print(f"✅ تم إضافة سعر {table_name} ليوم {today}")
            else:
                print(f"ℹ️ بيانات {table_name} موجودة مسبقاً لهذا اليوم")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_database()
