# scripts/export_openapi.py
# -*- coding: utf-8 -*-
import json
import sys

# نحاول استيراد تطبيق FastAPI من main.py أو app.py
app = None
try:
    from MasiAPI.main import app as _app
    app = _app
except Exception:
    try:
        from app import app as _app
        app = _app
    except Exception as e:
        print("❌ Could not import FastAPI app from main.py or app.py")
        print(e)
        sys.exit(1)

from fastapi.openapi.utils import get_openapi
import os

os.makedirs("docs", exist_ok=True)

# 1) التصدير الافتراضي (نستخدم ميتاداتا FastAPI الحالية)
schema_base = get_openapi(
    title=app.title,
    version=app.version,
    description=app.description,
    routes=app.routes,
)

# 2) نسخة إنجليزية — نضبط العنوان والوصف (يمكنك تعديل النصوص أدناه)
schema_en = dict(schema_base)
schema_en["info"]["title"] = "Morocco Market API – English"
schema_en["info"]["description"] = (
    "OpenAPI specification for Morocco Market API (Company table only).\n\n"
    "Features:\n"
    "- Alphabetical company list\n"
    "- Latest trading day snapshot\n"
    "- Symbol range queries (week, month, 3/6 months, year, 3 years)\n"
    "- All results sorted from newest to oldest\n"
)

# 3) نسخة عربية — نضبط العنوان والوصف
schema_ar = dict(schema_base)
schema_ar["info"]["title"] = "واجهة سوق المغرب – العربية"
schema_ar["info"]["description"] = (
    "مخطط OpenAPI لواجهة سوق المغرب (الاعتماد على جدول Company فقط).\n\n"
    "الميزات:\n"
    "- قائمة الشركات مرتبة أبجديًا\n"
    "- أحدث يوم تداول في القاعدة\n"
    "- استعلامات فترات جاهزة (أسبوع، شهر، 3/6 أشهر، سنة، 3 سنوات)\n"
    "- النتائج دائمًا من الأحدث إلى الأقدم\n"
)

with open("docs/openapi-en.json", "w", encoding="utf-8") as f:
    json.dump(schema_en, f, ensure_ascii=False, indent=2)

with open("docs/openapi-ar.json", "w", encoding="utf-8") as f:
    json.dump(schema_ar, f, ensure_ascii=False, indent=2)

print("✅ Generated docs/openapi-en.json and docs/openapi-ar.json")
