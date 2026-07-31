import csv, io, json, re
from html import unescape
from pathlib import Path
from .database import knowledge_chunks, list_knowledge_documents, save_knowledge_document

ARABIC_STOP={"في","من","على","الى","إلى","عن","ما","ماذا","كيف","هل","هو","هي","هذا","هذه",
 "التي","الذي","مع","او","أو","كل","اي","أي","اريد","أريد","لي","لدي","عندكم"}

def normalize(text):
    text=(text or "").lower()
    text=text.replace("أ","ا").replace("إ","ا").replace("آ","ا").replace("ى","ي").replace("ة","ه")
    text=re.sub(r"[\u064b-\u065f\u0670ـ]","",text)
    return re.sub(r"\s+"," ",re.sub(r"[^\w\u0600-\u06ff]+"," ",text)).strip()

def tokens(text):
    return [x for x in normalize(text).split() if len(x)>1 and x not in ARABIC_STOP]

def chunk_text(text,max_chars=1100,overlap=150):
    paragraphs=[re.sub(r"\s+"," ",p).strip() for p in re.split(r"\n\s*\n",text) if p.strip()]
    chunks=[]; current=""; heading=""
    for p in paragraphs:
        if len(p)<120 and (p.endswith(":") or len(p.split())<10):heading=p.strip(": ")
        if len(current)+len(p)+1>max_chars and current:
            chunks.append({"heading":heading,"content":current,"normalized":normalize(current)})
            current=current[-overlap:]+" "+p
        else:current=(current+" "+p).strip()
    if current:chunks.append({"heading":heading,"content":current,"normalized":normalize(current)})
    return chunks

def extract_document(filename,data):
    suffix=Path(filename).suffix.lower()
    if suffix in {".txt",".md"}:return data.decode("utf-8",errors="replace")
    if suffix==".html":
        return unescape(re.sub(r"<[^>]+>"," ",data.decode("utf-8",errors="replace")))
    if suffix==".json":
        obj=json.loads(data.decode("utf-8")); return json.dumps(obj,ensure_ascii=False,indent=2)
    if suffix==".csv":
        decoded=data.decode("utf-8-sig",errors="replace")
        return "\n".join(" | ".join(row) for row in csv.reader(io.StringIO(decoded)))
    if suffix==".pdf":
        try:
            from pypdf import PdfReader
            return "\n\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
        except ImportError:raise ValueError("ثبّت pypdf لدعم ملفات PDF.")
    if suffix==".docx":
        try:
            from docx import Document
            return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
        except ImportError:raise ValueError("ثبّت python-docx لدعم ملفات DOCX.")
    raise ValueError("الصيغة غير مدعومة. استخدم TXT أو MD أو HTML أو CSV أو JSON أو PDF أو DOCX.")

def ingest(title,filename,data,category="سياسات المكتبة",language="العربية",access_level="public"):
    text=extract_document(filename,data).strip()
    if len(text)<40:raise ValueError("لم يُستخرج نص كافٍ من الوثيقة.")
    chunks=chunk_text(text)
    return save_knowledge_document(title or filename,filename,category,language,chunks,access_level),len(chunks)

def retrieve(query,limit=5,access_level="public"):
    q_tokens=tokens(query)
    if not q_tokens:return []
    results=[]
    for row in knowledge_chunks():
        if access_level=="public" and row["access_level"]!="public":continue
        content_tokens=tokens(row["normalized_text"])
        if not content_tokens:continue
        counts={t:content_tokens.count(t) for t in q_tokens}
        matched=sum(1 for v in counts.values() if v)
        phrase=3 if normalize(query) in row["normalized_text"] else 0
        score=phrase+matched*2+sum(min(v,3) for v in counts.values())/max(len(content_tokens)**0.5,1)
        if score>0:
            results.append({**row,"score":round(score,3),
              "citation":f"{row['document_title']} — المقطع {row['chunk_index']+1}"})
    return sorted(results,key=lambda x:x["score"],reverse=True)[:limit]

def documents():
    return list_knowledge_documents()
