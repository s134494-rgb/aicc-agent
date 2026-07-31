import re
from collections import Counter

STOPWORDS = {
    "هذا","هذه","ذلك","التي","الذي","على","من","في","إلى","عن","مع","تم","كما","أو","هو","هي",
    "كتاب","الكتاب","الفصل","المقدمة","المحتويات","الصفحة","صفحة","اللغة","العربية","استخدام",
}

def analyze_subject(pages):
    selected = [
        p for p in pages
        if p.get("page_type") in {"الفهرس", "المقدمة", "صفحة داخلية"}
    ]
    text = "\n".join(p.get("text", "") for p in selected)
    words = re.findall(r"[\u0600-\u06FFA-Za-z]{4,}", text)
    normalized = [w.strip("ـ") for w in words if w not in STOPWORDS]
    keywords = [word for word, _ in Counter(normalized).most_common(12)]

    summary_source = ""
    for page in selected:
        if page.get("page_type") == "المقدمة" and len(page.get("text", "")) > 80:
            summary_source = page["text"]
            break

    summary = re.sub(r"\s+", " ", summary_source).strip()[:600]
    return {
        "keywords": keywords,
        "summary_draft": summary,
        "method": "تحليل محلي إحصائي للنص؛ يحتاج مراجعة بشرية",
    }
