"""Evidence-only bibliographic extraction from book-page images via OpenAI Vision."""
import base64
import io
import json
import os
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

from .isbn_agent import status as isbn_status

PLACEHOLDER_PATTERNS = (
    r"أدلة\s*ocr", r"ocr\s*إضاف", r"غير\s*واضح", r"غير\s*مقروء",
    r"غير\s*متوفر", r"غير\s*مذكور", r"لا\s*يوجد", r"unknown",
    r"not\s+(?:visible|available|provided)", r"^\[.*\]$",
)

FIELDS = (
    "title", "subtitle", "parallel_title", "statement_of_responsibility",
    "author", "corporate_author", "translator", "editor", "isbn", "issn",
    "publisher", "publication_place", "publication_year", "copyright_date",
    "edition", "language", "original_language", "pages", "illustrations",
    "dimensions", "accompanying_material", "series", "series_number",
    "bibliography_note", "index_note", "general_notes", "target_audience",
    "resource_type", "content_type", "media_type", "carrier_type",
)


def vision_config():
    base = (os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    model = (os.getenv("VISION_MODEL") or os.getenv("LLM_MODEL") or
             os.getenv("OPENAI_MODEL") or "gpt-4.1-mini")
    configured = bool(
        base and key and model
        and not key.lower().startswith(("ضع_", "your_", "changeme"))
    )
    return {"configured": configured, "base_url": base, "api_key": key, "model": model}


def _schema():
    string_properties = {field: {"type": "string"} for field in FIELDS}
    confidence_properties = {
        field: {"type": "integer", "minimum": 0, "maximum": 100}
        for field in FIELDS
    }
    evidence_properties = {field: {"type": "string"} for field in FIELDS}
    properties = {
        **string_properties,
        "subject_keywords": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
        "ddc_suggestion": {"type": "string"},
        "lcc_suggestion": {"type": "string"},
        "classification_reason": {"type": "string"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "confidence": {
            "type": "object",
            "properties": confidence_properties,
            "required": list(FIELDS),
            "additionalProperties": False,
        },
        "evidence": {
            "type": "object",
            "properties": evidence_properties,
            "required": list(FIELDS),
            "additionalProperties": False,
        },
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(FIELDS) + [
            "subject_keywords", "summary", "ddc_suggestion", "lcc_suggestion",
            "classification_reason", "warnings", "confidence", "evidence",
        ],
        "additionalProperties": False,
    }


def _image_data_url(path):
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=82, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _response_text(payload):
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"].strip()
    pieces = []
    for item in payload.get("output") or []:
        if item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                pieces.append(content["text"])
    return "\n".join(pieces).strip()


def analyze_images(items):
    """Analyze [(filename, path), ...]. Failure is returned, never hidden."""
    config = vision_config()
    if not config["configured"]:
        return {"used": False, "data": {}, "error": "not_configured"}
    content = [{
        "type": "input_text",
        "text": (
            "حلل صور صفحات هذا الكتاب كمفهرس محترف وفق RDA وMARC 21. "
            "استخرج فقط المعلومات المقروءة بوضوح من الصور. لا تخمّن ولا تكمل "
            "من المعرفة العامة. اترك أي حقل غير ظاهر سلسلة فارغة وثقته صفرًا. "
            "في evidence اذكر اسم الصورة والنص المرئي المختصر الذي يثبت القيمة. "
            "ميّز المؤلف عن المترجم والمحرر، وميّز سنة الطبعة من سنوات حقوق سابقة. "
            "ISBN لا يقبل إلا إذا كان كاملًا. اقتراحا DDC وLCC غير معتمدين "
            "ويجب أن يستندا إلى الفهرس أو المقدمة أو الملخص المرئي."
        ),
    }]
    for filename, path in items[:12]:
        content.append({"type": "input_text", "text": f"اسم الصورة التالية: {filename}"})
        content.append({"type": "input_image", "image_url": _image_data_url(path), "detail": "high"})
    body = {
        "model": config["model"],
        "input": [{"role": "user", "content": content}],
        "text": {"format": {
            "type": "json_schema",
            "name": "aicc_bibliographic_record",
            "strict": True,
            "schema": _schema(),
        }},
        "max_output_tokens": 3500,
    }
    request = urllib.request.Request(
        config["base_url"] + "/responses",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + config["api_key"],
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = json.loads(response.read())
        text = _response_text(raw)
        data = json.loads(text)
        isbn = data.get("isbn", "")
        if isbn and not isbn_status(isbn)["valid"]:
            data["warnings"].append("تجاهل Vision رقم ISBN لأنه لم يجتز التحقق الرياضي.")
            data["isbn"] = ""
            data["confidence"]["isbn"] = 0
            data["evidence"]["isbn"] = ""
        return {"used": True, "data": data, "error": "", "model": config["model"]}
    except Exception as exc:
        return {"used": False, "data": {}, "error": type(exc).__name__, "model": config["model"]}


def merge_vision(ocr_book, result):
    """Merge only evidenced, sufficiently confident Vision values."""
    book = dict(ocr_book)
    data = result.get("data") or {}
    confidence = data.get("confidence") or {}
    evidence = data.get("evidence") or {}
    sources = dict(book.get("field_sources") or {})
    conflicts = list(book.get("verification_conflicts") or [])
    accepted = []
    for field in FIELDS:
        value = str(data.get(field) or "").strip()
        score = int(confidence.get(field) or 0)
        proof = str(evidence.get(field) or "").strip()
        if (not value or score < 75 or not proof or
            any(__import__("re").search(pattern, value, __import__("re").I)
                for pattern in PLACEHOLDER_PATTERNS)):
            continue
        old = str(book.get(field) or "").strip()
        if old and old.casefold() != value.casefold():
            conflicts.append({
                "field": field, "ocr_value": old, "verified_value": value,
                "source": "GPT Vision — دليل من الصورة",
            })
        book[field] = value
        book.setdefault("confidence", {})[field] = min(score, 95)
        sources[field] = "GPT Vision: " + proof
        accepted.append(field)
    book["field_sources"] = sources
    book["verification_conflicts"] = conflicts
    book["vision_used"] = bool(result.get("used"))
    book["vision_model"] = result.get("model", "")
    book["vision_error"] = result.get("error", "")
    book["vision_fields_accepted"] = accepted
    book["vision_warnings"] = data.get("warnings") or []
    book["vision_subject_keywords"] = data.get("subject_keywords") or []
    book["vision_summary"] = data.get("summary") or ""
    book["vision_ddc_suggestion"] = data.get("ddc_suggestion") or ""
    book["vision_lcc_suggestion"] = data.get("lcc_suggestion") or ""
    book["vision_classification_reason"] = data.get("classification_reason") or ""
    return book
