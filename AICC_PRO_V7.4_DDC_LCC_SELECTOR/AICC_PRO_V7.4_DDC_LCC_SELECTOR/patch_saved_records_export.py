from pathlib import Path

p = Path("app/main.py")
text = p.read_text(encoding="utf-8")

if "from fastapi.middleware.cors import CORSMiddleware" not in text:
    text = text.replace(
        'from fastapi import Body, FastAPI, File, Form, Header, HTTPException, Request, UploadFile\n',
        'from fastapi import Body, FastAPI, File, Form, Header, HTTPException, Request, UploadFile\nfrom fastapi.middleware.cors import CORSMiddleware\n',
        1
    )

app_anchor = 'app=FastAPI(title="AICC — AI Cataloging & Classification Center",version="7.0.0",\n description="Evidence-grounded bilingual library cataloging MVP")\n'
if 'allow_origins=["https://smlib.kesug.com"]' not in text:
    cors = app_anchor + 'app.add_middleware(\n    CORSMiddleware,\n    allow_origins=["https://smlib.kesug.com"],\n    allow_credentials=False,\n    allow_methods=["GET", "OPTIONS"],\n    allow_headers=["*"],\n)\n'
    if app_anchor not in text:
        raise SystemExit("FastAPI app anchor not found")
    text = text.replace(app_anchor, cors, 1)

records_anchor = '@app.get("/api/records")\ndef records(q:str="",language:str="",year_from:str="",authorization:str|None=Header(None)):\n    actor(authorization); return {"ok":True,"items":search_books(q,language,year_from,500)}\n'

platform_endpoint = '''@app.get("/api/platform/records")
def platform_records():
    items=[]
    for row in search_books("","","",5000):
        full=get_book(row.get("id")) or row
        items.append({
          "aicc_id":full.get("id",""),
          "title":full.get("title","") or "",
          "subtitle":full.get("subtitle","") or "",
          "author":full.get("author","") or "",
          "author_type":full.get("author_type","") or "",
          "isbn":full.get("isbn","") or "",
          "publisher":full.get("publisher","") or "",
          "publication_place":full.get("publication_place","") or "",
          "publication_year":full.get("publication_year","") or "",
          "edition":full.get("edition","") or "",
          "language":full.get("language","") or "",
          "ddc":full.get("ddc","") or "",
          "lcc":full.get("lcc","") or "",
          "cutter":full.get("cutter","") or "",
          "classification_system":full.get("classification_system","ddc") or "ddc",
          "call_number":full.get("call_number","") or "",
          "keywords":full.get("keywords") or [],
          "subjects":full.get("subjects") or [],
          "summary":full.get("summary","") or "",
          "marc_json":full.get("marc_json") or {},
          "quality_score":int(full.get("quality_score") or 0),
          "created_at":full.get("created_at","") or "",
          "updated_at":full.get("updated_at","") or "",
        })
    return {"ok":True,"count":len(items),"items":items}

'''

if "/api/platform/records" not in text:
    if records_anchor not in text:
        raise SystemExit("records endpoint anchor not found")
    text = text.replace(records_anchor, platform_endpoint + records_anchor, 1)

p.write_text(text, encoding="utf-8")
print("AICC saved-record export patch applied")
