import json
import sqlite3
import re
from difflib import SequenceMatcher
from pathlib import Path
from uuid import uuid4

DB_PATH = Path(__file__).resolve().parent / "data" / "aicc.db"

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def initialize():
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id TEXT PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role TEXT,
          active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS analysis_sessions(
          id TEXT PRIMARY KEY, status TEXT NOT NULL, draft_json TEXT NOT NULL,
          created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS books(
          id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'approved',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          approved_at TEXT, approved_by TEXT, version INTEGER DEFAULT 1,
          title TEXT, subtitle TEXT, author TEXT, author_type TEXT, isbn TEXT,
          publisher TEXT, publication_place TEXT, publication_year TEXT, edition TEXT,
          language TEXT, raw_text TEXT NOT NULL, ddc TEXT, lcc TEXT, cutter TEXT,
          classification_system TEXT DEFAULT 'ddc', call_number TEXT, keywords TEXT,
          subjects TEXT, summary TEXT, marc_json TEXT,
          quality_score INTEGER DEFAULT 0, deleted_at TEXT);
        CREATE TABLE IF NOT EXISTS record_versions(
          id TEXT PRIMARY KEY, book_id TEXT NOT NULL, version INTEGER NOT NULL,
          snapshot_json TEXT NOT NULL, created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS pages(
          id TEXT PRIMARY KEY, session_id TEXT, book_id TEXT, filename TEXT, page_type TEXT,
          language TEXT, raw_text TEXT, clean_text TEXT, quality_score INTEGER,
          warnings TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS audit_logs(
          id TEXT PRIMARY KEY, actor TEXT, action TEXT, entity_type TEXT, entity_id TEXT,
          details TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS knowledge_documents(
          id TEXT PRIMARY KEY, title TEXT NOT NULL, filename TEXT, category TEXT,
          language TEXT, access_level TEXT DEFAULT 'public', version TEXT DEFAULT '1',
          status TEXT DEFAULT 'indexed', chunk_count INTEGER DEFAULT 0,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS knowledge_chunks(
          id TEXT PRIMARY KEY, document_id TEXT NOT NULL, chunk_index INTEGER NOT NULL,
          heading TEXT, content TEXT NOT NULL, normalized_text TEXT NOT NULL,
          FOREIGN KEY(document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE);
        CREATE INDEX IF NOT EXISTS idx_knowledge_document ON knowledge_chunks(document_id);
        CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
        CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn);
        CREATE INDEX IF NOT EXISTS idx_books_ddc ON books(ddc);
        """)
        columns={row["name"] for row in conn.execute("PRAGMA table_info(books)")}
        if "classification_system" not in columns:
            conn.execute("ALTER TABLE books ADD COLUMN classification_system TEXT DEFAULT 'ddc'")
        # Demo credentials are deliberately local-only and prominently documented.
        conn.execute("""INSERT OR IGNORE INTO users(id,username,password_hash,role)
                        VALUES('demo-admin','admin','aicc-demo-change-me','system_admin')""")

def audit(actor, action, entity_type="", entity_id="", details=None):
    with connect() as conn:
        conn.execute("INSERT INTO audit_logs VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)",
          (str(uuid4()), actor, action, entity_type, entity_id,
           json.dumps(details or {}, ensure_ascii=False)))

def create_session(draft, actor="demo-admin"):
    sid = str(uuid4())
    with connect() as conn:
        conn.execute("""INSERT INTO analysis_sessions(id,status,draft_json,created_by)
                        VALUES(?,?,?,?)""", (sid, "draft", json.dumps(draft, ensure_ascii=False), actor))
    audit(actor, "analysis.completed", "analysis_session", sid)
    return sid

def get_session(sid):
    with connect() as conn:
        row = conn.execute("SELECT * FROM analysis_sessions WHERE id=?", (sid,)).fetchone()
    if not row: return None
    data = dict(row); data["draft"] = json.loads(data.pop("draft_json"))
    return data

def update_session(sid, patch, actor="demo-admin"):
    session = get_session(sid)
    if not session or session["status"] != "draft": return None
    draft = session["draft"]
    for group in ("book", "cataloging", "subject", "marc", "quality",
                  "professional_cataloging", "marc_validation"):
        if isinstance(patch.get(group), dict):
            draft.setdefault(group, {}).update(patch[group])
    with connect() as conn:
        conn.execute("""UPDATE analysis_sessions SET draft_json=?,updated_at=CURRENT_TIMESTAMP
                        WHERE id=?""", (json.dumps(draft, ensure_ascii=False), sid))
    audit(actor, "draft.updated", "analysis_session", sid, {"groups": list(patch)})
    return draft

def find_by_isbn(isbn):
    if not isbn: return None
    with connect() as conn:
        row = conn.execute("""SELECT id,title,author,created_at FROM books
          WHERE isbn=? AND status='approved' AND deleted_at IS NULL LIMIT 1""",(isbn,)).fetchone()
    return dict(row) if row else None

def approve_session(sid, actor="demo-admin"):
    session = get_session(sid)
    if not session or session["status"] != "draft": return None
    d=session["draft"]; b=d["book"]; c=d["cataloging"]; s=d["subject"]; marc=d["marc"]
    if not (b.get("title") or "").strip():
        raise ValueError("لا يمكن اعتماد سجل بلا عنوان.")
    professional=d.get("professional_cataloging") or {}
    if not (professional.get("validation") or {}).get("valid",False):
        raise ValueError("لا يمكن اعتماد السجل قبل معالجة أخطاء وكيل الفهرسة المهنية.")
    if not (d.get("quality") or {}).get("may_submit",False):
        raise ValueError("لا يمكن اعتماد السجل قبل معالجة أخطاء الجودة الحرجة.")
    book_id=str(uuid4())
    snapshot={"book":b,"cataloging":c,"subject":s,"marc":marc}
    with connect() as conn:
        conn.execute("""INSERT INTO books(
          id,approved_at,approved_by,title,subtitle,author,author_type,isbn,publisher,
          publication_place,publication_year,edition,language,raw_text,ddc,lcc,cutter,
          classification_system,call_number,keywords,subjects,summary,marc_json,quality_score)
          VALUES(?,CURRENT_TIMESTAMP,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
          book_id,actor,b.get("title",""),b.get("subtitle",""),b.get("author",""),
          b.get("author_type","personal"),b.get("isbn",""),b.get("publisher",""),
          b.get("publication_place",""),b.get("publication_year",""),b.get("edition",""),
          b.get("language",""),b.get("raw_text",""),c.get("ddc",""),c.get("lcc",""),
          c.get("cutter",""),c.get("classification_system","ddc"),c.get("call_number",""),
          json.dumps(s.get("keywords",[]),ensure_ascii=False),
          json.dumps(c.get("subject_headings",[]),ensure_ascii=False),s.get("summary_draft",""),
          json.dumps(marc,ensure_ascii=False),d.get("quality",{}).get("score",0)))
        conn.execute("INSERT INTO record_versions VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)",
          (str(uuid4()),book_id,1,json.dumps(snapshot,ensure_ascii=False),actor))
        conn.execute("UPDATE analysis_sessions SET status='approved',updated_at=CURRENT_TIMESTAMP WHERE id=?",(sid,))
    audit(actor,"record.approved","book",book_id,{"session_id":sid})
    return book_id

def recent_books(limit=30):
    with connect() as conn:
        rows=conn.execute("""SELECT id,created_at,title,author,isbn,language,status,quality_score
          FROM books WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT ?""",(limit,)).fetchall()
    return [dict(r) for r in rows]

def get_book(book_id):
    with connect() as conn:
        row=conn.execute("""SELECT * FROM books
          WHERE id=? AND deleted_at IS NULL""",(book_id,)).fetchone()
    if not row:return None
    item=dict(row)
    for field,default in (("keywords",[]),("subjects",[]),("marc_json",{})):
        try:item[field]=json.loads(item.get(field) or json.dumps(default))
        except (TypeError,json.JSONDecodeError):item[field]=default
    return item

def update_book(book_id, fields, actor="demo-admin"):
    current=get_book(book_id)
    if not current:return None
    allowed={"title","subtitle","author","author_type","isbn","publisher",
      "publication_place","publication_year","edition","language","raw_text",
      "ddc","lcc","cutter","classification_system","call_number","keywords","subjects","summary",
      "marc_json","quality_score"}
    patch={key:value for key,value in (fields or {}).items() if key in allowed}
    if not str(patch.get("title",current.get("title","")) or "").strip():
        raise ValueError("لا يمكن حفظ سجل بلا عنوان.")
    for field in ("keywords","subjects","marc_json"):
        if field in patch and not isinstance(patch[field],str):
            patch[field]=json.dumps(patch[field],ensure_ascii=False)
    version=int(current.get("version") or 1)+1
    assignments=[f"{field}=?" for field in patch]
    values=list(patch.values())
    snapshot=dict(current)
    snapshot.update(fields or {})
    snapshot["version"]=version
    with connect() as conn:
        if assignments:
            conn.execute(f"""UPDATE books SET {",".join(assignments)},
              version=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND deleted_at IS NULL""",
              (*values,version,book_id))
        conn.execute("INSERT INTO record_versions VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)",
          (str(uuid4()),book_id,version,json.dumps(snapshot,ensure_ascii=False),actor))
    audit(actor,"record.updated","book",book_id,{"version":version,"fields":list(patch)})
    return get_book(book_id)

def delete_book(book_id, actor="demo-admin"):
    current=get_book(book_id)
    if not current:return False
    with connect() as conn:
        conn.execute("""UPDATE books SET status='deleted',deleted_at=CURRENT_TIMESTAMP,
          updated_at=CURRENT_TIMESTAMP WHERE id=? AND deleted_at IS NULL""",(book_id,))
    audit(actor,"record.deleted","book",book_id,{"title":current.get("title","")})
    return True

def search_books(query="", language="", year_from="", limit=25):
    def norm(value):
        value=(value or "").lower().replace("أ","ا").replace("إ","ا").replace("آ","ا").replace("ى","ي").replace("ة","ه")
        value=re.sub(r"[\u064b-\u065f\u0670ـ]","",value)
        return re.sub(r"\s+"," ",re.sub(r"[^\w\u0600-\u06ff]+"," ",value)).strip()
    q=norm(query); terms=[x for x in q.split() if len(x)>1]
    with connect() as conn:
        rows=conn.execute("""SELECT id,title,author,isbn,publication_year,language,ddc,lcc,
          call_number,summary,keywords,subjects,publisher,quality_score,created_at
          FROM books WHERE status='approved' AND deleted_at IS NULL""").fetchall()
    results=[]
    for raw in rows:
        row=dict(raw)
        if language and norm(language) not in norm(row.get("language","")):continue
        if year_from and int(row.get("publication_year") or 0)<int(year_from):continue
        hay=norm(" ".join(str(row.get(k) or "") for k in
          ("title","author","isbn","summary","keywords","subjects","publisher","ddc","lcc","call_number")))
        if not terms:score=1
        else:
            matched=sum(1 for t in terms if t in hay)
            if matched==0 and not (q and q==norm(row.get("isbn",""))):continue
            score=matched*12
            if q and q in hay:score+=35
            if q and q==norm(row.get("isbn","")):score+=100
            score+=SequenceMatcher(None,q,norm(row.get("title",""))).ratio()*18
        row["relevance_score"]=round(score,2)
        row["match_reason"]="مطابقة عنوان/مؤلف/موضوع/معرّف داخل الفهرس المحلي"
        results.append(row)
    results.sort(key=lambda x:(x["relevance_score"],x.get("quality_score",0)),reverse=True)
    return results[:limit]

def stats():
    with connect() as conn:
        total=conn.execute("SELECT COUNT(*) n FROM books WHERE deleted_at IS NULL").fetchone()["n"]
        pending=conn.execute("SELECT COUNT(*) n FROM analysis_sessions WHERE status='draft'").fetchone()["n"]
        langs=conn.execute("""SELECT COALESCE(NULLIF(language,''),'غير محدد') language,COUNT(*) n
          FROM books WHERE deleted_at IS NULL GROUP BY language ORDER BY n DESC""").fetchall()
        ddc=conn.execute("""SELECT ddc,COUNT(*) n FROM books WHERE deleted_at IS NULL AND ddc!=''
          GROUP BY ddc ORDER BY n DESC LIMIT 10""").fetchall()
    items=[{"ddc":r["ddc"],"count":r["n"]} for r in ddc]
    return {"total":total,"pending":pending,
      "languages":[{"language":r["language"],"count":r["n"]} for r in langs],
      "top_ddc_list":items,"top_ddc":(items[0]["ddc"],items[0]["count"]) if items else None}

def audit_list(limit=100):
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?",(limit,))]

def save_knowledge_document(title, filename, category, language, chunks, access_level="public"):
    document_id=str(uuid4())
    with connect() as conn:
        conn.execute("""INSERT INTO knowledge_documents(
          id,title,filename,category,language,access_level,chunk_count)
          VALUES(?,?,?,?,?,?,?)""",(document_id,title,filename,category,language,access_level,len(chunks)))
        for index,chunk in enumerate(chunks):
            conn.execute("""INSERT INTO knowledge_chunks(
              id,document_id,chunk_index,heading,content,normalized_text)
              VALUES(?,?,?,?,?,?)""",(str(uuid4()),document_id,index,chunk.get("heading",""),
              chunk["content"],chunk["normalized"]))
    audit("demo-admin","knowledge.indexed","knowledge_document",document_id,{"chunks":len(chunks)})
    return document_id

def list_knowledge_documents():
    with connect() as conn:
        rows=conn.execute("""SELECT id,title,filename,category,language,access_level,
          version,status,chunk_count,created_at FROM knowledge_documents
          ORDER BY created_at DESC""").fetchall()
    return [dict(r) for r in rows]

def knowledge_chunks():
    with connect() as conn:
        rows=conn.execute("""SELECT c.id,c.chunk_index,c.heading,c.content,c.normalized_text,
          d.id document_id,d.title document_title,d.category,d.language,d.access_level
          FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id
          WHERE d.status='indexed'""").fetchall()
    return [dict(r) for r in rows]

def records_missing(field="isbn",limit=50):
    allowed={"isbn","author","publisher","publication_year","ddc","call_number"}
    field=field if field in allowed else "isbn"
    with connect() as conn:
        rows=conn.execute(f"""SELECT id,title,author,isbn,publisher,publication_year,ddc,call_number
          FROM books WHERE status='approved' AND deleted_at IS NULL
          AND ({field} IS NULL OR TRIM({field})='') ORDER BY created_at DESC LIMIT ?""",(limit,)).fetchall()
    return [dict(r) for r in rows]

def duplicate_candidates(limit=50):
    with connect() as conn:
        rows=conn.execute("""SELECT isbn,COUNT(*) count,GROUP_CONCAT(title,' | ') titles
          FROM books WHERE status='approved' AND deleted_at IS NULL AND isbn!=''
          GROUP BY isbn HAVING COUNT(*)>1 ORDER BY count DESC LIMIT ?""",(limit,)).fetchall()
    return [dict(r) for r in rows]
