import re
from .isbn_agent import status as isbn_status

HONORIFICS = re.compile(
    r"^(?:أ\.?\s*د\.?|د\.?|الدكتور|الدكتورة|الأستاذ|الأستاذة|الشيخ)\s+",
    re.I,
)

REQUIRED_CAPTURE = {
    "title": ("صفحة العنوان", "صوّر صفحة العنوان الداخلية كاملة."),
    "publisher": ("صفحة حقوق النشر", "صوّر صفحة حقوق النشر التي تعرض بيانات الناشر."),
    "publication_year": ("صفحة حقوق النشر", "صوّر صفحة حقوق النشر والسنة بوضوح."),
    "isbn": ("صفحة الرقم الدولي ISBN", "صوّر ISBN والباركود عن قرب."),
    "pages": ("صفحة الوصف المادي", "صوّر آخر صفحة مرقمة أو بيانات عدد الصفحات."),
    "dimensions": ("قياس مادي", "تحقق من أبعاد الكتاب يدويًا عند عدم ظهورها في المصدر."),
}


def normalize_authority_name(value):
    value = HONORIFICS.sub("", (value or "").strip())
    value = re.sub(r"\s+", " ", value).strip(" ،,.;:")
    return value


def descriptive_cataloging(book):
    author = normalize_authority_name(book.get("author", ""))
    corporate = book.get("author_type") == "corporate"
    if author:
        access_point = {
            "type": "corporate" if corporate else "personal",
            "authorized_form": author,
            "marc_tag": "110" if corporate else "100",
            "relationship": "جهة مؤلفة" if corporate else "مؤلف",
            "decision": "اختير من بيان المسؤولية الظاهر في المصدر.",
        }
    else:
        access_point = {
            "type": "title",
            "authorized_form": book.get("title", ""),
            "marc_tag": "245",
            "relationship": "",
            "decision": "لا يوجد مؤلف مثبت؛ يبدأ السجل بالعنوان.",
        }
    rda = {
        "title_proper": book.get("title", ""),
        "other_title_information": book.get("subtitle", ""),
        "statement_of_responsibility": book.get("statement_of_responsibility", ""),
        "edition_statement": book.get("edition", ""),
        "production_publication": {
            "place": book.get("publication_place", ""),
            "agent": book.get("publisher", ""),
            "date": book.get("publication_year", ""),
        },
        "extent": book.get("pages", ""),
        "dimensions": book.get("dimensions", ""),
        "content_type": book.get("content_type", "نص"),
        "media_type": book.get("media_type", "بدون وسيط"),
        "carrier_type": book.get("carrier_type", "مجلد"),
    }
    return access_point, rda


def validate_catalog_record(book, classification):
    errors, warnings, tasks = [], [], []
    for field, (page_type, instruction) in REQUIRED_CAPTURE.items():
        if not (book.get(field) or "").strip():
            severity = "error" if field == "title" else "warning"
            (errors if severity == "error" else warnings).append(
                {"field": field, "message": f"{field} غير مثبت من المصدر."}
            )
            tasks.append({"field": field, "required_page": page_type, "instruction": instruction})
    isbn = (book.get("isbn") or "").strip()
    if isbn and not isbn_status(isbn)["valid"]:
        errors.append({"field": "isbn", "message": "ISBN لم يجتز التحقق الرياضي."})
    system = classification.get("classification_system", "ddc")
    selected_field = "lcc" if system == "lcc" else "ddc"
    selected_name = "LCC" if system == "lcc" else "DDC"
    if not classification.get(selected_field):
        warnings.append({"field": selected_field,
          "message": f"تعذر اقتراح {selected_name} موثوق من الأدلة المتاحة."})
    if classification.get("confidence", 0) < 75:
        warnings.append({"field": "classification", "message": "ثقة التصنيف منخفضة؛ راجع الفهرس والمقدمة."})
    if not classification.get("subject_headings"):
        warnings.append({"field": "subjects", "message": "لا توجد رؤوس موضوعات قابلة للاعتماد."})
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "capture_tasks": tasks,
        "decision": "جاهز للمراجعة المهنية" if not errors else "غير جاهز للاعتماد",
    }


def run_professional_cataloging(book, subject, classification, pages):
    access_point, rda = descriptive_cataloging(book)
    validation = validate_catalog_record(book, classification)
    evidence_map = {}
    for field, items in (book.get("evidence") or {}).items():
        evidence_map[field] = [
            {"value": item.get("value", ""), "source": item.get("filename", ""),
             "page_type": item.get("page_type", "")}
            for item in items
        ]
    return {
        "standard": "RDA + MARC 21",
        "status": validation["decision"],
        "main_access_point": access_point,
        "rda_elements": rda,
        "subject_analysis": {
            "aboutness": subject.get("summary_draft", ""),
            "keywords": subject.get("keywords", []),
            "controlled_headings": classification.get("subject_headings", []),
        },
        "classification_decision": {
            "classification_system": classification.get("classification_system", "ddc"),
            "ddc": classification.get("ddc", ""),
            "lcc": classification.get("lcc", ""),
            "cutter": classification.get("cutter", ""),
            "call_number": classification.get("call_number", ""),
            "reason": classification.get("reason", ""),
            "alternatives": classification.get("alternatives", []),
            "confidence": classification.get("confidence", 0),
        },
        "validation": validation,
        "evidence_map": evidence_map,
        "pages_reviewed": len(pages),
        "human_approval_required": True,
    }
