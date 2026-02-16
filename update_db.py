import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd

# القاموس الشامل لرموز جوجل فاينانس
# المفتاح (Key): هو اسم الجدول في قاعدة بياناتك (تأكد أنه يطابق تماماً)
# القيمة (Value): هو الرمز في Google Finance
SYMBOLS = {
    "MASI": "MASI",                 # مؤشر مازي
    "MSI20": "MSI20",               # مؤشر msi20
    "Alliances": "ADI",             # شركة اليانس (من ملفك ADI)
    "Maroc_Telecom": "IAM",         # اتصالات المغرب
    "Attijariwafa_Bank": "ATW",     # التجاري وفا بنك
    "BCP": "BCP",                   # البنك الشعبي
    "Bank_Of_Africa": "BOA",        # بنك أفريقيا
    "LafargeHolcim_Maroc": "LHM",   # لافارج هولسيم
    "Douja_Prom_Addoha": "ADH",     # الضحى
    "Taqa_Morocco": "TQM",          # طاقة المغرب
    "Marsa_Maroc": "SOD",           # مرسى المغرب
    "Ciments_du_Maroc": "CMA",      # أسمنت المغرب
    "Wafa_Assurance": "WAA",        # وفا ضمان
    "Cosumar": "CSM",               # كوسومار
    "Label_Vie": "LBV",             # لابل في
    "Managem": "MNG",               # مناجم
    "Sonasid": "SID",               # سوناسيد
    "Sodep_Marsa": "SOD",
    "TotalEnergies_Maroc": "TMA",   # توتال المغرب
    "Akdital": "AKT",               # أكديمتال
    "Aradei_Capital": "ARD",        # أرادي كابيتال
    "Mutandis": "MUT"               # موتانديس
}

def get_live_data(google_symbol):
    """جلب السعر من جوجل فاينانس"""
    try:
        url = f"https://www.google.com/finance/quote/{google_symbol}:INDEXMAR"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # البحث عن خلية السعر
        price_str = soup.find("div", {"class": "YMlS7e"}).text
        price = float(price_str.replace(",", "").replace("MAD", "").strip())
        return price
    except Exception as e:
        print(f"⚠️ فشل جلب {google_symbol}: {e}")
        return None

def update_database():
    conn = sqlite3.connect('stocks_morocco.db')
    cursor = conn.cursor()
    # تاريخ اليوم بصيغة YYYY-MM-DD
    today = datetime.now().strftime('%Y-%m-%d')

    for table_name, google_code in SYMBOLS.items():
        price = get_live_data(google_code)
        
        if price:
            try:
                # التحقق هل السعر موجود مسبقاً لهذا التاريخ لمنع التكرار
                cursor.execute(f"SELECT 1 FROM {table_name} WHERE Date = ?", (today,))
                if cursor.fetchone() is None:
                    # إضافة السعر (نجعل 시عر الفتح والأعلى والأسفل هو نفس الإغلاق للتحديث السريع)
                    cursor.execute(f"INSERT INTO {table_name} (Date, Price, Open, High, Low) VALUES (?, ?, ?, ?, ?)",
                                   (today, price, price, price, price))
                    print(f"✅ تم تحديث {table_name}: {price} MAD")
                else:
                    print(f"ℹ️ بيانات {table_name} موجودة بالفعل ليوم {today}")
            except sqlite3.OperationalError:
                print(f"❌ خطأ: الجدول {table_name} غير موجود في القاعدة!")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_database()
