import re
from collections import Counter
from .isbn_agent import candidates as isbn_candidates, find_valid_isbn, latin_digits

LABELS=r"(?:اسم\s*الكتاب|عنوان\s*الكتاب|العنوان|book\s*title)"
AUTHOR_LABELS=r"(?:تأليف|المؤلف(?:ون)?|إعداد|اعداد|بقلم|تحرير|author|written\s+by)"
PUBLISHER_LABELS=r"(?:الناشر|دار\s*النشر|نشر\s*وتوزيع|publisher|published\s+by)"
ROLE_WORDS={"تأليف","المؤلف","إعداد","اعداد","بقلم","تحرير","ترجمة","مراجعة","إشراف"}
BLOCKED=("isbn","ردمك","حقوق","copyright","الفهرس","المحتويات","المقدمة","الطبعة",
         "هاتف","فاكس","بريد","www.","http","إيداع","ايداع","رقم","تأليف","المؤلف",
         "إعداد","اعداد","بقلم","تحرير","ترجمة","مراجعة","الناشر","دار النشر")
PLACEHOLDERS=("أدلة ocr","ocr إضافية","غير واضح","غير مقروء","غير متوفر",
              "غير مذكور","unknown","not visible","not available")

def clean(value,limit=400):
    value=re.sub(r"[\u200e\u200f\u202a-\u202e]","",value or "")
    value=re.sub(r"\s+"," ",value).strip(" .،,:：;-–—|")
    return value[:limit]

def usable(value):
    low=clean(value).lower()
    return bool(low) and not any(marker in low for marker in PLACEHOLDERS) and not (
        low.startswith("[") and low.endswith("]"))

def lines(text):
    return [clean(x) for x in (text or "").splitlines() if clean(x)]

def match(pattern,text):
    found=re.search(pattern,text or "",re.I|re.M)
    return clean(found.group(1)) if found else ""

def title_candidate(pages,evidence):
    explicit=(evidence.get("title") or [])
    explicit=[x for x in explicit if x.get("quality_score",100)>=60]
    if explicit:
        best=max(explicit,key=lambda x:(x.get("ocr_agreement",0),x.get("quality_score",0)))
        return best["value"],best["filename"],92
    priority={"صفحة العنوان":140,"الغلاف الأمامي":125,"غلاف أو صفحة عنوان":110,"صفحة حقوق النشر":60}
    ranked=[]
    for p in pages:
        weight=priority.get(p.get("page_type",""),25)
        for i,line in enumerate(lines(p.get("text",""))[:30]):
            low=line.lower()
            if any(x in low for x in BLOCKED) or not usable(line) or len(line)>180:continue
            letters=len(re.findall(r"[A-Za-z\u0600-\u06FF]",line))
            words=len(line.split())
            if letters<5 or not 1<=words<=18:continue
            ranked.append((weight+min(letters,50)+max(0,25-i*2),line,p.get("filename","")))
    if not ranked:return "","",0
    # A title repeated independently on cover and title page is strong evidence.
    grouped={}
    for score,value,source in ranked:
        key=re.sub(r"[\W_]+","",value).lower()
        if key:
            grouped.setdefault(key,[]).append((score,value,source))
    repeated=[items for items in grouped.values()
              if len({item[2] for item in items})>=2]
    if repeated:
        items=max(repeated,key=lambda x:max(item[0] for item in x))
        _,value,source=max(items)
        value=re.sub(rf"^{LABELS}\s*[:：\-]?\s*","",value,flags=re.I)
        return clean(value),source,86
    _,value,source=max(ranked)
    # Remove OCR labels accidentally attached to the value.
    value=re.sub(rf"^{LABELS}\s*[:：\-]?\s*","",value,flags=re.I)
    # An unlabelled cover line is only a candidate. It must not be presented as
    # a reliable title or unlock approval by itself.
    return clean(value),source,58

def author_candidate(pages,evidence,title):
    explicit=(evidence.get("author") or [])
    explicit=[x for x in explicit if x.get("quality_score",100)>=60]
    if explicit:
        best=max(explicit,key=lambda x:(x.get("ocr_agreement",0),x.get("quality_score",0)))
        return best["value"],92,"explicit_label"
    patterns=[
      rf"{AUTHOR_LABELS}\s*[:：\-]?\s*([^\n]{{2,160}})",
      r"(?:د\.|دكتور|الدكتور|الأستاذ|أ\.د\.)\s*([^\n]{3,120})"]
    merged="\n".join(p.get("text","") for p in pages)
    for pattern in patterns:
        value=match(pattern,merged)
        if value and value!=title:return value,80,"role_pattern"
    # Never guess a personal name merely because a short line looks like one.
    return "",0,"unresolved"

def contributor(text,role_words):
    label="|".join(map(re.escape,role_words))
    return match(rf"(?:{label})\s*[:：\-]?\s*([^\n]{{2,140}})",text)

def extract_metadata(pages,language,evidence=None):
    evidence=evidence or {}
    merged="\n\n".join(p.get("text","") for p in pages)
    normalized=latin_digits(merged)
    title,source,title_score=title_candidate(pages,evidence)
    subtitle=match(r"(?:العنوان\s*الفرعي|subtitle)\s*[:：\-]?\s*([^\n]+)",merged)
    if not subtitle and ":" in title:
        title,subtitle=[clean(x) for x in title.split(":",1)]
    author,author_score,author_method=author_candidate(pages,evidence,title)
    publisher=(evidence.get("publisher") or [{}])[0].get("value","")
    if not publisher:
        publisher=match(rf"{PUBLISHER_LABELS}\s*[:：\-]?\s*([^\n]{{2,180}})",merged)
    if not publisher:
        pub_lines=[x for x in lines(merged) if re.search(r"\b(?:دار|مركز|مؤسسة|منشورات|جامعة)\b",x) and len(x)<160]
        publisher=pub_lines[-1] if pub_lines else ""
    valid_isbn=find_valid_isbn(normalized)
    all_isbns=isbn_candidates(normalized)
    copyright_pages="\n".join(
        p.get("text","") for p in pages
        if p.get("page_type")=="صفحة حقوق النشر" and p.get("quality_score",100)>=60)
    year_candidates=re.findall(r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2})\b",
                               latin_digits(copyright_pages))
    explicit_year=match(r"(?:سنة\s*النشر|تاريخ\s*النشر|published|publication\s*date)\s*[:：\-]?\s*(18\d{2}|19\d{2}|20\d{2}|21\d{2})",
                        normalized)
    year=explicit_year or (Counter(year_candidates).most_common(1)[0][0] if len(set(year_candidates))==1 else "")
    edition=match(r"(?:الطبعة|ط\.|edition)\s*[:：\-]?\s*([^\n]{1,100})",normalized)
    place=match(r"(?:مكان\s*النشر|نشر\s*في|publication\s*place)\s*[:：\-]?\s*([^\n]{2,100})",merged)
    if not place:
        for city in ("مسقط","القاهرة","بيروت","الرياض","دبي","الشارقة","عمان","الكويت","الدوحة","لندن"):
            if city in merged:place=city;break
    pages_count=match(r"\b(\d{1,4})\s*(?:ص(?:فحة)?|صفحة|pages?|p\.)\b",normalized)
    dimensions=match(r"\b(\d{1,3}(?:[.,]\d+)?)\s*(?:سم|cm)\b",normalized)
    series=match(r"(?:السلسلة|سلسلة|series)\s*[:：\-]?\s*([^\n]{2,140})",merged)
    translator=contributor(merged,("ترجمة","ترجمها","المترجم","translator"))
    editor=contributor(merged,("تحرير","المحرر","مراجعة","راجع","editor"))
    responsibility=match(r"(?:بيان\s*المسؤولية|statement\s*of\s*responsibility)\s*[:：\-]?\s*([^\n]+)",merged) or author
    bibliography=bool(re.search(r"مراجع|ببليوغرافي|bibliograph",merged,re.I))
    index_note=bool(re.search(r"كشاف|index",merged,re.I))
    confidence={"title":title_score,"subtitle":75 if subtitle else 0,"author":author_score,
      "isbn":100 if valid_isbn else 0,"publisher":82 if publisher else 0,
      "publication_place":75 if place else 0,"publication_year":92 if year else 0,
      "edition":82 if edition else 0,"language":92 if language else 0,
      "pages":78 if pages_count else 0,"dimensions":85 if dimensions else 0,
      "series":78 if series else 0,"translator":82 if translator else 0,"editor":82 if editor else 0}
    return {"title":title,"subtitle":subtitle,"parallel_title":"","other_title_information":subtitle,
      "statement_of_responsibility":responsibility,"author":author,"author_detection_method":author_method,
      "corporate_author":"","translator":translator,"editor":editor,"publisher":publisher,
      "publication_place":place,"publication_year":year,"copyright_date":year,
      "edition":edition,"isbn":valid_isbn,"isbn_candidates":all_isbns,"issn":"",
      "language":language,"original_language":"","pages":pages_count,
      "illustrations":"يوجد" if re.search(r"صور|رسوم|illustr",merged,re.I) else "",
      "dimensions":f"{dimensions} سم" if dimensions else "","accompanying_material":"",
      "series":series,"series_number":"","bibliography_note":"يتضمن مراجع" if bibliography else "",
      "index_note":"يتضمن كشافًا" if index_note else "","general_notes":"",
      "target_audience":"","resource_type":"نص","content_type":"نص","media_type":"بدون وسيط",
      "carrier_type":"مجلد","raw_text":merged,"confidence":confidence,"evidence":evidence,
      "title_source":source,
      "field_sources":{"title":source if title_score>=80 else "مرشح OCR غير مؤكد",
        "author":"عبارة مسؤولية صريحة" if author_score>=80 else "",
        "isbn":"تحقق ISBN الرياضي" if valid_isbn else "",
        "publication_year":"صفحة حقوق النشر" if year else ""},
      "verification_conflicts":[]}
