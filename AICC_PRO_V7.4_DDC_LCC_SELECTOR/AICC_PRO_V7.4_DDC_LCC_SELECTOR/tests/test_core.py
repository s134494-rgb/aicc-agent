import xml.etree.ElementTree as ET
from app.agents.isbn_agent import valid_isbn10, valid_isbn13, status
from app.agents.cataloging_agent import build_cutter
from app.agents.marc_agent import build_marc, to_marcxml, validate_marc
from app.agents.metadata_agent import extract_metadata
from app.agents.evidence_agent import evidence_conflicts
from app.agents.cataloging_agent import classify
from app.agents.professional_cataloging_agent import (
    normalize_authority_name, run_professional_cataloging)
from app.agents.bibliographic_lookup import merge_verified
from app.agents.chat_agent import _response_text
from app.agents.vision_cataloging_agent import merge_vision, _schema, analyze_images, FIELDS
from app.main import apply_human_review

def test_isbn_validation():
    assert valid_isbn10("0-306-40615-2")
    assert not valid_isbn10("0-306-40615-3")
    assert valid_isbn13("978-0-306-40615-7")
    assert not valid_isbn13("978-0-306-40615-8")

def test_cutter_is_not_fixed():
    assert build_cutter("أحمد","") != build_cutter("محمد","")

def test_marc_personal_and_invalid_isbn():
    book={"title":"اختبار","author":"أحمد","author_type":"personal","isbn":"123",
          "language":"العربية","publication_year":"2026"}
    marc=build_marc(book,{"ddc":"020","lcc":"Z665","cutter":"ع123","subject_headings":[]}, "")
    tags=[f["tag"] for f in marc["fields"]]
    assert "100" in tags and "110" not in tags and "020" not in tags
    assert all(x in tags for x in ("001","005","008","245"))
    assert validate_marc(marc)["valid"]
    ET.fromstring(to_marcxml(marc))

def test_marc_corporate():
    marc=build_marc({"title":"تقرير","author":"وزارة الثقافة","author_type":"corporate",
      "isbn":"","language":"العربية"}, {}, "")
    assert "110" in [f["tag"] for f in marc["fields"]]

def test_arabic_metadata_and_digits():
    text="""اسم الكتاب: استراتيجيات تدريس اللغة العربية
تأليف: أحمد بن سعيد الحارثي
الناشر: المركز التربوي للغة العربية
الطبعة الأولى - ٢٠١٩
ISBN ٩٧٨-٠-٣٠٦-٤٠٦١٥-٧
245 صفحة ؛ 24 سم
يتضمن مراجع"""
    page={"text":text,"page_type":"صفحة حقوق النشر","filename":"copyright.jpg"}
    data=extract_metadata([page],"العربية",{
      "title":[{"value":"استراتيجيات تدريس اللغة العربية","filename":"copyright.jpg"}],
      "author":[{"value":"أحمد بن سعيد الحارثي","filename":"copyright.jpg"}],
      "publisher":[{"value":"المركز التربوي للغة العربية","filename":"copyright.jpg"}]})
    assert data["isbn"]=="9780306406157"
    assert data["author"]=="أحمد بن سعيد الحارثي"
    assert data["pages"]=="245"

def test_evidence_conflict_is_not_hidden():
    conflicts=evidence_conflicts({"author":[
      {"value":"أحمد بن سعيد","filename":"title.jpg"},
      {"value":"محمد بن سعيد","filename":"cover.jpg"}]})
    assert conflicts and conflicts[0]["field"]=="author"

def test_classification_has_professional_basis():
    result=classify("مقدمة في القانون والتشريع","","", "", "2025")
    assert result["ddc"]=="340"
    assert result["lcc"]=="K"
    assert result["classification_basis"]["matched_rule"]=="القانون"

def test_selected_classification_system_controls_call_number():
    ddc=classify("مقدمة في القانون والتشريع","","","","2025",
      classification_system="ddc")
    lcc=classify("مقدمة في القانون والتشريع","","","","2025",
      classification_system="lcc")
    assert ddc["classification_system"]=="ddc"
    assert ddc["call_number"].startswith("340 ")
    assert lcc["classification_system"]=="lcc"
    assert lcc["call_number"].startswith("K ")

def test_marc_exports_only_selected_classification_system():
    book={"title":"مقدمة في القانون","language":"العربية"}
    ddc_record=build_marc(book,{"classification_system":"ddc","ddc":"340",
      "lcc":"K","cutter":"A100","subject_headings":[]},"")
    lcc_record=build_marc(book,{"classification_system":"lcc","ddc":"340",
      "lcc":"K","cutter":"A100","subject_headings":[]},"")
    assert "082" in [field["tag"] for field in ddc_record["fields"]]
    assert "050" not in [field["tag"] for field in ddc_record["fields"]]
    assert "050" in [field["tag"] for field in lcc_record["fields"]]
    assert "082" not in [field["tag"] for field in lcc_record["fields"]]

def test_marc_requires_title_value():
    marc=build_marc({"title":"","author":"","isbn":"","language":"العربية"},{}, "")
    validation=validate_marc(marc)
    assert not validation["valid"]
    assert any("245$a" in error for error in validation["errors"])

def test_professional_agent_builds_rda_and_access_point():
    book={"title":"الفهرسة الحديثة","author":"د. أحمد بن سعيد",
      "author_type":"personal","isbn":"9780306406157","publisher":"دار المعرفة",
      "publication_year":"2025","publication_place":"مسقط","language":"العربية",
      "pages":"220","dimensions":"24 سم","content_type":"نص",
      "media_type":"بدون وسيط","carrier_type":"مجلد","evidence":{}}
    subject={"keywords":["فهرسة"],"summary_draft":"دليل في الفهرسة"}
    classification=classify(book["title"],subject["summary_draft"],subject["keywords"],
      book["author"],book["publication_year"])
    report=run_professional_cataloging(book,subject,classification,[])
    assert normalize_authority_name(book["author"])=="أحمد بن سعيد"
    assert report["main_access_point"]["marc_tag"]=="100"
    assert report["rda_elements"]["title_proper"]=="الفهرسة الحديثة"
    assert report["validation"]["valid"]

def test_professional_agent_blocks_missing_title():
    report=run_professional_cataloging(
      {"title":"","author":"","isbn":"","publisher":"","publication_year":""},
      {"keywords":[],"summary_draft":""},{"ddc":"","lcc":"","subject_headings":[],
      "confidence":0,"alternatives":[]},[])
    assert not report["validation"]["valid"]
    assert any(x["field"]=="title" for x in report["validation"]["errors"])

def test_marc_has_rda_agency_field():
    marc=build_marc({"title":"اختبار","author":"","isbn":"","language":"العربية"},{}, "")
    assert "040" in [field["tag"] for field in marc["fields"]]

def test_unlabelled_short_line_is_not_guessed_as_author():
    page={"text":"مدخل إلى إدارة المعرفة\nمعاذ الوردي\nمسقط 2026",
          "page_type":"غلاف أو صفحة عنوان","filename":"cover.jpg","quality_score":90}
    data=extract_metadata([page],"العربية",{})
    assert data["author"]==""
    assert data["confidence"]["author"]==0

def test_verified_isbn_metadata_replaces_ocr_and_records_conflict():
    original={"title":"عنوان OCR خاطئ","author":"","confidence":{"title":58},
              "field_sources":{},"verification_conflicts":[]}
    merged=merge_verified(original,{"title":"العنوان الصحيح","author":"المؤلف الصحيح",
      "publication_year":"2024","source":"Open Library ISBN"})
    assert merged["title"]=="العنوان الصحيح"
    assert merged["author"]=="المؤلف الصحيح"
    assert merged["confidence"]["title"]==98
    assert merged["verification_conflicts"][0]["field"]=="title"

def test_external_transliteration_never_replaces_arabic_image_evidence():
    original={"title":"قصتي","author":"حسان الزين","isbn":"9781855162976",
      "publisher":"","confidence":{"title":98,"author":98},
      "field_sources":{"title":"GPT Vision","author":"GPT Vision"},
      "verification_conflicts":[]}
    verified={"title":"Qiṣṣatī","subtitle":"Samīr al-Qanṭār : riwāyah wathāʼiqīyah",
      "author":"Samīr Qanṭār","publisher":"Dar Saqi","match_method":"exact_isbn",
      "match_status":"exact","match_score":100,"sources":["Open Library","Google Books"]}
    merged=merge_verified(original,verified)
    assert merged["title"]=="قصتي"
    assert merged["author"]=="حسان الزين"
    assert merged["publisher"]=="Dar Saqi"
    assert set(merged["external_match"]["preserved_fields"])=={"title","author"}
    assert merged["external_match"]["filled_fields"]==["subtitle","publisher"]

def test_non_isbn_consensus_only_fills_missing_fields():
    original={"title":"إدارة المعرفة","author":"محمد أحمد","publisher":"",
      "confidence":{"title":92,"author":91},"field_sources":{},
      "verification_conflicts":[]}
    verified={"title":"إدارة المعرفة","author":"محمد أحمد","publisher":"دار العلم",
      "match_method":"title_author_consensus","match_status":"strong_consensus",
      "match_score":94,"sources":["Open Library","Google Books"]}
    merged=merge_verified(original,verified)
    assert merged["title"]=="إدارة المعرفة"
    assert merged["publisher"]=="دار العلم"
    assert merged["confidence"]["publisher"]==90
    assert not merged["verified_ddc"]

def test_truncated_isbn13_prefix_cannot_pass_as_isbn10():
    from app.agents.isbn_agent import status
    result=status("9789948387")
    assert not result["valid"]
    assert result["type"]=="ISBN-10"

def test_openai_responses_text_parser():
    payload={"output":[{"type":"message","content":[
      {"type":"output_text","text":"إجابة موثقة"}]}]}
    assert _response_text(payload)=="إجابة موثقة"

def test_vision_schema_is_strict_and_complete():
    schema=_schema()
    assert schema["additionalProperties"] is False
    assert "title" in schema["required"]
    assert "confidence" in schema["required"]
    assert schema["properties"]["confidence"]["additionalProperties"] is False

def test_vision_merge_requires_evidence_and_confidence():
    original={"title":"عنوان OCR","confidence":{"title":58},"field_sources":{},
      "verification_conflicts":[]}
    result={"used":True,"model":"gpt-test","error":"","data":{
      "title":"العنوان الصحيح","author":"اسم بلا دليل",
      "confidence":{"title":94,"author":99},
      "evidence":{"title":"title-page.jpg: العنوان الصحيح","author":""},
      "warnings":[],"subject_keywords":["فهرسة"],"summary":"ملخص مرئي"}}
    merged=merge_vision(original,result)
    assert merged["title"]=="العنوان الصحيح"
    assert merged.get("author","")==""
    assert merged["vision_fields_accepted"]==["title"]
    assert merged["field_sources"]["title"].startswith("GPT Vision")

def test_vision_placeholder_is_never_accepted_as_title():
    original={"title":"","confidence":{},"field_sources":{},
      "verification_conflicts":[]}
    result={"used":True,"model":"gpt-test","error":"","data":{
      "title":"[أدلة OCR إضافية]","confidence":{"title":99},
      "evidence":{"title":"image.jpg: أدلة OCR إضافية"}}}
    merged=merge_vision(original,result)
    assert merged.get("title","")==""

def test_vision_request_and_structured_response(monkeypatch,tmp_path):
    from PIL import Image
    import json
    image_path=tmp_path/"title-page.jpg"
    Image.new("RGB",(800,600),"white").save(image_path)
    data={field:"" for field in FIELDS}
    data.update({"title":"اختبار Vision","subject_keywords":[],"summary":"",
      "ddc_suggestion":"","lcc_suggestion":"","classification_reason":"",
      "warnings":[],"confidence":{field:0 for field in FIELDS},
      "evidence":{field:"" for field in FIELDS}})
    data["confidence"]["title"]=95
    data["evidence"]["title"]="title-page.jpg: اختبار Vision"
    payload={"output_text":json.dumps(data,ensure_ascii=False)}
    class FakeResponse:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self):return json.dumps(payload,ensure_ascii=False).encode()
    monkeypatch.setenv("LLM_BASE_URL","https://api.openai.com/v1")
    monkeypatch.setenv("LLM_API_KEY","test-key")
    monkeypatch.setenv("VISION_MODEL","gpt-test")
    monkeypatch.setattr("urllib.request.urlopen",lambda request,timeout:FakeResponse())
    result=analyze_images([("title-page.jpg",image_path)])
    assert result["used"]
    assert result["data"]["title"]=="اختبار Vision"

def test_human_review_resolves_machine_conflict():
    book={"title":"عنوان آلي","confidence":{"title":58},
      "field_sources":{"title":"OCR"},"field_conflicts":[{"field":"title"}],
      "verification_conflicts":[{"field":"title"}]}
    reviewed=apply_human_review(book,{"title":"العنوان المعتمد"})
    assert reviewed["confidence"]["title"]==100
    assert reviewed["field_sources"]["title"].startswith("اعتماد بشري")
    assert reviewed["field_conflicts"]==[]
    assert reviewed["verification_conflicts"]==[]

def test_saved_record_update_versions_and_soft_delete(tmp_path):
    import app.database as database
    original=database.DB_PATH
    database.DB_PATH=tmp_path/"records.db"
    try:
        database.initialize()
        with database.connect() as conn:
            conn.execute("""INSERT INTO books(id,title,author,raw_text,status,version)
              VALUES('book-1','العنوان القديم','مؤلف','نص','approved',1)""")
        updated=database.update_book("book-1",{"title":"العنوان الجديد"},"tester")
        assert updated["title"]=="العنوان الجديد"
        assert updated["version"]==2
        with database.connect() as conn:
            assert conn.execute("""SELECT COUNT(*) FROM record_versions
              WHERE book_id='book-1'""").fetchone()[0]==1
        assert database.delete_book("book-1","tester")
        assert database.get_book("book-1") is None
        with database.connect() as conn:
            row=conn.execute("SELECT status,deleted_at FROM books WHERE id='book-1'").fetchone()
            assert row["status"]=="deleted" and row["deleted_at"]
    finally:
        database.DB_PATH=original
