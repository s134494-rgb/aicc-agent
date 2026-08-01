from pathlib import Path

path = Path("app/main.py")
text = path.read_text(encoding="utf-8")

import_anchor = 'from .rag import documents as knowledge_documents, ingest as ingest_knowledge, retrieve as retrieve_knowledge\n'
if 'from .platform_sync import sync_to_platform' not in text:
    if import_anchor not in text:
        raise SystemExit('Could not find import anchor in app/main.py')
    text = text.replace(import_anchor, import_anchor + 'from .platform_sync import sync_to_platform\n', 1)

old = '''@app.post("/api/analysis/{sid}/approve")
def approve(sid:str,authorization:str|None=Header(None)):
    try: bid=approve_session(sid,actor(authorization))
    except ValueError as e:
      session=get_session(sid); quality=((session or {}).get("draft") or {}).get("quality") or {}
      blockers=quality.get("critical_errors") or []
      detail=str(e)+((" الأسباب: "+"؛ ".join(blockers)) if blockers else "")
      raise HTTPException(422,detail)
    if not bid: raise HTTPException(409,"الجلسة غير موجودة أو سبق اعتمادها")
    return {"ok":True,"record_id":bid,"message":"تم اعتماد السجل وحفظ الإصدار الأول."}
'''

new = '''@app.post("/api/analysis/{sid}/approve")
def approve(sid:str,authorization:str|None=Header(None)):
    user=actor(authorization)
    session_snapshot=get_session(sid)
    try: bid=approve_session(sid,user)
    except ValueError as e:
      session=get_session(sid); quality=((session or {}).get("draft") or {}).get("quality") or {}
      blockers=quality.get("critical_errors") or []
      detail=str(e)+((" الأسباب: "+"؛ ".join(blockers)) if blockers else "")
      raise HTTPException(422,detail)
    if not bid: raise HTTPException(409,"الجلسة غير موجودة أو سبق اعتمادها")

    draft=((session_snapshot or {}).get("draft") or {})
    platform_payload={
      "aicc_record_id":bid,
      "session_id":sid,
      "book":draft.get("book") or {},
      "pages":draft.get("pages") or [],
      "subject":draft.get("subject") or {},
      "cataloging":draft.get("cataloging") or {},
      "professional_cataloging":draft.get("professional_cataloging") or {},
      "marc":draft.get("marc") or {},
      "marcxml":draft.get("marcxml") or "",
      "marc_validation":draft.get("marc_validation") or {},
      "quality":draft.get("quality") or {},
    }
    platform=sync_to_platform(platform_payload)
    if platform.get("ok"):
      message="تم اعتماد السجل وحفظه في AICC وإضافته مباشرة إلى منصة المكتبة."
      audit(user,"platform.sync.success","book",str(bid),platform)
    else:
      message="تم اعتماد السجل في AICC، لكن تعذر حفظه في منصة المكتبة. يمكن إعادة المزامنة بعد فحص إعداد الربط."
      audit(user,"platform.sync.failed","book",str(bid),platform)

    return {"ok":True,"record_id":bid,"message":message,"platform_sync":platform}
'''

if old not in text:
    if 'platform_sync' in text:
        print('main.py already appears patched')
    else:
        raise SystemExit('Could not find the exact approve() block; repository version may have changed.')
else:
    text = text.replace(old, new, 1)

path.write_text(text, encoding='utf-8')
print('AICC platform integration patch applied.')
