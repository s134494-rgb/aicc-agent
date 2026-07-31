import hashlib, re
ARABIC_INITIALS={
 "ا":"A","أ":"A","إ":"A","آ":"A","ب":"B","ت":"T","ث":"T","ج":"J","ح":"H","خ":"K",
 "د":"D","ذ":"D","ر":"R","ز":"Z","س":"S","ش":"S","ص":"S","ض":"D","ط":"T","ظ":"Z",
 "ع":"A","غ":"G","ف":"F","ق":"Q","ك":"K","ل":"L","م":"M","ن":"N","ه":"H","و":"W","ي":"Y"}
RULES=[
 (["الذكاء الاصطناعي","تعلم الآلة","التعلم الآلي","شبكات عصبية","artificial intelligence"],"006.3","Q335",["الذكاء الاصطناعي","تعلم الآلة"],"الحوسبة والذكاء الاصطناعي"),
 (["برمجة","خوارزميات","حاسوب","الحاسوب","software","programming"],"005.1","QA76.6",["برمجة الحاسوب"],"البرمجة والخوارزميات"),
 (["فهرسة","تصنيف","المكتبات","علم المكتبات","library"],"025.3","Z693",["الفهرسة","التصنيف"],"عمليات الفهرسة والتصنيف"),
 (["تعليم اللغة العربية","تدريس اللغة العربية","تعليم العربية"],"492.7071","PJ6068",["اللغة العربية — تعليم"],"تعليم اللغة العربية"),
 (["لغة عربية","النحو","الصرف","بلاغة"],"492.7","PJ6001",["اللغة العربية"],"اللغة العربية"),
 (["إدارة","القيادة","management","ريادة الأعمال"],"658","HD31",["الإدارة"],"الإدارة والقيادة"),
 (["اقتصاد","اقتصادي","economics"],"330","HB71",["الاقتصاد"],"الاقتصاد"),
 (["قانون","تشريع","حقوق","law"],"340","K",["القانون"],"القانون"),
 (["طب","صحة","مرض","علاج","medicine"],"610","R",["الطب"],"الطب والصحة"),
 (["هندسة","engineering"],"620","TA",["الهندسة"],"الهندسة"),
 (["تاريخ","حضارة","history"],"900","D",["التاريخ"],"التاريخ والحضارة"),
 (["جغرافيا","خرائط","geography"],"910","G",["الجغرافيا"],"الجغرافيا"),
 (["أدب","رواية","شعر","قصة","literature"],"892.7","PJ7501",["الأدب العربي"],"الأدب العربي"),
 (["دين","الإسلام","القرآن","حديث","فقه"],"297","BP",["الإسلام"],"الدراسات الإسلامية"),
 (["علم النفس","نفسي","psychology"],"150","BF",["علم النفس"],"علم النفس"),
 (["تربية","تعليم","مناهج","education"],"370","L",["التربية والتعليم"],"التربية والتعليم")]

def build_cutter(author,title):
    source=(author or title or "كتاب").strip()
    chars=re.sub(r"[^A-Za-z\u0600-\u06FF]","",source)
    letter=(chars[0].upper() if chars and chars[0].isascii()
            else ARABIC_INITIALS.get(chars[0],"A") if chars else "A")
    number=100+(int(hashlib.sha256(source.encode()).hexdigest()[:4],16)%899)
    return f"{letter}{number}"

def classify(title,summary,keywords,author,year,verified=None,classification_system="ddc"):
    verified=verified or {}
    classification_system="lcc" if classification_system=="lcc" else "ddc"
    if verified.get("verified_ddc") or verified.get("verified_lcc"):
        ddc=verified.get("verified_ddc",""); lcc=verified.get("verified_lcc","")
        cutter=build_cutter(author,title)
        selected=ddc if classification_system=="ddc" else lcc
        return {"ddc":ddc,"lcc":lcc,"cutter":cutter,
          "classification_system":classification_system,
          "selected_classification":selected,
          "call_number":" ".join(x for x in [selected,cutter,year] if x),
          "subject_headings":(verified.get("verified_subjects") or [])[:6],
          "reason":"تصنيف مسترجع من سجل ISBN خارجي موثق.","confidence":96,
          "alternatives":[],"ddc_source":verified.get("verification_source","ISBN source"),
          "lcc_source":verified.get("verification_source","ISBN source"),
          "requires_review":True,
          "classification_basis":{"title":title,"keywords":keywords or [],
            "matched_rule":"تصنيف مرتبط بالطبعة عبر ISBN"}}
    verified_subjects=verified.get("verified_subjects") or []
    text=" ".join([title or "",summary or ""," ".join(keywords or []),
                   " ".join(verified_subjects)]).lower()
    ranked=[]
    for terms,ddc,lcc,subjects,reason in RULES:
        title_hits=sum(1 for t in terms if t.lower() in (title or "").lower())
        supporting_hits=sum(1 for t in terms if t.lower() in
            " ".join([summary or ""," ".join(keywords or [])," ".join(verified_subjects)]).lower())
        score=title_hits*3+supporting_hits
        if score: ranked.append((score,ddc,lcc,subjects,reason))
    ranked.sort(reverse=True)
    if ranked:
        score,ddc,lcc,subjects,reason=ranked[0]
        # A lone generic keyword is not enough for a professional number.
        if score < 3:
            ranked=[]
        else:
            confidence=min(88,55+score*5)
    if ranked:
        score,ddc,lcc,subjects,reason=ranked[0]
        alternatives=[{"ddc":r[1],"lcc":r[2],"reason":r[4]} for r in ranked[1:4]]
    else:
        ddc=lcc=""; subjects=(keywords or [])[:3]; reason="الأدلة غير كافية لتحديد رقم دقيق."; confidence=35; alternatives=[]
    cutter=build_cutter(author,title)
    selected=ddc if classification_system=="ddc" else lcc
    call=" ".join(x for x in [selected,cutter,year] if x)
    return {"ddc":ddc,"lcc":lcc,"cutter":cutter,"call_number":call,
      "classification_system":classification_system,
      "selected_classification":selected,
      "subject_headings":subjects,"reason":reason,"confidence":confidence,
      "alternatives":alternatives,"ddc_source":"اقتراح AI أولي — يتطلب جدول DDC مرخصًا للاعتماد",
      "lcc_source":"اقتراح أولي من قواعد محلية — يتطلب مراجعة الجدول المعتمد",
      "requires_review":confidence < 90,
      "classification_basis":{"title":title,"keywords":keywords or [],
        "matched_rule":reason if ddc else "لا توجد مطابقة موثوقة"}}
