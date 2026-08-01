"""AICC scoped agent: catalog/RAG tools plus OpenAI Responses API."""
import json, os, re, urllib.request
from .isbn_agent import candidates, status
from ..rag import normalize as _normalize

DOMAIN_TERMS={
 "مكتب","مكتبة","مكتبات","كتاب","كتب","مؤلف","ناشر","فهرس","فهرسة","تصنيف","ديوي",
 "مارك","marc","ddc","lcc","isbn","issn","رف","اعارة","إعارة","استعارة","مراجع",
 "سجل","سجلات","مجموعة","مجموعات","قراءة","باحث","مستفيد","رسالة","دورية","مجلة",
 "قصة","رواية","موسوعة","قاموس","مصدر","مصادر","خدمة","خدمات","سياسة","سياسات",
 "bibliographic","catalog","library"}
NORMALIZED_DOMAIN_TERMS={_normalize(t) for t in DOMAIN_TERMS}
STOP={"اريد","أريد","ابحث","لي","عن","كتاب","كتب","ما","هو","هي","هل","في","من","على",
 "الى","إلى","ممكن","اعطني","أعطني","احتاج","أحتاج","لو","سمحت","توجد","عندكم","لديكم",
 "شيء","موضوع","اظهر","أظهر","ابغى","بغيت","حول","يخص"}

def ai_config():
    base=(os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/"); key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY",""); model=os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"
    configured=bool(base and key and model and not key.lower().startswith(("ضع_","your_","changeme")))
    return {"configured":configured,"base_url":base,"model":model,
      "provider":"OpenAI" if "api.openai.com" in base else "OpenAI-compatible"}

def _response_text(payload):
    if isinstance(payload.get("output_text"),str):
        return payload["output_text"].strip()
    pieces=[]
    for item in payload.get("output") or []:
        if item.get("type")!="message":continue
        for content in item.get("content") or []:
            if content.get("type") in {"output_text","text"} and content.get("text"):
                pieces.append(content["text"])
    return "\n".join(pieces).strip()

def _optional_llm(message,history,context,records,chunks):
    config=ai_config()
    base=config["base_url"]; key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY",""); model=config["model"]
    if not config["configured"]:return "","not_configured"
    evidence=json.dumps({"active_record":context,"catalog_records":records[:8],
      "rag_chunks":[{"source":x["citation"],"text":x["content"]} for x in chunks[:5]]},ensure_ascii=False)
    system=("أنت AICC، وكيل مكتبة مهني محدود حصريًا بالمكتبات وهذا الموقع. "
      "أجب من الأدلة فقط، ولا تستخدم معلومات عامة غير مسترجعة، ولا تخترع مقتنيات أو سياسات. "
      "إذا كان السؤال خارج النطاق ارفضه. اذكر المصادر في نهاية الرد. ميّز الحقيقة من الاقتراح.")
    messages=[]
    for item in (history or [])[-6:]:
        if item.get("role") in {"user","assistant"}:messages.append({"role":item["role"],"content":str(item.get("content",""))[:1500]})
    messages.append({"role":"user","content":message})
    body=json.dumps({"model":model,"instructions":system+"\nEVIDENCE:\n"+evidence,
      "input":messages,"max_output_tokens":900}).encode()
    req=urllib.request.Request(base+"/responses",data=body,
      headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=60) as res:
            text=_response_text(json.loads(res.read()))
            return (text,"") if text else ("","empty_response")
    except Exception as exc:
        return "",type(exc).__name__

def _query(text):
    words=re.findall(r"[A-Za-z0-9.]+|[\u0621-\u063A\u0641-\u064A]+",text)
    return " ".join(w for w in words if w not in STOP and len(w)>1)

def _in_scope(text,context):
    low=text.lower()
    if any(x in low for x in ("من انت","من أنت","عرف بنفسك","عرّف بنفسك",
      "ماذا تستطيع","وش تقدر","كيف تساعدني","ما دورك")):return True
    if any(x in low for x in ("ابحث","بحث","فرز","رتب","اعرض السجلات")):return True
    if context.get("title") and any(x in low for x in ("هذا","السجل","الحالي","مثله","مشابه")):return True
    words=set(re.findall(r"[A-Za-z]+|[\u0621-\u063A\u0641-\u064A]+",low))
    words |= {w[2:] for w in words if w.startswith("ال") and len(w)>4}
    norm_words={_normalize(w) for w in words}
    return bool(NORMALIZED_DOMAIN_TERMS.intersection(norm_words)) or bool(candidates(text))

def _record_summary(c):
    return "\n".join([f"• العنوان: {c.get('title') or 'غير مستخرج'}",
      f"• المؤلف/المسؤول: {c.get('author') or 'غير مستخرج ويحتاج مراجعة'}",
      f"• ISBN: {c.get('isbn') or 'لم يُعثر على رقم صالح'}",
      f"• الناشر: {c.get('publisher') or 'غير مستخرج'}",
      f"• سنة النشر: {c.get('publication_year') or 'غير مستخرجة'}",
      f"• DDC: {c.get('ddc') or 'غير مقترح'}",f"• LCC: {c.get('lcc') or 'غير مقترح'}",
      f"• رقم الطلب: {c.get('call_number') or 'غير متوفر'}"])

def _format_records(records):
    if not records:return "لا توجد نتائج موثقة."
    return "\n".join(f"{i}. «{r.get('title') or 'بلا عنوان'}» — {r.get('author') or 'المؤلف غير محدد'}"
      f" | {r.get('publication_year') or 'بلا سنة'} | اللغة: {r.get('language') or '—'}"
      f" | DDC: {r.get('ddc') or '—'} | رقم الطلب: {r.get('call_number') or 'غير متوفر'}"
      for i,r in enumerate(records[:10],1))

def _sources(chunks):
    unique=[]
    for c in chunks:
        if c["citation"] not in unique:unique.append(c["citation"])
    return unique

def respond(message,context,history,stats,search_fn,retrieve_fn,missing_fn,duplicates_fn):
    text=(message or "").strip(); low=text.lower(); context=context or {}; history=history or []
    if not text:return {"reply":"اكتب طلبًا مكتبيًا لأبدأ.","intent":"empty","sources":[],"tools":[]}
    found=candidates(text)
    if found:
        x=found[0]; info=status(x["normalized"])
        return {"reply":f"تحققت من {info['value']}: {info['type']} — "
          f"{'صالح رياضيًا ✅' if info['valid'] else 'غير صالح رياضيًا ❌'}. {info['message']}.",
          "intent":"isbn_validation","sources":[],"tools":["ISBN Validator"]}
    if any(x in low for x in ("مرحبا","مرحباً","السلام عليكم","اهلا","أهلاً","هلا","هاي","hello","hi","hey")):
        return {"reply":"أهلًا بك. أنا وكيل AICC المكتبي، ولست محادثة عامة. أبحث في الفهرس، "
          "أحلل السجلات، أفرز الكتب، أراجع ISBN وMARC، أسترجع سياسات المكتبة عبر RAG، "
          "وأعد تقارير من البيانات الفعلية.","intent":"greeting","sources":[],"tools":[]}
    if not _in_scope(text,context):
        return {"reply":"هذا الطلب خارج نطاقي. أنا محدود بالمكتبات، سجلات الموقع، الفهرسة، التصنيف، "
          "خدمات المكتبة والتقارير فقط.","intent":"out_of_scope","sources":[],"tools":["Scope Guard"]}

    if any(x in low for x in ("من انت","من أنت","عرف بنفسك","عرّف بنفسك",
      "ماذا تستطيع","وش تقدر","كيف تساعدني","ما دورك")):
        llm,error=_optional_llm(text,history,context,[],[])
        if llm:
            return {"reply":llm,"intent":"assistant_identity","sources":["تعريف وكيل AICC"],
              "tools":["OpenAI Responses API"],"ai":{"used":True,"model":ai_config()["model"]}}
        fallback=("أنا أمين مكتبة AICC الذكي. أستخدم GPT مع فهرس الموقع وقاعدة RAG "
          "للبحث عن الكتب وتحليل السجلات ومراجعة الفهرسة والتصنيف، وأوضح عندما لا توجد أدلة.")
        if error and error!="not_configured":
            fallback+=f"\n\nتعذر الوصول إلى GPT حاليًا ({error}). افحص اتصال API والرصيد."
        return {"reply":fallback,"intent":"assistant_identity","sources":[],
          "tools":["OpenAI Responses API"],"ai":{"used":False,"error":error}}

    if any(x in low for x in ("هذا الكتاب","الكتاب الحالي","الكتاب الأخير","حلل السجل","حلل الكتاب","بيانات الكتاب")):
        return {"reply":"تحليل السجل النشط:\n"+_record_summary(context)+
          "\n\nالحقول المفقودة لا أخمّنها؛ يلزم الرجوع إلى صور الكتاب أو مصدر موثوق.",
          "intent":"active_record","sources":["جلسة التحليل النشطة"],"tools":["Active Record Inspector"]}

    missing_map={"isbn":"isbn","مؤلف":"author","ناشر":"publisher","سنة":"publication_year",
      "ddc":"ddc","تصنيف":"ddc","رقم الطلب":"call_number"}
    if any(x in low for x in ("ناقص","ناقصة","بدون","مفقود","مفقودة")):
        field=next((v for k,v in missing_map.items() if k in low),"isbn")
        rows=missing_fn(field)
        return {"reply":f"وجدت {len(rows)} سجلًا يفتقد الحقل «{field}»:\n"+_format_records(rows),
          "intent":"missing_fields_report","sources":["قاعدة بيانات الفهرس"],"tools":["Missing Fields Report"]}

    if any(x in low for x in ("مكرر","مكررة","تكرار","duplicate")):
        rows=duplicates_fn()
        if not rows:reply="لم أجد أرقام ISBN مكررة بين السجلات المعتمدة."
        else:reply="التكرارات المحتملة:\n"+"\n".join(f"• ISBN {x['isbn']} — {x['count']} سجلات: {x['titles']}" for x in rows)
        return {"reply":reply,"intent":"duplicate_report","sources":["قاعدة بيانات الفهرس"],"tools":["Duplicate Detector"]}

    if any(x in low for x in ("احصائ","إحصائ","كم كتاب","تقرير","توزيع")):
        langs="، ".join(f"{x['language']}: {x['count']}" for x in stats.get("languages",[])) or "لا توجد بيانات"
        ddc="، ".join(f"{x['ddc']}: {x['count']}" for x in stats.get("top_ddc_list",[])[:5]) or "لا توجد بيانات"
        return {"reply":f"تقرير مباشر من قاعدة البيانات:\n• السجلات المعتمدة: {stats.get('total',0)}"
          f"\n• المسودات: {stats.get('pending',0)}\n• اللغات: {langs}\n• أكثر تصنيفات DDC: {ddc}",
          "intent":"catalog_report","sources":["إحصائيات الفهرس الحالية"],"tools":["Report Tool"]}

    if "marc" in low or "مارك" in low:
        chunks=retrieve_fn(text)
        author_tag="110" if context.get("author_type")=="corporate" else "100" if context.get("author") else "لا يوجد 1XX"
        reply=f"بالنسبة للسجل النشط: مدخل المسؤولية المتوقع {author_tag}، العنوان في 245، والنشر في 264. "
        reply+="لا يُنشأ 020 إلا عند وجود ISBN صالح. القرار النهائي للمفهرس."
        if chunks:reply+="\n\nمن قاعدة المعرفة:\n"+chunks[0]["content"][:650]
        return {"reply":reply,"intent":"marc_rag","sources":_sources(chunks) or ["قواعد MARC المحلية"],
          "tools":["Active Record Inspector","RAG Retriever"]}

    # Retrieval and catalog tools run together, then the orchestrator selects the best evidence.
    query=_query(text)
    language="العربية" if "عربي" in low or "العربية" in low else "الإنجليزية" if "انجليزي" in low or "إنجليزي" in low else ""
    year_match=re.search(r"(?:بعد|منذ|من)\s*(20\d{2}|19\d{2})",text)
    records=search_fn(query,language,year_match.group(1) if year_match else "")
    if any(x in low for x in ("الأحدث","احدث","حديث","جديد")):
        records.sort(key=lambda r:r.get("publication_year") or "",reverse=True)
    elif any(x in low for x in ("الأقدم","اقدم","قديم")):
        records.sort(key=lambda r:r.get("publication_year") or "9999")
    elif "رتب" in low and "عنوان" in low:
        records.sort(key=lambda r:r.get("title") or "")
    chunks=retrieve_fn(text)
    has_evidence=bool(records or chunks or context.get("title"))
    llm,llm_error=_optional_llm(text,history,context,records,chunks) if has_evidence else ("","")
    if llm:return {"reply":llm,"intent":"grounded_ai","sources":[r["id"] for r in records[:5]]+_sources(chunks),
      "tools":["Intent Router","Catalog Search","RAG Retriever","OpenAI Responses API"],
      "ai":{"used":True,"model":ai_config()["model"],"provider":ai_config()["provider"]}}

    if any(x in low for x in ("اقترح","مشابه","مشابهة","مثل هذا","توصية")):
        if not records and context.get("title"):records=search_fn(context.get("title",""))
        return {"reply":"اقتراحات موثقة من الفهرس:\n"+_format_records(records)+
          "\n\nلم أضف أي كتاب غير موجود في قاعدة البيانات.",
          "intent":"recommendation","sources":[r["id"] for r in records[:10]],
          "tools":["Recommendation Tool","Catalog Search"]}
    if records:
        filters=[]
        if language:filters.append("اللغة="+language)
        if year_match:filters.append("من سنة "+year_match.group(1))
        return {"reply":f"وجدت {len(records)} نتيجة موثقة"+(f" ({'، '.join(filters)})" if filters else "")+
          ":\n"+_format_records(records)+"\n\nيمكنك طلب فرزها بالأحدث أو الأقدم أو تحديد لغة وسنة.",
          "intent":"catalog_search","sources":[r["id"] for r in records[:10]],
          "tools":["Intent Router","Catalog Search","Filter & Sort"],
          "ai":{"used":False,"error":llm_error} if llm_error else {"used":False}}
    if chunks:
        excerpt="\n\n".join(f"من «{x['citation']}»:\n{x['content'][:750]}" for x in chunks[:2])
        return {"reply":excerpt,"intent":"rag_answer","sources":_sources(chunks),
          "tools":["Intent Router","RAG Retriever"]}
    return {"reply":"لم أجد إجابة موثقة في فهرس الموقع أو قاعدة معرفة المكتبة. "
      "لن أخمّن. يمكن للمسؤول رفع سياسة أو دليل إلى قاعدة المعرفة، أو يمكنك تبسيط طلب البحث.",
      "intent":"no_verified_evidence","sources":[],"tools":["Catalog Search","RAG Retriever"]}
