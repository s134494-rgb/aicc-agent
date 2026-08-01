from pathlib import Path

p = Path("app/static/app.js")
text = p.read_text(encoding="utf-8")

marker = "/* AICC_MANUAL_SYNC_BUTTON_V6 */"

if marker not in text:
    block = r'''
/* AICC_MANUAL_SYNC_BUTTON_V6 */
const AICC_MANUAL_SYNC_IMPORT_URL = "https://smlib.kesug.com/api/aicc_import_saved_record.php";
const AICC_LAST_APPROVED_KEY = "aicc-last-approved-record-id";

function setManualSyncRecordId(recordId) {
  if (!recordId) return;
  localStorage.setItem(AICC_LAST_APPROVED_KEY, String(recordId));
  const btn = document.getElementById("manualSyncBtn");
  if (btn) {
    btn.disabled = false;
    btn.dataset.recordId = String(recordId);
  }
}

async function getManualSyncRecord(recordId) {
  const response = await fetch(`/api/records/${encodeURIComponent(recordId)}`, {
    headers: {Authorization: "Bearer aicc-demo-token"},
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`تعذر قراءة السجل: HTTP ${response.status}`);
  const data = await response.json();
  if (!data.ok || !data.item) throw new Error("تعذر قراءة بيانات السجل المحفوظ.");
  const x = data.item;
  return {
    aicc_id: x.id || recordId,
    title: x.title || "",
    subtitle: x.subtitle || "",
    author: x.author || "",
    author_type: x.author_type || "",
    isbn: x.isbn || "",
    publisher: x.publisher || "",
    publication_place: x.publication_place || "",
    publication_year: x.publication_year || "",
    edition: x.edition || "",
    language: x.language || "",
    ddc: x.ddc || "",
    lcc: x.lcc || "",
    cutter: x.cutter || "",
    classification_system: x.classification_system || "ddc",
    call_number: x.call_number || "",
    keywords: x.keywords || [],
    subjects: x.subjects || [],
    summary: x.summary || "",
    marc_json: x.marc_json || {},
    quality_score: Number(x.quality_score || 0),
    created_at: x.created_at || "",
    updated_at: x.updated_at || ""
  };
}

function submitManualSyncRecord(record) {
  return new Promise((resolve, reject) => {
    const frameName = `aicc-manual-sync-${Date.now()}-${Math.random().toString(16).slice(2)}`;

    const iframe = document.createElement("iframe");
    iframe.name = frameName;
    iframe.style.display = "none";

    const form = document.createElement("form");
    form.method = "POST";
    form.action = AICC_MANUAL_SYNC_IMPORT_URL;
    form.target = frameName;
    form.style.display = "none";

    const input = document.createElement("input");
    input.type = "hidden";
    input.name = "payload";
    input.value = JSON.stringify(record);
    form.appendChild(input);

    document.body.appendChild(iframe);
    document.body.appendChild(form);

    const timeout = setTimeout(() => {
      cleanup();
      reject(new Error("انتهت مهلة المزامنة. أعد المحاولة."));
    }, 20000);

    function cleanup() {
      clearTimeout(timeout);
      window.removeEventListener("message", onMessage);
      form.remove();
      iframe.remove();
    }

    function onMessage(event) {
      if (event.origin !== "https://smlib.kesug.com") return;
      if (!event.data || event.data.type !== "AICC_PLATFORM_IMPORT_RESULT") return;

      const result = event.data.data || {};
      if (String(result.aicc_id || "") !== String(record.aicc_id || "")) return;

      cleanup();
      if (result.ok) resolve(result);
      else reject(new Error(result.detail || result.error || "فشلت المزامنة."));
    }

    window.addEventListener("message", onMessage);
    form.submit();
  });
}

async function manualSyncCurrentApprovedRecord() {
  const btn = document.getElementById("manualSyncBtn");
  const recordId = (btn && btn.dataset.recordId) || localStorage.getItem(AICC_LAST_APPROVED_KEY) || "";

  if (!recordId) {
    setMessage("اعتمد السجل أولًا، ثم اضغط «المزامنة».", "error");
    return;
  }

  const oldText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "جارٍ المزامنة...";

  try {
    const record = await getManualSyncRecord(recordId);
    if (!record.title) throw new Error("السجل المحفوظ لا يحتوي على عنوان.");

    const result = await submitManualSyncRecord(record);
    btn.textContent = "تمت المزامنة ✓";
    setMessage(`تمت المزامنة بنجاح. أضيف الكتاب إلى المنصة برقم ${result.book_id}.`, "success");

    setTimeout(() => {
      btn.textContent = oldText;
      btn.disabled = false;
    }, 2500);
  } catch (error) {
    btn.textContent = oldText;
    btn.disabled = false;
    setMessage(`فشلت المزامنة: ${error.message}`, "error");
  }
}

function installManualSyncButton() {
  if (!approveBtn || document.getElementById("manualSyncBtn")) return;

  const btn = document.createElement("button");
  btn.type = "button";
  btn.id = "manualSyncBtn";
  btn.className = approveBtn.className;
  btn.textContent = "المزامنة";
  btn.title = "إرسال السجل المحفوظ يدويًا إلى كتب المنصة";

  const savedId = localStorage.getItem(AICC_LAST_APPROVED_KEY) || "";
  btn.dataset.recordId = savedId;
  btn.disabled = !savedId;

  btn.addEventListener("click", manualSyncCurrentApprovedRecord);
  approveBtn.insertAdjacentElement("afterend", btn);
}

window.addEventListener("load", installManualSyncButton);
setTimeout(installManualSyncButton, 300);
'''
    text += block

if "setManualSyncRecordId(data.record_id);" not in text:
    needle = '''      approveBtn.textContent = "تم الاعتماد ✓";
      refreshStats();
'''
    replacement = '''      approveBtn.textContent = "تم الاعتماد ✓";
      refreshStats();
      setManualSyncRecordId(data.record_id);
'''
    if needle not in text:
        raise SystemExit("Could not find approval success block")
    text = text.replace(needle, replacement, 1)

p.write_text(text, encoding="utf-8")
print("Manual Sync button V6 installed.")
