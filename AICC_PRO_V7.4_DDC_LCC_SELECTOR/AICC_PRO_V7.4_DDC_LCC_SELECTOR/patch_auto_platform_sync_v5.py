from pathlib import Path

p=Path("app/static/app.js")
text=p.read_text(encoding="utf-8")

for marker in ("/* AICC_AUTO_PLATFORM_SYNC_V3 */","/* AICC_AUTO_PLATFORM_SYNC_V4_FORM */"):
    i=text.find(marker)
    if i!=-1:
        text=text[:i].rstrip()+"\n"

marker="/* AICC_AUTO_PLATFORM_SYNC_V5_BEACON */"
if marker not in text:
    block = r'''
/* AICC_AUTO_PLATFORM_SYNC_V5_BEACON */
const AICC_V5_IMPORT_URL="https://smlib.kesug.com/api/aicc_import_saved_record.php";
const AICC_V5_STATE_KEY="aicc-platform-v5-beacon-state";
let aiccV5Busy=false;

function aiccV5Read(){
  try{return JSON.parse(localStorage.getItem(AICC_V5_STATE_KEY)||"{}")}catch(_){return{}}
}
function aiccV5Write(s){
  try{localStorage.setItem(AICC_V5_STATE_KEY,JSON.stringify(s))}catch(_){}
}
function aiccV5Sig(r){
  return `${r.updated_at||r.created_at||""}|${r.title||""}|${r.isbn||""}|${r.quality_score||0}`;
}
function aiccV5Send(record){
  const payload=JSON.stringify(record);
  try{
    if(navigator.sendBeacon){
      const blob=new Blob([payload],{type:"text/plain;charset=UTF-8"});
      return navigator.sendBeacon(AICC_V5_IMPORT_URL,blob);
    }
  }catch(_){}
  fetch(AICC_V5_IMPORT_URL,{
    method:"POST",
    mode:"no-cors",
    keepalive:true,
    headers:{"Content-Type":"text/plain;charset=UTF-8"},
    body:payload
  }).catch(()=>{});
  return true;
}

async function aiccV5GetRecord(recordId){
  const r=await fetch(`/api/records/${encodeURIComponent(recordId)}`,{
    headers:{Authorization:"Bearer aicc-demo-token"},
    cache:"no-store"
  });
  if(!r.ok) throw new Error("record detail HTTP "+r.status);
  const d=await r.json();
  if(!d.ok||!d.item) throw new Error("invalid record detail");
  const x=d.item;
  return {
    aicc_id:x.id||recordId,
    title:x.title||"",
    subtitle:x.subtitle||"",
    author:x.author||"",
    author_type:x.author_type||"",
    isbn:x.isbn||"",
    publisher:x.publisher||"",
    publication_place:x.publication_place||"",
    publication_year:x.publication_year||"",
    edition:x.edition||"",
    language:x.language||"",
    ddc:x.ddc||"",
    lcc:x.lcc||"",
    cutter:x.cutter||"",
    classification_system:x.classification_system||"ddc",
    call_number:x.call_number||"",
    keywords:x.keywords||[],
    subjects:x.subjects||[],
    summary:x.summary||"",
    marc_json:x.marc_json||{},
    quality_score:Number(x.quality_score||0),
    created_at:x.created_at||"",
    updated_at:x.updated_at||""
  };
}

async function aiccV5SyncRecord(recordId){
  const record=await aiccV5GetRecord(recordId);
  if(!record.title) throw new Error("record has no title");
  const sent=aiccV5Send(record);
  if(sent){
    const state=aiccV5Read();
    state[String(record.aicc_id)]=aiccV5Sig(record);
    aiccV5Write(state);
    console.info("[AICC V5] immediate sync queued",record.title);
  }
}

async function aiccV5Backfill(){
  if(aiccV5Busy) return;
  aiccV5Busy=true;
  try{
    const r=await fetch("/api/platform/records",{cache:"no-store"});
    if(!r.ok) throw new Error("records HTTP "+r.status);
    const d=await r.json();
    if(!d.ok||!Array.isArray(d.items)) throw new Error("invalid records response");
    const state=aiccV5Read();
    for(const record of d.items){
      const id=String(record.aicc_id||"");
      if(!id) continue;
      const sig=aiccV5Sig(record);
      if(state[id]===sig) continue;
      if(aiccV5Send(record)){
        state[id]=sig;
        aiccV5Write(state);
      }
    }
  }catch(err){
    console.error("[AICC V5] backfill failed",err);
  }finally{
    aiccV5Busy=false;
  }
}

window.addEventListener("load",()=>setTimeout(aiccV5Backfill,1200));
setInterval(aiccV5Backfill,5000);
'''
    text += block

needle='''      approveBtn.textContent = "تم الاعتماد ✓";
      refreshStats();
'''
replacement='''      approveBtn.textContent = "تم الاعتماد ✓";
      refreshStats();
      setTimeout(() => {
        if (typeof aiccV5SyncRecord === "function") {
          aiccV5SyncRecord(data.record_id).catch(err => console.error("[AICC V5] immediate sync failed", err));
        }
      }, 300);
'''
if "aiccV5SyncRecord(data.record_id)" not in text:
    if needle not in text:
        raise SystemExit("Approval success block not found")
    text=text.replace(needle,replacement,1)

p.write_text(text,encoding="utf-8")
print("AICC V5 installed")
