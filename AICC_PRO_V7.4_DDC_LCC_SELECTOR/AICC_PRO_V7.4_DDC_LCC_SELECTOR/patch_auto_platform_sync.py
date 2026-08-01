from pathlib import Path

p=Path("app/static/app.js")
text=p.read_text(encoding="utf-8")
marker="/* AICC_AUTO_PLATFORM_SYNC_V3 */"

if marker not in text:
    block = r'''
/* AICC_AUTO_PLATFORM_SYNC_V3 */
const AICC_PLATFORM_IMPORT_URL = "https://smlib.kesug.com/api/aicc_import_saved_record.php";
const AICC_AUTO_SYNC_STATE_KEY = "aicc-platform-auto-sync-v3";
let aiccAutoSyncRunning = false;

function readAiccAutoSyncState() {
  try { return JSON.parse(localStorage.getItem(AICC_AUTO_SYNC_STATE_KEY) || "{}"); }
  catch (_) { return {}; }
}
function writeAiccAutoSyncState(state) {
  try { localStorage.setItem(AICC_AUTO_SYNC_STATE_KEY, JSON.stringify(state)); }
  catch (_) {}
}

async function syncSavedRecordsToPlatform({force=false}={}) {
  if (aiccAutoSyncRunning) return;
  aiccAutoSyncRunning = true;
  try {
    const source = await fetch("/api/platform/records", {cache:"no-store"});
    if (!source.ok) throw new Error(`AICC records HTTP ${source.status}`);
    const data = await source.json();
    if (!data.ok || !Array.isArray(data.items)) throw new Error("Invalid saved-record response");

    const state = readAiccAutoSyncState();
    for (const record of data.items) {
      const id = String(record.aicc_id || "");
      if (!id) continue;
      const stamp = String(record.updated_at || record.created_at || "");
      const signature = `${stamp}|${record.title || ""}|${record.isbn || ""}|${record.quality_score || 0}`;
      if (!force && state[id] === signature) continue;

      const response = await fetch(AICC_PLATFORM_IMPORT_URL, {
        method: "POST",
        mode: "cors",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(record)
      });
      let result = {};
      try { result = await response.json(); } catch (_) {}
      if (!response.ok || !result.ok) {
        throw new Error(result.detail || result.error || `Platform HTTP ${response.status}`);
      }
      state[id] = signature;
      writeAiccAutoSyncState(state);
      console.info("[AICC] Auto-synced:", record.title, result.mode);
    }
  } catch (error) {
    console.error("[AICC] Automatic platform sync failed:", error);
  } finally {
    aiccAutoSyncRunning = false;
  }
}

window.addEventListener("load", () => setTimeout(() => syncSavedRecordsToPlatform(), 1200));
setInterval(() => syncSavedRecordsToPlatform(), 4000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) syncSavedRecordsToPlatform();
});
'''
    text += block
    p.write_text(text,encoding="utf-8")
    print("Automatic platform sync installed")
else:
    print("Automatic platform sync already installed")
