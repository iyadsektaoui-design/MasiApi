# scripts/postprocess_html.py
# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ARABIC_STYLE = """
<style>
@font-face {
  font-family: 'Noto Sans Arabic';
  src: url('./NotoSansArabic-VariableFont_wdth,wght.ttf') format('truetype');
  font-weight: 100 900;
  font-style: normal;
}
html, body {
  direction: rtl;
  font-family: 'Noto Sans Arabic', system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial, sans-serif;
}
body .menu-content, body .api-content, body .redoc-wrap {
  direction: rtl !important;
  text-align: right !important;
}
</style>
"""

def inject_css(html_path: str):
    p = Path(html_path)
    if not p.exists():
        print(f"❌ HTML not found: {html_path}")
        sys.exit(1)
    content = p.read_text(encoding="utf-8")
    # حقن الستايل قبل </head>
    if "</head>" in content:
        content = content.replace("</head>", ARABIC_STYLE + "\n</head>")
    else:
        content = ARABIC_STYLE + content
    p.write_text(content, encoding="utf-8")
    print(f"✅ Injected RTL+font CSS into {html_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/postprocess_html.py docs/index-ar.html")
        sys.exit(1)
    inject_css(sys.argv[1])
