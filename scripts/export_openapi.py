# scripts/export_openapi.py
# -*- coding: utf-8 -*-

import json
import sys

# --------------------------------------------
#  استيراد تطبيق FastAPI من المسار الصحيح:
#  MasiAPI/main.py  →  from MasiAPI.main import app
# --------------------------------------------
try:
    from MasiAPI.main import app
    print("✅ Successfully imported FastAPI app from MasiAPI/main.py")
except Exception as e:
    print("❌ ERROR: Could not import FastAPI app from MasiAPI/main.py")
    print("سبب الخطأ:", e)
    sys.exit(1)

from fastapi.openapi.utils import get_openapi
import os

# التأكد من وجود مجلد docs/
os.makedirs("docs", exist_ok=True)

# 1) المخطط الأساسي
schema_base = get_openapi(
    title=app.title,
    version=app.version,
    description=app.description,
    routes=app.routes,
)

# 2) النسخة الإنجليزية
schema_en = dict(schema_base)
schema_en["info"]["title"] = "Morocco Market API – English"
schema_en["info"]["description"] = (
    "English OpenAPI documentation for Morocco Market API.\n"
    "Features include:\n"
    "- Alphabetical company list\n"
    "- Latest day snapshot\n"
    "- Time ranges: week, month, 3/6 months, year, 3 years\n"
    "- All results sorted newest-to-oldest\n"
)

# 3) النسخة العربية
schema_ar = dict(schema_base)
schema_ar["info"]["title"] = "واجهة سوق المغرب – العربية"
schema_ar["info"]["description"] = (
    "مخطط OpenAPI لواجهة سوق المغرب.\n"
    "الميزات:\n"
    "- قائمة الشركات مرتبة أبجديًا\n"
    "- أحدث يوم تداول\n"
    "- فترات جاهزة: أسبوع، شهر، 3/6 أشهر، سنة، 3 سنوات\n"
    "- النتائج من الأحدث إلى الأقدم\n"
)

# كتابة الملفات
with open("docs/openapi-en.json", "w", encoding="utf-8") as f:
    json.dump(schema_en, f, ensure_ascii=False, indent=2)

with open("docs/openapi-ar.json", "w", encoding="utf-8") as f:
    json.dump(schema_ar, f, ensure_ascii=False, indent=2)

print("✅ Generated: docs/openapi-en.json")
print("✅ Generated: docs/openapi-ar.json")
