from datetime import datetime, timezone
from uuid import uuid4
from xml.sax.saxutils import escape
from .isbn_agent import status

def _f(tag,ind1=" ",ind2=" ",subs=None):
    return {"tag":tag,"ind1":ind1,"ind2":ind2,"subfields":subs or []}

def build_marc(book,cataloging,summary):
    now=datetime.now(timezone.utc); control=str(uuid4())
    lang="ara" if book.get("language")=="العربية" else "eng"
    year=(book.get("publication_year") or "    ")[:4].ljust(4)
    fields=[{"tag":"001","value":control},{"tag":"005","value":now.strftime("%Y%m%d%H%M%S.0")},
      {"tag":"008","value":now.strftime("%y%m%d")+"s"+year+"    xx ||||| |||| 00| 0 "+lang+" d"}]
    fields.append(_f("040",subs=[{"code":"a","value":"AICC"},{"code":"b","value":lang},
      {"code":"e","value":"rda"},{"code":"c","value":"AICC"}]))
    if status(book.get("isbn",""))["valid"]: fields.append(_f("020",subs=[{"code":"a","value":book["isbn"]}]))
    author=book.get("author",""); corporate=book.get("author_type")=="corporate"
    if author: fields.append(_f("110" if corporate else "100","2" if corporate else "1",subs=[{"code":"a","value":author}]))
    subs=[{"code":"a","value":book.get("title","")}]
    if book.get("subtitle"): subs.append({"code":"b","value":book["subtitle"]})
    if author: subs.append({"code":"c","value":author})
    fields.append(_f("245","1" if author else "0","0",subs))
    if book.get("parallel_title"):
        fields.append(_f("246","3","1",[{"code":"a","value":book["parallel_title"]}]))
    if book.get("edition"): fields.append(_f("250",subs=[{"code":"a","value":book["edition"]}]))
    pub=[{"code":c,"value":v} for c,v in [("a",book.get("publication_place","")),("b",book.get("publisher","")),("c",book.get("publication_year",""))] if v]
    if pub: fields.append(_f("264"," ","1",pub))
    physical=[]
    if book.get("pages"): physical.append({"code":"a","value":f"{book['pages']} صفحة"})
    if book.get("illustrations"): physical.append({"code":"b","value":book["illustrations"]})
    if book.get("dimensions"): physical.append({"code":"c","value":book["dimensions"]})
    if physical: fields.append(_f("300",subs=physical))
    fields.append(_f("336",subs=[{"code":"a","value":"text"},{"code":"2","value":"rdacontent"}]))
    fields.append(_f("337",subs=[{"code":"a","value":"unmediated"},{"code":"2","value":"rdamedia"}]))
    fields.append(_f("338",subs=[{"code":"a","value":"volume"},{"code":"2","value":"rdacarrier"}]))
    classification_system=cataloging.get("classification_system","ddc")
    if classification_system=="ddc" and cataloging.get("ddc"):
        fields.append(_f("082","0","4",[{"code":"a","value":cataloging["ddc"]}]))
    if classification_system=="lcc" and cataloging.get("lcc"):
        fields.append(_f("050"," ","4",[{"code":"a","value":cataloging["lcc"]},{"code":"b","value":cataloging.get("cutter","")}]))
    if summary: fields.append(_f("520",subs=[{"code":"a","value":summary}]))
    if book.get("series"):
        series=[{"code":"a","value":book["series"]}]
        if book.get("series_number"):series.append({"code":"v","value":book["series_number"]})
        fields.append(_f("490","1"," ",series))
        fields.append(_f("830"," ","0",series))
    if book.get("bibliography_note"):fields.append(_f("504",subs=[{"code":"a","value":book["bibliography_note"]}]))
    if book.get("index_note"):fields.append(_f("500",subs=[{"code":"a","value":book["index_note"]}]))
    if book.get("general_notes"):fields.append(_f("500",subs=[{"code":"a","value":book["general_notes"]}]))
    if book.get("target_audience"):fields.append(_f("521",subs=[{"code":"a","value":book["target_audience"]}]))
    for field,role in (("translator","مترجم"),("editor","محرر")):
        if book.get(field):fields.append(_f("700","1"," ",[{"code":"a","value":book[field]},{"code":"e","value":role}]))
    for subject in cataloging.get("subject_headings",[]): fields.append(_f("650"," ","4",[{"code":"a","value":subject}]))
    return {"leader":"00000nam a2200000 i 4500","fields":fields}

def validate_marc(record):
    errors=[]; tags=[f.get("tag") for f in record.get("fields",[])]
    for required in ("001","005","008","245"):
        if required not in tags: errors.append(f"الحقل {required} مفقود")
    for f in record.get("fields",[]):
        if f.get("tag")=="020":
            val=next((x["value"] for x in f.get("subfields",[]) if x["code"]=="a"),"")
            if not status(val)["valid"]: errors.append("020$a يحتوي ISBN غير صالح")
    warnings=[]
    field245=next((f for f in record.get("fields",[]) if f.get("tag")=="245"),None)
    if field245 and not next((s.get("value") for s in field245.get("subfields",[]) if s.get("code")=="a"),""):
        errors.append("245$a لا يحتوي عنوانًا")
    if not any(t in tags for t in ("100","110","111")):
        warnings.append("لا يوجد مدخل رئيسي؛ تحقق من بيان المسؤولية")
    if "264" not in tags:
        warnings.append("بيانات النشر 264 غير مكتملة")
    if "300" not in tags:
        warnings.append("الوصف المادي 300 غير مكتمل")
    return {"valid":not errors,"errors":errors,"warnings":warnings}

def to_marcxml(record):
    p=['<?xml version="1.0" encoding="UTF-8"?>','<record xmlns="http://www.loc.gov/MARC21/slim">',
       f'<leader>{escape(record.get("leader",""))}</leader>']
    for f in record.get("fields",[]):
        if "value" in f: p.append(f'<controlfield tag="{escape(f["tag"])}">{escape(str(f["value"]))}</controlfield>'); continue
        p.append(f'<datafield tag="{escape(f["tag"])}" ind1="{escape(f.get("ind1"," "))}" ind2="{escape(f.get("ind2"," "))}">')
        for s in f.get("subfields",[]): 
            if s.get("value")!="": p.append(f'<subfield code="{escape(s["code"])}">{escape(str(s["value"]))}</subfield>')
        p.append("</datafield>")
    p.append("</record>"); return "\n".join(p)
