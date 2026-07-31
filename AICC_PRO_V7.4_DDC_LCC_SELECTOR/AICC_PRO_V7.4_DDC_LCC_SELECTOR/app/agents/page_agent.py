import re

FILENAME_HINTS = [
    ("الغلاف الأمامي", ["front-cover", "front_cover", "cover-front", "غلاف"]),
    ("الغلاف الخلفي", ["back-cover", "back_cover", "cover-back"]),
    ("صفحة العنوان", ["title-page", "title_page", "titlepage"]),
    ("صفحة حقوق النشر", ["copyright", "rights"]),
    ("الفهرس", ["contents", "toc", "فهرس"]),
    ("المقدمة", ["introduction", "preface", "مقدمة"]),
    ("صفحة الرقم الدولي ISBN", ["isbn"]),
    ("كعب الكتاب", ["spine", "book-spine"]),
]

TEXT_RULES = [
    ("صفحة الرقم الدولي ISBN", [r"\bISBN\b", r"ردمك", r"الرقم الدولي"]),
    ("صفحة حقوق النشر", [r"حقوق الطبع", r"جميع الحقوق محفوظة", r"copyright", r"الطبعة"]),
    ("الفهرس", [r"الفهرس", r"المحتويات", r"contents"]),
    ("المقدمة", [r"^\s*المقدمة", r"^\s*تمهيد", r"preface", r"introduction"]),
    ("صفحة العنوان", [r"اسم الكتاب", r"عنوان الكتاب", r"تأليف", r"المؤلف", r"دار النشر"]),
]

def detect_page_type(text, filename=""):
    lower_name = (filename or "").lower()
    for page_type, hints in FILENAME_HINTS:
        if any(hint in lower_name for hint in hints):
            return page_type

    source = text or ""
    for page_type, patterns in TEXT_RULES:
        if any(re.search(pattern, source, re.I | re.M) for pattern in patterns):
            return page_type

    meaningful = [line for line in source.splitlines() if line.strip()]
    if len(meaningful) <= 10:
        return "غلاف أو صفحة عنوان"
    return "صفحة داخلية"
