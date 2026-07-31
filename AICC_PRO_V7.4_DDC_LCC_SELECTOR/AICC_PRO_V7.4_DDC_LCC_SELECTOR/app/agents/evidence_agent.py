import re
from collections import defaultdict

FIELD_PATTERNS = {
    "title": [
        r"(?:اسم\s*الكتاب|عنوان\s*الكتاب|العنوان|book\s*title)\s*[:：-]?\s*(.+)",
    ],
    "author": [
        r"(?:تأليف|المؤلف(?:ون)?|إعداد|اعداد|بقلم|تحرير)\s*[:：-]?\s*(.+)",
        r"(?:author|written by)\s*[:：-]?\s*(.+)",
    ],
    "publisher": [
        r"(?:الناشر|دار\s*النشر|نشر\s*وتوزيع|نشر بواسطة)\s*[:：-]?\s*(.+)",
        r"(?:publisher|published by)\s*[:：-]?\s*(.+)",
    ],
    "edition": [
        r"(?:الطبعة)\s*[:：-]?\s*(.+)",
        r"(?:edition)\s*[:：-]?\s*(.+)",
    ],
    "publication_place": [r"(?:مكان\s*النشر)\s*[:：-]?\s*(.+)"],
    "translator": [r"(?:ترجمة|المترجم)\s*[:：-]?\s*(.+)"],
    "editor": [r"(?:تحرير|مراجعة|المحرر)\s*[:：-]?\s*(.+)"],
    "series": [r"(?:السلسلة|سلسلة)\s*[:：-]?\s*(.+)"],
}

def clean_value(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip(" .،,:：-")
    return value[:300]

def collect_evidence(pages):
    evidence = defaultdict(list)
    for page in pages:
        text = page.get("text", "")
        page_type = page.get("page_type", "")
        filename = page.get("filename", "")
        for field, patterns in FIELD_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.I):
                    value = clean_value(match.group(1).splitlines()[0])
                    if value:
                        evidence[field].append({
                            "value": value,
                            "page_type": page_type,
                            "filename": filename,
                            "source": "explicit_label",
                            "quality_score": page.get("quality_score", 0),
                            "ocr_agreement": (page.get("ocr_metrics") or {}).get("agreement", 0),
                        })
    return dict(evidence)

def evidence_conflicts(evidence):
    """Report material disagreements instead of silently choosing one OCR value."""
    conflicts=[]
    for field, items in (evidence or {}).items():
        normalized={}
        for item in items:
            key=re.sub(r"[\W_]+","",item.get("value","")).lower()
            if key:
                normalized.setdefault(key,[]).append(item)
        # OCR differences on one weak page are not independent evidence. Report a
        # conflict only when distinct values have usable sources.
        usable = [group for group in normalized.values()
                  if any(item.get("quality_score", 100) >= 60 for item in group)]
        if len(usable)>1:
            conflicts.append({
                "field":field,
                "values":[group[0]["value"] for group in usable],
                "sources":[group[0].get("filename","") for group in usable],
            })
    return conflicts
