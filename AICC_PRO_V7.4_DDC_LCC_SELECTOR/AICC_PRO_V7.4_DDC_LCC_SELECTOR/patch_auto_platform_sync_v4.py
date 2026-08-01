from pathlib import Path

p=Path("app/static/app.js")
text=p.read_text(encoding="utf-8")
old=text.find("/* AICC_AUTO_PLATFORM_SYNC_V3 */")
if old!=-1:
    text=text[:old].rstrip()+"\n"
marker="/* AICC_AUTO_PLATFORM_SYNC_V4_FORM */"
if marker not in text:
    block = """\n/* AICC_AUTO_PLATFORM_SYNC_V4_FORM */
const AICC_V4_IMPORT_URL="https://smlib.kesug.com/api/aicc_import_saved_record.php";
const AICC_V4_STATE_KEY="aicc-platform-v4-form-state";
let aiccV4Busy=false;

function aiccV4Read(){try{return JSON.parse(localStorage.getItem(AICC_V4_STATE_KEY)||"{}")}catch(_){return{}}}
function aiccV4Write(s){try{localStorage.setItem(AICC_V4_STATE_KEY,JSON.stringify(s))}catch(_){}}
function aiccV4Sig(r){return `${r.updated_at||r.created_at||""}|${r.title||""}|${r.isbn||""}|${r.quality_score||0}`}

function aiccV4Submit(record){
  return new Promise((resolve,reject)=>{
    const frameName="aicc-v4-"+Date.now()+"-"+Math.random().toString(16).slice(2);
    const iframe=document.createElement("iframe"); iframe.name=frameName; iframe.style.display="none";
    const form=document.createElement("form"); form.method="POST"; form.action=AICC_V4_IMPORT_URL; form.target=frameName; form.style.display="none";
    const input=document.createElement("input"); input.type="hidden"; input.name="payload"; input.value=JSON.stringify(record); form.appendChild(input);
    document.body.appendChild(iframe); document.body.appendChild(form);

    const timeout=setTimeout(()=>{cleanup();reject(new Error("Platform sync timeout"))},15000);
    function onMessage(event){
      if(event.origin!=="https://smlib.kesug.com") return;
      if(!event.data||event.data.type!=="AICC_PLATFORM_IMPORT_RESULT") return;
      const d=event.data.data||{};
      if(String(d.aicc_id||"")!==String(record.aicc_id||"")) return;
      cleanup();
      if(d.ok) resolve(d); else reject(new Error(d.detail||d.error||"Platform sync failed"));
    }
    function cleanup(){clearTimeout(timeout);window.removeEventListener("message",onMessage);form.remove();iframe.remove()}
    window.addEventListener("message",onMessage);
    form.submit();
  });
}

async function aiccV4Sync(){
  if(aiccV4Busy) return;
  aiccV4Busy=true;
  try{
    const r=await fetch("/api/platform/records",{cache:"no-store"});
    if(!r.ok) throw new Error("records HTTP "+r.status);
    const d=await r.json();
    if(!d.ok||!Array.isArray(d.items)) throw new Error("invalid records response");
    const state=aiccV4Read();
    for(const record of d.items){
      const id=String(record.aicc_id||""); if(!id) continue;
      const sig=aiccV4Sig(record); if(state[id]===sig) continue;
      const result=await aiccV4Submit(record);
      state[id]=sig; aiccV4Write(state);
      console.info("[AICC V4] synced",record.title,result.mode,result.book_id);
    }
  }catch(err){console.error("[AICC V4] sync failed",err)}
  finally{aiccV4Busy=false}
}

window.addEventListener("load",()=>setTimeout(aiccV4Sync,1200));
setInterval(aiccV4Sync,3000);
document.addEventListener("visibilitychange",()=>{if(!document.hidden)aiccV4Sync()});
"""
    text += block
p.write_text(text,encoding="utf-8")
print("V4 form sync installed")
