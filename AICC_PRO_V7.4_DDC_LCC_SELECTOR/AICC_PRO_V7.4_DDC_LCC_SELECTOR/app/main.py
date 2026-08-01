import json, logging, os, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, Form, Header, HTTPException, Request, UploadFile

load_dotenv(Path(__file__).resolve().parent.parent/".env")
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .database import (approve_session, audit, audit_list, create_session, find_by_isbn,
  get_session, initialize, recent_books, search_books, stats, update_session,
  records_missing, duplicate_candidates, get_book, update_book, delete_book)
from .agents.image_agent import validate_image, image_quality
from .agents.ocr_agent import extract_text
from .agents.page_agent import detect_page_type
from .agents.evidence_agent import collect_evidence, evidence_conflicts
from .agents.metadata_agent import extract_metadata
from .agents.bibliographic_lookup import lookup_book, merge_verified
from .agents.web_bibliographic_agent import research_book
from .agents.vision_cataloging_agent import (
  analyze_images as vision_analyze, merge_vision, vision_config)
from .agents.subject_agent import analyze_subject
from .agents.isbn_agent import find_valid_isbn, status as isbn_status
from .agents.cataloging_agent import classify
from .agents.professional_cataloging_agent import run_professional_cataloging
from .agents.marc_agent import build_marc, to_marcxml, validate_marc
from .agents.qrcode_agent import build_call_number_qr
from .agents.chat_agent import respond as chat_respond, ai_config, _optional_llm
from .rag import documents as knowledge_documents, ingest as ingest_knowledge, retrieve as retrieve_knowledge

BASE=Path(__file__).resolve().parent
DATA=BASE/"data"
UPLOAD=BASE/"uploads"
DATA.mkdir(parents=True,exist_ok=True)
UPLOAD.mkdir(parents=True,exist_ok=True)
logging.basicConfig(filename=DATA/"aicc.log",level=logging.INFO)
app=FastAPI(title="AICC — AI Cataloging & Classification Center",version="7.0.0",
 description="Evidence-grounded bilingual library cataloging MVP")
app.mount("/static",StaticFiles(directory=BASE/"static"),name="static")
templates=Jinja2Templates(directory=BASE/"templates")

@app.on_event("startup")
def startup():
    initialize()
    if not knowledge_documents():
        seed=BASE.parent/"knowledge"/"sample-policies"/"aicc-library-guide.txt"
        if seed.exists():
            ingest_knowledge("دليل المعرفة المكتبية العام في AICC",seed.name,seed.read_bytes(),
              "دليل مكتبي عام","العربية","public")

def actor(authorization: str|None):
    # Demo token; production guide requires reverse-proxy TLS and replacing this provider.
    if authorization not in (None,"","Bearer aicc-demo-token"):
        raise HTTPException(401,"جلسة غير صالحة")
    return "demo-admin"

@app.get("/",response_class=HTMLResponse)
def index(request:Request): return templates.TemplateResponse("index.html",{"request":request,"books":recent_books()})

@app.get("/api/health")
def health(): return {"ok":True,"version":"7.0.0","database":"ready","rag":"ready",
  "knowledge_documents":len(knowledge_documents()),"mode":"hybrid-local-vision",
  "gpt":{"configured":ai_config()["configured"],"model":ai_config()["model"]},
  "vision":{"configured":vision_config()["configured"],"model":vision_config()["model"]}}

@app.get("/api/ai/status")
def ai_status(authorization:str|None=Header(None)):
    actor(authorization); config=ai_config()
    return {"ok":True,"configured":config["configured"],"provider":config["provider"],
      "model":config["model"],"message":"GPT جاهز" if config["configured"] else
      "أضف LLM_API_KEY إلى ملف .env ثم أعد تشغيل النظام"}

@app.get("/api/ai/test")
def ai_test(authorization:str|None=Header(None)):
    actor(authorization); config=ai_config()
    if not config["configured"]:
        return {"ok":False,"connected":False,"error":"not_configured",
          "message":"مفتاح OpenAI غير مضبوط في ملف .env"}
    reply,error=_optional_llm("أجب فقط: اتصال AICC ناجح",[],{},[],[])
    return {"ok":bool(reply),"connected":bool(reply),"model":config["model"],
      "message":"تم الاتصال الفعلي بـGPT" if reply else "فشل طلب GPT الفعلي",
      "error":error}

@app.post("/api/auth/login")
def login(payload:dict=Body(...)):
    if payload.get("username")=="admin" and payload.get("password")=="aicc-demo-change-me":
        audit("demo-admin","auth.login"); return {"ok":True,"access_token":"aicc-demo-token","role":"system_admin"}
    raise HTTPException(401,"اسم المستخدم أو كلمة المرور غير صحيحة")

@app.get("/api/auth/me")
def me(authorization:str|None=Header(None)): return {"id":actor(authorization),"username":"admin","role":"system_admin"}

@app.get("/api/stats")
def stats_endpoint(): return {"ok":True,"stats":stats()}

def quality_review(book,pages,cataloging,marc_validation):
    critical=[]; warnings=[]
    if not book.get("title"): critical.append("العنوان مفقود")
    if book.get("isbn") and not isbn_status(book["isbn"])["valid"]: critical.append("ISBN غير صالح")
    if not book.get("author"): warnings.append("لا يوجد مدخل مسؤولية؛ يلزم التحقق")
    if (book.get("confidence") or {}).get("title",0)<80:
        critical.append("العنوان مرشح OCR غير مؤكد؛ يجب مطابقته مع صفحة العنوان أو ISBN")
    if book.get("author") and (book.get("confidence") or {}).get("author",0)<80:
        critical.append("اسم المؤلف غير مؤكد من بيان مسؤولية صريح")
    if not book.get("publisher"): warnings.append("الناشر غير مثبت من الصور")
    if not book.get("publication_year"): warnings.append("سنة النشر غير مثبتة من الصور")
    required_types={"غلاف أو صفحة عنوان","الغلاف الأمامي","صفحة العنوان","صفحة حقوق النشر","صفحة الرقم الدولي ISBN"}
    if not any(p.get("page_type") in required_types for p in pages):
        critical.append("لم تُرفع صفحة عنوان أو غلاف صالحة")
    bad=[p["filename"] for p in pages if p.get("quality_score",0)<60]
    if bad: critical.append("صور غير واضحة ويجب إعادة التقاطها: "+"، ".join(bad))
    if book.get("field_conflicts"):
        critical.append("توجد قيم متعارضة بين الصور ويجب حسمها")
    if book.get("verification_conflicts"):
        warnings.append("صحح مصدر ISBN اختلافات في OCR؛ راجع القيم الموثقة قبل الاعتماد")
    system=cataloging.get("classification_system","ddc")
    selected_field="lcc" if system=="lcc" else "ddc"
    selected_name="LCC" if system=="lcc" else "DDC"
    if not cataloging.get(selected_field):
        warnings.append(f"لم يُقترح {selected_name} بسبب نقص الأدلة")
    critical += marc_validation["errors"]
    scores=list((book.get("confidence") or {}).values())
    score=max(0,min(100,int(sum(scores)/len(scores)) if scores else 0)-len(critical)*20-len(warnings)*4)
    return {"score":score,"critical_errors":critical,"warnings":warnings,
      "requires_human_review":True,"may_submit":not critical}

def apply_human_review(book, patch):
    """An explicit field save resolves machine conflicts for reviewed values."""
    book=dict(book); patch=patch or {}
    reviewed={field for field,value in patch.items()
              if field not in {"raw_text","evidence"} and value is not None}
    confidence=dict(book.get("confidence") or {})
    sources=dict(book.get("field_sources") or {})
    for field in reviewed:
        if str(patch.get(field) or "").strip():
            confidence[field]=100
            sources[field]="اعتماد بشري صريح من شاشة المراجعة"
    book["confidence"]=confidence
    book["field_sources"]=sources
    book["field_conflicts"]=[
      conflict for conflict in (book.get("field_conflicts") or [])
      if conflict.get("field") not in reviewed]
    book["verification_conflicts"]=[
      conflict for conflict in (book.get("verification_conflicts") or [])
      if conflict.get("field") not in reviewed]
    book["human_reviewed_fields"]=sorted(
      set(book.get("human_reviewed_fields") or [])|reviewed)
    return book

def process_page(index, filename, path):
    started=time.perf_counter()
    validate_image(path)
    metrics=image_quality(path)
    warning=list(metrics["warnings"])
    try:
        raw_text,lang,ocr_metrics=extract_text(path)
    except FileNotFoundError:
        raw_text=""; lang="غير محددة"; ocr_metrics={"attempts":0,"agreement":0}
        warning.append("تعذر OCR المحلي؛ سيحاول GPT Vision استخراج البيانات من الصورة.")
    if not raw_text:
        warning.append("لم يستطع OCR استخراج نص كافٍ؛ سيحاول GPT Vision قراءة الصورة مباشرة.")
    clean_text=raw_text or "[لم يتم استخراج نص واضح]"
    page={"index":index,"filename":filename,"page_type":detect_page_type(clean_text,filename),
      "language":lang,"raw_text":raw_text,"text":clean_text,
      "quality_score":metrics["score"],
      "quality_metrics":metrics,"ocr_metrics":ocr_metrics,"warnings":warning}
    elapsed=int((time.perf_counter()-started)*1000)
    runs=[
      {"agent":"Image Quality Agent","status":"اكتمل","ms":elapsed},
      {"agent":"Page Type Agent","status":"اكتمل","ms":1},
      {"agent":"OCR Agent","status":"اكتمل بتحذير" if warning else "اكتمل","ms":elapsed}]
    return page,runs

@app.post("/api/analyze")
async def analyze(files:list[UploadFile]=File(...),
  classification_system:str=Form("ddc"),authorization:str|None=Header(None)):
    user=actor(authorization)
    classification_system="lcc" if classification_system=="lcc" else "ddc"
    if not files: raise HTTPException(400,"لم يتم اختيار أي ملف")
    if len(files)>20: raise HTTPException(400,"الحد الأقصى 20 ملفًا")
    pages=[]; runs=[]; queued=[]
    try:
      for i,file in enumerate(files,1):
        suffix=Path(file.filename or "").suffix.lower()
        if suffix not in {".png",".jpg",".jpeg",".webp",".bmp"}: raise ValueError(f"الملف {i}: نوع غير مدعوم")
        data=await file.read()
        if len(data)>15*1024*1024: raise ValueError(f"الملف {i}: يتجاوز 15MB")
        path=UPLOAD/f"{uuid4().hex}{suffix}"; path.write_bytes(data)
        queued.append((i,file.filename or f"image-{i}{suffix}",path))
      # Vision is network-bound, so run it beside up to three OCR workers.
      # This removes a complete serial API wait from every analysis.
      with ThreadPoolExecutor(max_workers=min(4,len(queued)+1)) as pool:
        vision_future=pool.submit(
          vision_analyze,[(filename,path) for _,filename,path in queued])
        futures={pool.submit(process_page,*item):item[0] for item in queued}
        for future in as_completed(futures):
          page,page_runs=future.result(); pages.append(page); runs.extend(page_runs)
        vision=vision_future.result()
      pages.sort(key=lambda p:p["index"])
      langs=[p["language"] for p in pages]; main_lang="العربية" if langs.count("العربية")>=langs.count("الإنجليزية") else "الإنجليزية"
      evidence=collect_evidence(pages); book=extract_metadata(pages,main_lang,evidence)
      book["field_conflicts"]=evidence_conflicts(evidence)
      book=merge_vision(book,vision)
      runs.append({"agent":"GPT Vision Bibliographic Agent",
        "status":"اكتمل" if vision.get("used") else
          ("غير مفعّل" if vision.get("error")=="not_configured" else "تعذر الاتصال"),
        "ms":0})
      valid_from_ocr=find_valid_isbn(book.get("raw_text",""))
      vision_isbn=book.get("isbn","")
      valid=vision_isbn if isbn_status(vision_isbn)["valid"] else valid_from_ocr
      book["isbn"]=valid
      book["isbn_validation"]=isbn_status(valid); book["author_type"]="corporate" if any(x in book.get("author","") for x in ("وزارة","جامعة","مركز","هيئة","مؤسسة","شركة")) else "personal"
      # Exact ISBN is preferred. Without one, both title and author must be
      # present and two independent catalogues must agree before enrichment.
      verified=lookup_book(book)
      if verified:
        book=merge_verified(book,verified)
        book["author_type"]="corporate" if any(x in book.get("author","") for x in ("وزارة","جامعة","مركز","هيئة","مؤسسة","شركة")) else "personal"
      missing_critical=any(not str(book.get(field) or "").strip()
        for field in ("title","author","publisher","publication_year"))
      exact_catalog=(book.get("external_match") or {}).get("method")=="exact_isbn"
      if missing_critical or not exact_catalog:
        web_verified=research_book(book)
        if web_verified:
          book=merge_verified(book,web_verified)
          book["author_type"]="corporate" if any(x in book.get("author","") for x in
            ("وزارة","جامعة","مركز","هيئة","مؤسسة","شركة")) else "personal"
          runs.append({"agent":"GPT Web Bibliographic Research Agent",
            "status":"اكتمل — تطابق موثق","ms":0})
        else:
          runs.append({"agent":"GPT Web Bibliographic Research Agent",
            "status":"لم يثبت تطابقًا كافيًا","ms":0})
      subject=analyze_subject(pages)
      vision_keywords=book.get("vision_subject_keywords") or []
      subject["keywords"]=list(dict.fromkeys(vision_keywords+subject.get("keywords",[])))[:15]
      if book.get("vision_summary"):
        subject["summary_draft"]=book["vision_summary"]
        subject["method"]="GPT Vision من الفهرس/المقدمة مع مراجعة بشرية"
      cat=classify(book.get("title",""),subject.get("summary_draft",""),
        subject.get("keywords",[]),book.get("author",""),
        book.get("publication_year",""),book,classification_system)
      vision_selected=(book.get("vision_lcc_suggestion") if classification_system=="lcc"
        else book.get("vision_ddc_suggestion"))
      if vision_selected and not cat.get(classification_system):
        cat["alternatives"]=[{"ddc":book.get("vision_ddc_suggestion",""),
          "lcc":book.get("vision_lcc_suggestion",""),
          "reason":book.get("vision_classification_reason","اقتراح Vision غير معتمد")}]
        cat["reason"]="تعذر التحقق من رقم تصنيف معتمد؛ يظهر اقتراح Vision ضمن البدائل فقط."
      professional=run_professional_cataloging(book,subject,cat,pages)
      marc=build_marc(book,cat,subject.get("summary_draft","")); validation=validate_marc(marc)
      book["duplicate_of"]=find_by_isbn(valid)
      quality=quality_review(book,pages,cat,validation)
      draft={"book":book,"pages":pages,"subject":subject,"cataloging":cat,
        "professional_cataloging":professional,"marc":marc,
        "marcxml":to_marcxml(marc),"marc_validation":validation,"quality":quality}
      sid=create_session(draft,user)
      return {"ok":True,"session_id":sid,**draft,"agent_runs":runs,
        "qr_label":build_call_number_qr(cat.get("call_number",""),valid,book.get("title",""))}
    except ValueError as e: return JSONResponse(status_code=400,content={"ok":False,"error":str(e),"work_preserved":False})
    except Exception:
      logging.exception("analysis failed"); return JSONResponse(status_code=500,content={"ok":False,"error":"تعذر إكمال التحليل. راجع سجل النظام.","work_preserved":False})

@app.get("/api/analysis/{sid}/results")
def analysis_results(sid:str,authorization:str|None=Header(None)):
    actor(authorization); s=get_session(sid)
    if not s: raise HTTPException(404,"الجلسة غير موجودة")
    return {"ok":True,**s}

@app.patch("/api/analysis/{sid}/fields")
def patch_analysis(sid:str,payload:dict=Body(...),authorization:str|None=Header(None)):
    user=actor(authorization)
    d=update_session(sid,payload,user)
    if not d: raise HTTPException(409,"الجلسة غير موجودة أو معتمدة")
    d["book"]=apply_human_review(d["book"],payload.get("book") or {})
    classification_system=(payload.get("cataloging") or {}).get(
      "classification_system",d.get("cataloging",{}).get("classification_system","ddc"))
    regenerated=classify(d["book"].get("title",""),d["subject"].get("summary_draft",""),
      d["subject"].get("keywords",[]),d["book"].get("author",""),
      d["book"].get("publication_year",""),d["book"],classification_system)
    regenerated.update(payload.get("cataloging") or {})
    d["cataloging"]=regenerated
    d["marc"]=build_marc(d["book"],d["cataloging"],d["subject"].get("summary_draft",""))
    d["marcxml"]=to_marcxml(d["marc"])
    d["professional_cataloging"]=run_professional_cataloging(
      d["book"],d["subject"],d["cataloging"],d.get("pages",[]))
    d["marc_validation"]=validate_marc(d["marc"])
    d["quality"]=quality_review(d["book"],d.get("pages",[]),d["cataloging"],d["marc_validation"])
    update_session(sid,{"book":d["book"],"cataloging":d["cataloging"],"marc":d["marc"],
      "professional_cataloging":d["professional_cataloging"],"quality":d["quality"]},user)
    return {"ok":True,"draft":d,"notice":"تم حفظ التعديلات وإعادة بناء التصنيف ورقم الطلب وMARC."}

@app.post("/api/analysis/{sid}/approve")
def approve(sid:str,authorization:str|None=Header(None)):
    try: bid=approve_session(sid,actor(authorization))
    except ValueError as e:
      session=get_session(sid); quality=((session or {}).get("draft") or {}).get("quality") or {}
      blockers=quality.get("critical_errors") or []
      detail=str(e)+((" الأسباب: "+"؛ ".join(blockers)) if blockers else "")
      raise HTTPException(422,detail)
    if not bid: raise HTTPException(409,"الجلسة غير موجودة أو سبق اعتمادها")
    return {"ok":True,"record_id":bid,"message":"تم اعتماد السجل وحفظ الإصدار الأول."}

@app.get("/api/records")
def records(q:str="",language:str="",year_from:str="",authorization:str|None=Header(None)):
    actor(authorization); return {"ok":True,"items":search_books(q,language,year_from,500)}

@app.get("/api/records/{record_id}")
def record_detail(record_id:str,authorization:str|None=Header(None)):
    actor(authorization); item=get_book(record_id)
    if not item:raise HTTPException(404,"السجل غير موجود")
    return {"ok":True,"item":item}

@app.patch("/api/records/{record_id}")
def edit_record(record_id:str,payload:dict=Body(...),authorization:str|None=Header(None)):
    user=actor(authorization); current=get_book(record_id)
    if not current:raise HTTPException(404,"السجل غير موجود")
    book=dict(current); book.update(payload.get("book") or {})
    isbn=(book.get("isbn") or "").strip()
    if isbn and not isbn_status(isbn)["valid"]:
        raise HTTPException(422,"ISBN غير صالح؛ صححه أو اتركه فارغًا")
    cataloging={"ddc":current.get("ddc",""),"lcc":current.get("lcc",""),
      "classification_system":current.get("classification_system","ddc"),
      "cutter":current.get("cutter",""),"call_number":current.get("call_number",""),
      "subject_headings":current.get("subjects") or []}
    cataloging.update(payload.get("cataloging") or {})
    subject={"keywords":current.get("keywords") or [],
      "summary_draft":current.get("summary","")}
    subject.update(payload.get("subject") or {})
    marc=build_marc(book,cataloging,subject.get("summary_draft",""))
    validation=validate_marc(marc)
    if not validation["valid"]:
        raise HTTPException(422,"تعذر حفظ MARC: "+"؛ ".join(validation["errors"]))
    fields={key:book.get(key,"") for key in (
      "title","subtitle","author","author_type","isbn","publisher",
      "publication_place","publication_year","edition","language","raw_text")}
    fields.update({"ddc":cataloging.get("ddc",""),"lcc":cataloging.get("lcc",""),
      "classification_system":cataloging.get("classification_system","ddc"),
      "cutter":cataloging.get("cutter",""),"call_number":cataloging.get("call_number",""),
      "keywords":subject.get("keywords") or [],
      "subjects":cataloging.get("subject_headings") or [],
      "summary":subject.get("summary_draft",""),"marc_json":marc})
    try:item=update_book(record_id,fields,user)
    except ValueError as exc:raise HTTPException(422,str(exc))
    return {"ok":True,"item":item,"message":"تم تعديل السجل وحفظ إصدار جديد."}

@app.delete("/api/records/{record_id}")
def remove_record(record_id:str,authorization:str|None=Header(None)):
    if not delete_book(record_id,actor(authorization)):
        raise HTTPException(404,"السجل غير موجود أو محذوف سابقًا")
    return {"ok":True,"message":"تم حذف السجل من الفهرس."}

@app.get("/api/search")
def search(q:str="",language:str="",year_from:str=""):
    return {"ok":True,"query":q,"items":search_books(q,language,year_from)}

@app.post("/api/chat")
def chat(payload:dict=Body(...)):
    result=chat_respond(payload.get("message",""),payload.get("context") or {},
      payload.get("history") or [],stats(),search_books,retrieve_knowledge,
      records_missing,duplicate_candidates)
    return {"ok":True,**result}

@app.get("/api/knowledge/documents")
def list_knowledge(authorization:str|None=Header(None)):
    actor(authorization); return {"ok":True,"items":knowledge_documents()}

@app.post("/api/knowledge/documents")
async def add_knowledge(file:UploadFile=File(...),title:str=Form(""),
  category:str=Form("سياسات المكتبة"),language:str=Form("العربية"),
  access_level:str=Form("public"),authorization:str|None=Header(None)):
    user=actor(authorization)
    data=await file.read()
    if len(data)>20*1024*1024:raise HTTPException(413,"حجم الوثيقة يتجاوز 20MB")
    try:
        document_id,count=ingest_knowledge(title or file.filename or "وثيقة مكتبية",
          file.filename or "document.txt",data,category,language,access_level)
    except ValueError as exc:raise HTTPException(422,str(exc))
    audit(user,"knowledge.uploaded","knowledge_document",document_id,{"filename":file.filename})
    return {"ok":True,"document_id":document_id,"chunk_count":count,
      "message":"تمت فهرسة الوثيقة وإضافتها إلى RAG."}

@app.post("/api/knowledge/test")
def test_knowledge(payload:dict=Body(...),authorization:str|None=Header(None)):
    actor(authorization); query=payload.get("query","")
    return {"ok":True,"query":query,"results":retrieve_knowledge(query)}

@app.post("/api/reports/generate")
def report(payload:dict=Body(...),authorization:str|None=Header(None)):
    user=actor(authorization); kind=payload.get("type","summary"); s=stats()
    audit(user,"report.generated","report",kind,payload)
    return {"ok":True,"report":{"type":kind,"filters":payload.get("filters",{}),
      "summary":f"إجمالي السجلات المعتمدة: {s['total']}، والمسودات قيد المراجعة: {s['pending']}.",
      "languages":s["languages"],"ddc":s["top_ddc_list"]}}

@app.get("/api/admin/audit-logs")
def logs(authorization:str|None=Header(None)): actor(authorization); return {"ok":True,"items":audit_list()}

@app.get("/api/records/{record_id}/exports/{fmt}")
def export(record_id:str,fmt:str,authorization:str|None=Header(None)):
    actor(authorization)
    found=[x for x in search_books("") if x["id"]==record_id]
    if not found: raise HTTPException(404,"السجل غير موجود")
    if fmt=="json": return JSONResponse(found[0])
    raise HTTPException(400,"صيغة التصدير المتاحة من هذه النقطة: json")
