"""OpenAI web-search fallback for incomplete or unidentified books."""
import json
import os
import urllib.request

from .isbn_agent import status as isbn_status
from .vision_cataloging_agent import _response_text

WEB_FIELDS = (
    "title", "subtitle", "author", "translator", "editor", "publisher",
    "publication_place", "publication_year", "copyright_date", "edition",
    "isbn", "language", "original_language", "pages", "illustrations",
    "dimensions", "series", "series_number", "bibliography_note", "index_note",
    "target_audience", "ddc", "lcc",
)


def _schema():
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            **{field: {"type": "string"} for field in WEB_FIELDS},
            "subjects": {"type": "array", "items": {"type": "string"}},
            "match": {"type": "boolean"},
            "match_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "match_basis": {"type": "string"},
            "sources": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {"title": {"type": "string"}, "url": {"type": "string"},
                               "authority": {"type": "string"}},
                "required": ["title", "url", "authority"],
            }},
            "field_sources": {"type": "object", "additionalProperties": False,
                "properties": {field: {"type": "array", "items": {"type": "string"}}
                               for field in WEB_FIELDS},
                "required": list(WEB_FIELDS)},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": list(WEB_FIELDS) + [
            "subjects", "match", "match_score", "match_basis", "sources",
            "field_sources", "warnings",
        ],
    }


def research_book(book):
    """Search the live web and return only an evidence-backed exact identity."""
    base = (os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    model = (os.getenv("WEB_RESEARCH_MODEL") or os.getenv("LLM_MODEL") or
             os.getenv("OPENAI_MODEL") or "gpt-4.1-mini")
    if not (base and key and model):
        return {}
    observed = {key: book.get(key, "") for key in (
        "title", "subtitle", "author", "publisher", "publication_place",
        "publication_year", "edition", "isbn", "language")}
    observed["ocr_excerpt"] = str(book.get("raw_text") or "")[:12000]
    prompt = (
        "أنت باحث ببليوجرافي عربي. استخدم بحث الويب للتعرف على الكتاب نفسه "
        "من البيانات الجزئية التالية. ابحث أولًا بالـISBN الكامل إن كان صالحًا، "
        "ثم بالعبارات المميزة من OCR مع المؤلف/الناشر/السنة. فضّل بهذا الترتيب: "
        "صفحة الناشر الرسمية، فهرس مكتبة وطنية أو جامعية، WorldCat/Library of "
        "Congress، ثم متجر موثوق. لا تعتبر تشابه الموضوع تطابقًا. match=true فقط "
        "عند ISBN كامل متطابق، أو اتفاق مصدرين مستقلين على العنوان والمؤلف والناشر/السنة. "
        "كل حقل يجب أن يملك URL مؤيدًا في field_sources وإلا اتركه فارغًا. "
        "لا تخترع DDC أو LCC: أعدهما فقط إذا وجدت سجل فهرسة يعرض الرقم صراحة. "
        "أعد الأسماء والعناوين العربية بالعربية، ولا تستبدلها بالنقحرة اللاتينية.\n"
        + json.dumps(observed, ensure_ascii=False)
    )
    body = {
        "model": model, "input": prompt, "tools": [{"type": "web_search"}],
        "text": {"format": {"type": "json_schema",
                            "name": "verified_book_web_record",
                            "strict": True, "schema": _schema()}},
        "max_output_tokens": 4500,
    }
    request = urllib.request.Request(
        base + "/responses",
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=75) as response:
            payload = json.loads(response.read())
        data = json.loads(_response_text(payload))
    except Exception:
        return {}
    sources = [source for source in data.get("sources") or []
               if str(source.get("url") or "").startswith(("http://", "https://"))]
    unique_domains = {source["url"].split("/")[2].lower() for source in sources}
    observed_has_valid_isbn = isbn_status(book.get("isbn", ""))["valid"]
    minimum_sources = 1 if observed_has_valid_isbn else 2
    if (not data.get("match") or data.get("match_score", 0) < 95 or
        len(unique_domains) < minimum_sources):
        return {}
    isbn = data.get("isbn", "")
    observed_isbn = book.get("isbn", "")
    if observed_isbn and isbn_status(observed_isbn)["valid"]:
        if not isbn_status(isbn)["valid"] or isbn_status(isbn)["value"] != isbn_status(observed_isbn)["value"]:
            return {}
    # Discard any field that has no cited URL.
    for field in WEB_FIELDS:
        urls = [url for url in (data.get("field_sources", {}).get(field) or [])
                if str(url).startswith(("http://", "https://"))]
        if not urls:
            data[field] = ""
    return {
        **{field: data.get(field, "") for field in WEB_FIELDS},
        "subjects": data.get("subjects") or [],
        "sources": [source["title"] for source in sources],
        "source_links": sources,
        "field_evidence": {field: [{"value": data.get(field, ""), "source": url}
                                  for url in data.get("field_sources", {}).get(field, [])]
                           for field in WEB_FIELDS if data.get(field)},
        "match_method": "web_exact", "match_status": "exact",
        "match_score": data.get("match_score", 0),
        "match_basis": data.get("match_basis", ""),
        "ddc": data.get("ddc", ""), "lcc": data.get("lcc", ""),
    }
