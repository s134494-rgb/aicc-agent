"use strict";

const byId = (id) => document.getElementById(id);

/* ============================================================
   الوضع الليلي / النهاري
   ============================================================ */
const themeToggle = byId("themeToggle");
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  if (themeToggle) themeToggle.textContent = theme === "dark" ? "☀️" : "🌙";
  localStorage.setItem("aicc-theme", theme);
}
applyTheme(localStorage.getItem("aicc-theme") || "light");
if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    applyTheme(current === "dark" ? "light" : "dark");
  });
}

/* ============================================================
   عناصر الرفع والتحليل (كما في النسخة الأصلية، مع تحسينات)
   ============================================================ */
const form = byId("uploadForm");
const input = byId("files");
const previews = byId("previews");
const count = byId("count");
const clearBtn = byId("clearBtn");
const analyzeBtn = byId("analyzeBtn");
const progress = byId("progress");
const message = byId("message");
const result = byId("result");
const pagesSection = byId("pagesSection");
const pagesContainer = byId("pages");
const agentsSection = byId("agentsSection");
const agentsContainer = byId("agents");
const subjectSection = byId("subjectSection");
const catalogSection = byId("catalogSection");
const professionalSection = byId("professionalSection");
const marcSection = byId("marcSection");
const duplicateBanner = byId("duplicateBanner");
const reviewSection = byId("reviewSection");
const approveBtn = byId("approveBtn");
const saveDraftBtn = byId("saveDraftBtn");
const uploadModeBtn = byId("uploadModeBtn");
const cameraModeBtn = byId("cameraModeBtn");
const uploadModePanel = byId("uploadModePanel");
const cameraModePanel = byId("cameraModePanel");
const cameraVideo = byId("cameraVideo");
const cameraCanvas = byId("cameraCanvas");
const cameraSnapshot = byId("cameraSnapshot");
const cameraEmptyState = byId("cameraEmptyState");
const cameraError = byId("cameraError");
const startCameraBtn = byId("startCameraBtn");
const captureBtn = byId("captureBtn");
const acceptCaptureBtn = byId("acceptCaptureBtn");
const retakeBtn = byId("retakeBtn");
const skipStepBtn = byId("skipStepBtn");
const switchCameraBtn = byId("switchCameraBtn");
const finishCameraBtn = byId("finishCameraBtn");
const classificationSystemInput = byId("classificationSystem");
const classificationChoiceBadge = byId("classificationChoiceBadge");

let selectedFiles = [];
let lastBookContext = {}; // يُستخدم كسياق لمساعد المحادثة
let activeSessionId = "";
let cameraStream = null;
let cameraFacingMode = "environment";
let cameraStepIndex = 0;
let pendingCapture = null;
let selectedClassificationSystem = classificationSystemInput?.value || "ddc";

const CAMERA_STEPS = [
  {key:"front-cover", icon:"📕", title:"صوّر الغلاف الأمامي", help:"ضع الغلاف كاملًا داخل الإطار، واجعل العنوان واضحًا وتجنب انعكاس الإضاءة.", required:true},
  {key:"title-page", icon:"📄", title:"صوّر صفحة العنوان", help:"افتح صفحة العنوان الداخلية بحيث يظهر العنوان واسم المؤلف وبيان المسؤولية.", required:true},
  {key:"copyright", icon:"©️", title:"صوّر صفحة حقوق النشر", help:"صوّر الصفحة التي تتضمن الناشر والطبعة والسنة ومكان النشر وحقوق الطبع.", required:true},
  {key:"isbn", icon:"▥", title:"صوّر ISBN والباركود", help:"قرّب الكاميرا من رقم ISBN والباركود مع الحفاظ على وضوح الرقم كاملًا.", required:true},
  {key:"contents", icon:"📑", title:"صوّر صفحة الفهرس", help:"صوّر صفحة أو أكثر من المحتويات لمساعدة الوكيل في فهم موضوع الكتاب.", required:false},
  {key:"introduction", icon:"📝", title:"صوّر المقدمة", help:"صوّر الصفحة الأولى من المقدمة أو التمهيد لتحسين الملخص والتحليل الموضوعي.", required:false},
  {key:"back-cover", icon:"📘", title:"صوّر الغلاف الخلفي", help:"صوّر وصف الكتاب وأي معلومات عن المؤلف أو الناشر على الغلاف الخلفي.", required:false},
  {key:"spine", icon:"📚", title:"صوّر كعب الكتاب", help:"اجعل عنوان الكتاب واسم المؤلف على الكعب واضحين داخل الإطار.", required:false}
];

function setHidden(element, hidden) {
  if (!element) return;
  element.classList.toggle("hidden", hidden);
}

function setMessage(text, type) {
  if (!message) return;
  message.textContent = text;
  message.className = `message ${type}`;
}

function setClassificationSystem(system) {
  selectedClassificationSystem = system === "lcc" ? "lcc" : "ddc";
  if (classificationSystemInput) classificationSystemInput.value = selectedClassificationSystem;
  document.querySelectorAll(".classification-option").forEach(button => {
    const active = button.dataset.system === selectedClassificationSystem;
    button.classList.toggle("active", active);
    button.setAttribute("aria-checked", String(active));
  });
  const arabicName = selectedClassificationSystem === "lcc"
    ? "مكتبة الكونجرس LCC" : "ديوي DDC";
  if (classificationChoiceBadge) classificationChoiceBadge.textContent = `المحدد: ${arabicName}`;
}

document.querySelectorAll(".classification-option").forEach(button => {
  button.addEventListener("click", () => setClassificationSystem(button.dataset.system));
});
setClassificationSystem(selectedClassificationSystem);

function renderPreviews() {
  if (!previews || !count) return;
  previews.innerHTML = "";
  count.textContent = `${selectedFiles.length} صورة`;

  selectedFiles.forEach((file, index) => {
    const card = document.createElement("div");
    card.className = "preview-card";

    const image = document.createElement("img");
    image.src = URL.createObjectURL(file);
    image.alt = file.name;

    const name = document.createElement("small");
    name.textContent = file.name;

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove";
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      selectedFiles.splice(index, 1);
      renderPreviews();
    });

    card.append(remove, image, name);
    previews.appendChild(card);
  });
}

if (input) {
  input.addEventListener("change", () => {
    const incoming = Array.from(input.files || [])
      .filter(file => file.type.startsWith("image/"));
    selectedFiles = [...selectedFiles, ...incoming].slice(0, 20);
    input.value = "";
    renderPreviews();
  });
}

function updateCameraStep() {
  const step = CAMERA_STEPS[cameraStepIndex];
  if (!step) {
    byId("cameraStepCounter").textContent = "اكتملت خطوات التصوير";
    byId("cameraStepTitle").textContent = "تم تصوير صفحات الكتاب";
    byId("cameraStepHelp").textContent = "راجع الصور المصغرة، ثم ابدأ التحليل الذكي.";
    byId("cameraStepIcon").textContent = "✅";
    setHidden(byId("cameraStepRequired"), true);
    setHidden(captureBtn, true); setHidden(skipStepBtn, true);
    setHidden(finishCameraBtn, false);
    stopCamera();
    return;
  }
  byId("cameraStepCounter").textContent = `الخطوة ${cameraStepIndex + 1} من ${CAMERA_STEPS.length}`;
  byId("cameraStepTitle").textContent = step.title;
  byId("cameraStepHelp").textContent = step.help;
  byId("cameraStepIcon").textContent = step.icon;
  byId("cameraStepRequired").textContent = step.required ? "مطلوب" : "اختياري";
  byId("cameraStepRequired").classList.toggle("optional", !step.required);
  byId("cameraCapturedCount").textContent = `تم التقاط ${selectedFiles.filter(f => f.name.startsWith("camera-")).length} صور`;
  byId("cameraProgressFill").style.width = `${(cameraStepIndex / CAMERA_STEPS.length) * 100}%`;
  setHidden(skipStepBtn, step.required);
  if (!cameraStream) {
    setHidden(startCameraBtn, false); setHidden(captureBtn, true);
    setHidden(switchCameraBtn, true); setHidden(cameraEmptyState, false);
  }
}

function stopCamera() {
  if (cameraStream) cameraStream.getTracks().forEach(track => track.stop());
  cameraStream = null;
  if (cameraVideo) cameraVideo.srcObject = null;
}

async function startCamera() {
  setHidden(cameraError, true);
  if (!navigator.mediaDevices?.getUserMedia) {
    cameraError.textContent = "هذا المتصفح لا يدعم تشغيل الكاميرا. استخدم Chrome أو Edge وحدّث المتصفح.";
    return setHidden(cameraError, false);
  }
  stopCamera();
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: {facingMode:{ideal:cameraFacingMode}, width:{ideal:1920}, height:{ideal:1080}},
      audio:false
    });
    cameraVideo.srcObject = cameraStream;
    await cameraVideo.play();
    setHidden(cameraEmptyState, true); setHidden(cameraVideo, false);
    setHidden(startCameraBtn, true); setHidden(captureBtn, false);
    setHidden(switchCameraBtn, false);
    updateCameraStep();
  } catch (error) {
    const messages = {
      NotAllowedError:"تم رفض إذن الكاميرا. اسمح للموقع باستخدام الكاميرا من رمز القفل بجانب العنوان ثم أعد المحاولة.",
      NotFoundError:"لم يعثر النظام على كاميرا متصلة بالجهاز.",
      NotReadableError:"الكاميرا مستخدمة في برنامج آخر. أغلق البرنامج الآخر ثم أعد المحاولة."
    };
    cameraError.textContent = messages[error.name] || `تعذر تشغيل الكاميرا: ${error.message}`;
    setHidden(cameraError, false);
  }
}

function showLiveCamera() {
  pendingCapture = null;
  if (cameraSnapshot.src) URL.revokeObjectURL(cameraSnapshot.src);
  cameraSnapshot.removeAttribute("src");
  setHidden(cameraSnapshot, true); setHidden(cameraVideo, false);
  setHidden(acceptCaptureBtn, true); setHidden(retakeBtn, true);
  setHidden(captureBtn, false); setHidden(switchCameraBtn, false);
  updateCameraStep();
}

async function takePhoto() {
  if (!cameraStream || !cameraVideo.videoWidth) return;
  cameraCanvas.width = cameraVideo.videoWidth;
  cameraCanvas.height = cameraVideo.videoHeight;
  const ctx = cameraCanvas.getContext("2d");
  ctx.drawImage(cameraVideo, 0, 0, cameraCanvas.width, cameraCanvas.height);
  pendingCapture = await new Promise(resolve => cameraCanvas.toBlob(resolve, "image/jpeg", 0.94));
  if (!pendingCapture) return;
  cameraSnapshot.src = URL.createObjectURL(pendingCapture);
  setHidden(cameraVideo, true); setHidden(cameraSnapshot, false);
  setHidden(captureBtn, true); setHidden(switchCameraBtn, true);
  setHidden(acceptCaptureBtn, false); setHidden(retakeBtn, false); setHidden(skipStepBtn, true);
}

function acceptPhoto() {
  if (!pendingCapture) return;
  const step = CAMERA_STEPS[cameraStepIndex];
  const filename = `camera-${String(cameraStepIndex + 1).padStart(2,"0")}-${step.key}.jpg`;
  selectedFiles.push(new File([pendingCapture], filename, {type:"image/jpeg", lastModified:Date.now()}));
  selectedFiles = selectedFiles.slice(0, 20);
  renderPreviews();
  cameraStepIndex += 1;
  showLiveCamera();
}

function skipCameraStep() {
  if (CAMERA_STEPS[cameraStepIndex]?.required) return;
  cameraStepIndex += 1;
  updateCameraStep();
}

function setInputMode(mode) {
  const camera = mode === "camera";
  uploadModeBtn.classList.toggle("active", !camera);
  cameraModeBtn.classList.toggle("active", camera);
  uploadModeBtn.setAttribute("aria-selected", String(!camera));
  cameraModeBtn.setAttribute("aria-selected", String(camera));
  setHidden(uploadModePanel, camera); setHidden(cameraModePanel, !camera);
  if (!camera) stopCamera();
  else updateCameraStep();
}

if (uploadModeBtn) uploadModeBtn.addEventListener("click", () => setInputMode("upload"));
if (cameraModeBtn) cameraModeBtn.addEventListener("click", () => setInputMode("camera"));
if (startCameraBtn) startCameraBtn.addEventListener("click", startCamera);
if (captureBtn) captureBtn.addEventListener("click", takePhoto);
if (acceptCaptureBtn) acceptCaptureBtn.addEventListener("click", acceptPhoto);
if (retakeBtn) retakeBtn.addEventListener("click", showLiveCamera);
if (skipStepBtn) skipStepBtn.addEventListener("click", skipCameraStep);
if (switchCameraBtn) switchCameraBtn.addEventListener("click", async () => {
  cameraFacingMode = cameraFacingMode === "environment" ? "user" : "environment";
  await startCamera();
});
if (finishCameraBtn) finishCameraBtn.addEventListener("click", () => {
  stopCamera(); setInputMode("upload");
  setMessage(`تم تجهيز ${selectedFiles.length} صورة. اضغط «إنشاء مسودة التحليل» للمتابعة.`, "success");
  previews?.scrollIntoView({behavior:"smooth", block:"center"});
});
window.addEventListener("beforeunload", stopCamera);

function hideAllResults() {
  [result, pagesSection, agentsSection, subjectSection, catalogSection, professionalSection, marcSection, reviewSection]
    .forEach(section => setHidden(section, true));
  setHidden(duplicateBanner, true);
}

if (clearBtn) {
  clearBtn.addEventListener("click", () => {
    selectedFiles = [];
    cameraStepIndex = 0;
    pendingCapture = null;
    renderPreviews();
    updateCameraStep();
    hideAllResults();
    if (message) message.className = "message hidden";
  });
}

async function checkHealth() {
  const status = byId("status");
  try {
    const response = await fetch("/api/health", {cache: "no-store"});
    const data = await response.json();
    if (status) status.textContent = data.ok ? `النظام جاهز · v${data.version}` : "الخادم غير جاهز";
  } catch (error) {
    if (status) status.textContent = "تعذر الاتصال بالخادم";
  }
}

function setValue(id, value) {
  const el = byId(id);
  if (el) el.value = value ?? "";
}

function scoreClass(value) {
  if (value >= 80) return "score-high";
  if (value >= 50) return "score-mid";
  return "score-low";
}

function fillResults(book) {
  const verification = byId("sourceVerification");
  const match = book.external_match || {};
  if (verification) {
    if (match.status) {
      const exact = match.method === "exact_isbn";
      const filled = (match.filled_fields || []).join("، ") || "لا توجد حقول ناقصة";
      const preserved = (match.preserved_fields || []).join("، ");
      verification.className = `source-verification ${exact ? "verified" : "candidate"}`;
      verification.textContent =
        `${exact ? "✅ تطابق ISBN مؤكد" : "🔎 تطابق قوي من مصدرين"} — ` +
        `المصادر: ${(match.sources || []).join(" + ") || "غير محددة"}. ` +
        `تم إكمال: ${filled}.` +
        (preserved ? ` حُفظت قيم الصور ولم تستبدل: ${preserved}.` : "");
      (match.source_links || []).forEach(source => {
        if (!/^https?:\/\//i.test(source.url || "")) return;
        const link = document.createElement("a");
        link.href = source.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = `↗ ${source.title || "فتح المصدر"}`;
        verification.append(document.createTextNode(" "), link);
      });
    } else {
      verification.className = "source-verification unverified";
      verification.textContent =
        "⚠️ لم يُثبت تطابق خارجي؛ البيانات المعروضة مستخرجة من الصور وتحتاج مراجعة.";
    }
  }
  setValue("title", book.title || "");
  setValue("subtitle", book.subtitle || "");
  setValue("author", book.author || "");
  setValue("authorType", book.author_type || "personal");
  setValue("responsibility", book.statement_of_responsibility || "");
  setValue("translator", book.translator || "");
  setValue("editor", book.editor || "");
  setValue("isbn", book.isbn || "");
  setValue("issn", book.issn || "");
  setValue("publisher", book.publisher || "");
  setValue("publicationPlace", book.publication_place || "");
  setValue("year", book.publication_year || "");
  setValue("copyrightDate", book.copyright_date || "");
  setValue("edition", book.edition || "");
  setValue("language", book.language || "");
  setValue("originalLanguage", book.original_language || "");
  setValue("pagesCount", book.pages || "");
  setValue("illustrations", book.illustrations || "");
  setValue("dimensions", book.dimensions || "");
  setValue("series", book.series || "");
  setValue("seriesNumber", book.series_number || "");
  setValue("targetAudience", book.target_audience || "");
  setValue("resourceType", book.resource_type || "");
  setValue("contentType", book.content_type || "");
  setValue("mediaType", book.media_type || "");
  setValue("carrierType", book.carrier_type || "");
  setValue("bibliographyNote", book.bibliography_note || "");
  setValue("indexNote", book.index_note || "");
  setValue("generalNotes", book.general_notes || "");
  setValue("isbnCandidates", (book.isbn_candidates || []).map(x =>
    `${x.normalized} — ${x.valid ? "صالح" : "غير صالح"}`).join("\n"));

  Object.entries(book.confidence || {}).forEach(([key, value]) => {
    const el = byId(`score-${key}`);
    if (el) {
      el.textContent = `${value}%`;
      el.classList.remove("score-high", "score-mid", "score-low");
      el.classList.add(scoreClass(value));
    }
  });

  if (duplicateBanner) {
    if (book.duplicate_of) {
      duplicateBanner.textContent =
        `⚠️ تنبيه تكرار: يبدو أن هذا الكتاب مفهرس مسبقًا (سجل رقم ${book.duplicate_of.id} — «${book.duplicate_of.title || "بدون عنوان"}» بتاريخ ${book.duplicate_of.created_at}).`;
      setHidden(duplicateBanner, false);
    } else {
      setHidden(duplicateBanner, true);
    }
  }
}

function fillPages(pages) {
  if (!pagesContainer) return;
  pagesContainer.innerHTML = "";
  (pages || []).forEach(page => {
    const box = document.createElement("article");
    box.className = "page-box";

    const head = document.createElement("div");
    head.className = "page-head";

    const title = document.createElement("strong");
    title.textContent = `الصورة ${page.index}: ${page.filename}`;

    const type = document.createElement("span");
    type.textContent = page.page_type || "غير محدد";

    const text = document.createElement("textarea");
    text.rows = 8;
    text.readOnly = true;
    text.value = page.text || "";

    head.append(title, type);
    box.append(head, text);
    pagesContainer.appendChild(box);
  });
}

function spineLabelData(book = {}, cataloging = {}) {
  const ddc = String(cataloging.ddc || "").trim();
  const lcc = String(cataloging.lcc || "").trim();
  const system = cataloging.classification_system === "lcc" ? "lcc" : "ddc";
  const classification = system === "lcc" ? lcc : ddc;
  return {
    classification,
    cutter: String(cataloging.cutter || "").trim(),
    year: String(book.publication_year || "").trim(),
    copy: Math.max(1, Number.parseInt(byId("spineCopyNumber")?.value || "1", 10) || 1),
    title: String(book.title || "").trim(),
    author: String(book.author || "").trim(),
    callNumber: String(cataloging.call_number || "").trim()
  };
}

function renderSpineLabel(book = {}, cataloging = {}) {
  window.__spineLabelBook = {...book};
  window.__spineLabelCataloging = {...cataloging};
  const label = spineLabelData(book, cataloging);
  byId("spineClassNumber").textContent = label.classification || "—";
  byId("spineCutter").textContent = label.cutter || "—";
  byId("spineYear").textContent = label.year || "—";
  byId("spineCopy").textContent = `ن${label.copy}`;
  byId("spineBookTitle").textContent = label.title || "—";
  byId("spineBookAuthor").textContent = label.author || "—";
  byId("spineFullCallNumber").textContent = label.callNumber ||
    [label.classification, label.cutter, label.year].filter(Boolean).join(" ") || "—";
  const warning = byId("spineLabelWarning");
  const button = byId("printSpineLabelBtn");
  const missing = [];
  if (!label.classification) missing.push("رقم التصنيف");
  if (!label.cutter) missing.push("رمز المؤلف");
  if (warning) {
    warning.textContent = missing.length
      ? `أكمل ${missing.join(" و")} قبل الطباعة.`
      : "";
    setHidden(warning, !missing.length);
  }
  if (button) button.disabled = Boolean(missing.length);
}

if (form) {
  form.addEventListener("submit", async event => {
    event.preventDefault();

    if (selectedFiles.length === 0) {
      setMessage("اختر صورة واحدة على الأقل.", "error");
      return;
    }

    analyzeBtn.disabled = true;
    clearBtn.disabled = true;
    analyzeBtn.textContent = "جارٍ التحليل...";
    setHidden(progress, false);
    if (message) message.className = "message hidden";
    hideAllResults();

      const body = new FormData();
      selectedFiles.forEach(file => body.append("files", file, file.name));
      body.append("classification_system", selectedClassificationSystem);
    const controller = new AbortController();
    const requestTimeout = window.setTimeout(() => controller.abort(), 180000);

    try {
      const response = await fetch("/api/analyze", {
        method: "POST", body, signal: controller.signal
      });
      const raw = await response.text();
      let data;
      try {
        data = JSON.parse(raw);
      } catch {
        throw new Error(`استجابة غير مفهومة من الخادم: ${raw.slice(0, 250)}`);
      }

      if (!response.ok || !data.ok) {
        throw new Error(data.error || `فشل التحليل برمز ${response.status}`);
      }

      fillResults(data.book || {});
      activeSessionId = data.session_id || "";
      fillPages(data.pages || []);

      if (agentsContainer) {
        agentsContainer.innerHTML = "";
        (data.agent_runs || []).forEach(run => {
          const row = document.createElement("div");
          row.className = "agent-row";
          row.innerHTML = `<strong>${run.agent || "Agent"}</strong><span>✔ ${run.status || ""}</span><small>${run.ms || 0} ms</small>`;
          agentsContainer.appendChild(row);
        });
      }

      setValue("keywords", (data.subject?.keywords || []).join("، "));
      setValue("summary", data.subject?.summary_draft || "");
      setValue("ddc", data.cataloging?.ddc || "");
      setValue("lcc", data.cataloging?.lcc || "");
      setValue("cutter", data.cataloging?.cutter || "");
      setValue("callNumber", data.cataloging?.call_number || "");
      selectedClassificationSystem = data.cataloging?.classification_system || selectedClassificationSystem;
      setClassificationSystem(selectedClassificationSystem);
      if (byId("selectedClassificationSystem")) {
        byId("selectedClassificationSystem").textContent = selectedClassificationSystem === "lcc"
          ? "تصنيف مكتبة الكونجرس LCC" : "تصنيف ديوي DDC";
      }
      renderSpineLabel(data.book || {}, data.cataloging || {});
      setValue("catalogConfidence", `${data.cataloging?.confidence || 0}%`);
      setValue("catalogReason", data.cataloging?.reason || "");
      setValue("subjects", (data.cataloging?.subject_headings || []).join("\n"));
      const professional = data.professional_cataloging || {};
      const validation = professional.validation || {};
      setValue("catalogStandard", professional.standard || "");
      setValue("mainAccessPoint", professional.main_access_point?.authorized_form || "");
      setValue("mainAccessType", professional.main_access_point?.type || "");
      setValue("professionalDecision", professional.status || "");
      setValue("rdaElements", JSON.stringify(professional.rda_elements || {}, null, 2));
      setValue("classificationAlternatives",
        (professional.classification_decision?.alternatives || [])
          .map(x => `${x.ddc || "—"} | ${x.lcc || "—"} — ${x.reason || ""}`).join("\n"));
      const checklist = [
        ...(validation.errors || []).map(x => `❌ ${x.field}: ${x.message}`),
        ...(validation.warnings || []).map(x => `⚠️ ${x.field}: ${x.message}`),
        ...(validation.capture_tasks || []).map(x => `📷 ${x.instruction}`)
      ];
      setValue("catalogChecklist", checklist.join("\n") || "✅ لم يكتشف الوكيل نقصًا وصفيًا حرجًا.");
      if (byId("professionalStatus")) byId("professionalStatus").textContent =
        professional.status || "قيد المراجعة";
      setValue("marcJson", JSON.stringify(data.marc || {}, null, 2));
      setValue("marcXml", data.marcxml || "");

      // تحديث سياق مساعد المحادثة بأحدث كتاب تمت فهرسته
      lastBookContext = {
        title: data.book?.title || "",
        subtitle: data.book?.subtitle || "",
        author: data.book?.author || "",
        author_type: data.book?.author_type || "personal",
        isbn: data.book?.isbn || "",
        publisher: data.book?.publisher || "",
        publication_year: data.book?.publication_year || "",
        ddc: data.cataloging?.ddc || "",
        lcc: data.cataloging?.lcc || "",
        call_number: data.cataloging?.call_number || "",
      };

      window.__lastMarcXml = data.marcxml || "";
      window.__lastBookJson = {book: data.book, cataloging: data.cataloging, subject: data.subject, marc: data.marc};

      const qrBox = byId("qrBox");
      const qrImage = byId("qrImage");
      if (qrBox && qrImage) {
        if (data.qr_label) {
          qrImage.src = data.qr_label;
          setHidden(qrBox, false);
        } else {
          setHidden(qrBox, true);
        }
      }

      const qualityBox = byId("qualityBox");
      if (qualityBox) {
        const critical = data.quality?.critical_errors || [];
        const warnings = data.quality?.warnings || [];
        qualityBox.className = `message ${critical.length ? "error" : "success"}`;
        qualityBox.textContent = `درجة الجودة: ${data.quality?.score || 0}% | أخطاء حرجة: ${critical.join("، ") || "لا يوجد"} | تحذيرات: ${warnings.join("، ") || "لا يوجد"}`;
      }
      [result, pagesSection, agentsSection, subjectSection, catalogSection, professionalSection, marcSection, reviewSection]
        .forEach(section => setHidden(section, false));

      setMessage("اكتمل التحليل وأنشئت مسودة. راجعها ثم اضغط اعتماد السجل.", "success");
      if (result) result.scrollIntoView({behavior: "smooth", block: "start"});

      refreshStats();
    } catch (error) {
      console.error("AICC analysis error:", error);
      setMessage(error.name === "AbortError"
        ? "توقف التحليل بعد 3 دقائق. تحقق من تثبيت لغة العربية ara في Tesseract ثم حاول بعدد صور أقل."
        : (error.message || "حدث خطأ غير معروف."), "error");
    } finally {
      window.clearTimeout(requestTimeout);
      analyzeBtn.disabled = false;
      clearBtn.disabled = false;
      analyzeBtn.textContent = "✨ إنشاء مسودة التحليل";
      setHidden(progress, true);
    }
  });
}

function fieldValue(id) { return byId(id)?.value?.trim() || ""; }
function collectDraft() {
  return {
    book: {
      title: fieldValue("title"), subtitle: fieldValue("subtitle"),
      author: fieldValue("author"), author_type: fieldValue("authorType"),
      statement_of_responsibility: fieldValue("responsibility"),
      translator: fieldValue("translator"), editor: fieldValue("editor"),
      isbn: fieldValue("isbn"), issn: fieldValue("issn"), publisher: fieldValue("publisher"),
      publication_place: fieldValue("publicationPlace"), publication_year: fieldValue("year"),
      copyright_date: fieldValue("copyrightDate"), edition: fieldValue("edition"),
      language: fieldValue("language"), original_language: fieldValue("originalLanguage"),
      pages: fieldValue("pagesCount"), illustrations: fieldValue("illustrations"),
      dimensions: fieldValue("dimensions"), series: fieldValue("series"),
      series_number: fieldValue("seriesNumber"), target_audience: fieldValue("targetAudience"),
      resource_type: fieldValue("resourceType"), content_type: fieldValue("contentType"),
      media_type: fieldValue("mediaType"), carrier_type: fieldValue("carrierType"),
      bibliography_note: fieldValue("bibliographyNote"), index_note: fieldValue("indexNote"),
      general_notes: fieldValue("generalNotes")
    },
    subject: {keywords: fieldValue("keywords").split(/[،,]/).map(x => x.trim()).filter(Boolean),
      summary_draft: fieldValue("summary")},
    cataloging: {ddc: fieldValue("ddc"), lcc: fieldValue("lcc"),
      cutter: fieldValue("cutter"), call_number: fieldValue("callNumber"),
      classification_system: selectedClassificationSystem,
      subject_headings: fieldValue("subjects").split("\n").map(x => x.trim()).filter(Boolean)}
  };
}

function renderQuality(quality) {
  const qualityBox = byId("qualityBox");
  if (!qualityBox) return;
  const critical = quality?.critical_errors || [];
  const warnings = quality?.warnings || [];
  qualityBox.className = `message ${critical.length ? "error" : "success"}`;
  qualityBox.textContent = `درجة الجودة: ${quality?.score || 0}% | أخطاء حرجة: ${critical.join("، ") || "لا يوجد"} | تحذيرات: ${warnings.join("، ") || "لا يوجد"}`;
}

async function saveActiveDraft(showNotice = true) {
  if (!activeSessionId) throw new Error("لا توجد مسودة نشطة.");
  const response = await fetch(`/api/analysis/${activeSessionId}/fields`, {
    method: "PATCH",
    headers: {"Content-Type": "application/json", Authorization: "Bearer aicc-demo-token"},
    body: JSON.stringify(collectDraft())
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "تعذر حفظ التعديلات");
  const d = data.draft;
  setValue("ddc", d.cataloging?.ddc || "");
  setValue("lcc", d.cataloging?.lcc || "");
  setValue("cutter", d.cataloging?.cutter || "");
  setValue("callNumber", d.cataloging?.call_number || "");
  selectedClassificationSystem = d.cataloging?.classification_system || selectedClassificationSystem;
  setClassificationSystem(selectedClassificationSystem);
  if (byId("selectedClassificationSystem")) {
    byId("selectedClassificationSystem").textContent = selectedClassificationSystem === "lcc"
      ? "تصنيف مكتبة الكونجرس LCC" : "تصنيف ديوي DDC";
  }
  renderSpineLabel(d.book || window.__spineLabelBook || {}, d.cataloging || {});
  setValue("marcJson", JSON.stringify(d.marc || {}, null, 2));
  setValue("marcXml", d.marcxml || "");
  window.__lastMarcXml = d.marcxml || "";
  renderQuality(d.quality || {});
  if (showNotice) setMessage(data.notice, "success");
  return d;
}

if (saveDraftBtn) saveDraftBtn.addEventListener("click", async () => {
  saveDraftBtn.disabled = true;
  try { await saveActiveDraft(true); }
  catch (error) { setMessage(error.message, "error"); }
  finally { saveDraftBtn.disabled = false; }
});

if (approveBtn) {
  approveBtn.addEventListener("click", async () => {
    if (!activeSessionId) return setMessage("لا توجد مسودة نشطة للاعتماد.", "error");
    approveBtn.disabled = true;
    try {
      await saveActiveDraft(false);
      const response = await fetch(`/api/analysis/${activeSessionId}/approve`, {
        method: "POST",
        headers: {Authorization: "Bearer aicc-demo-token"}
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "تعذر اعتماد السجل");
      setMessage(`تم اعتماد السجل وحفظه. رقم السجل: ${data.record_id}`, "success");
      approveBtn.textContent = "تم الاعتماد ✓";
      refreshStats();
    } catch (error) {
      setMessage(error.message, "error");
      const qualityBox = byId("qualityBox");
      if (qualityBox) {
        qualityBox.className = "message error";
        qualityBox.textContent = `لم يتم الاعتماد: ${error.message}`;
        qualityBox.scrollIntoView({behavior:"smooth",block:"center"});
      }
      approveBtn.disabled = false;
    }
  });
}

/* ============================================================
   أزرار التصدير: طباعة / تنزيل JSON / تنزيل MARCXML
   ============================================================ */
function downloadBlob(filename, content, mime) {
  const blob = new Blob([content], {type: mime});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const printBtn = byId("printBtn");
if (printBtn) printBtn.addEventListener("click", () => window.print());

["spineCopyNumber", "spineLabelSize"].forEach(id => {
  byId(id)?.addEventListener("input", () =>
    renderSpineLabel(window.__spineLabelBook || {}, window.__spineLabelCataloging || {}));
});
["ddc", "lcc", "cutter", "callNumber", "year", "title", "author"].forEach(id => {
  byId(id)?.addEventListener("input", () => {
    const book = {
      ...(window.__spineLabelBook || {}),
      title: fieldValue("title"), author: fieldValue("author"),
      publication_year: fieldValue("year")
    };
    const cataloging = {
      ...(window.__spineLabelCataloging || {}),
      ddc: fieldValue("ddc"), lcc: fieldValue("lcc"),
      cutter: fieldValue("cutter"), call_number: fieldValue("callNumber")
    };
    renderSpineLabel(book, cataloging);
  });
});

function escapePrintText(value) {
  return String(value || "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  })[char]);
}

byId("printSpineLabelBtn")?.addEventListener("click", () => {
  const label = spineLabelData(
    window.__spineLabelBook || {},
    window.__spineLabelCataloging || {}
  );
  if (!label.classification || !label.cutter) {
    return setMessage("أكمل رقم التصنيف ورمز المؤلف قبل طباعة الملصق.", "error");
  }
  const selected = byId("spineLabelSize")?.value || "30x40";
  const [width, height] = selected.split("x").map(Number);
  const popup = window.open("", "_blank", "width=520,height=650");
  if (!popup) return setMessage("اسمح بالنوافذ المنبثقة حتى تتم طباعة ملصق الكعب.", "error");
  const lines = [
    label.classification, label.cutter, label.year, `ن${label.copy}`
  ].filter(Boolean).map(value => `<div>${escapePrintText(value)}</div>`).join("");
  popup.document.open();
  popup.document.write(`<!doctype html><html lang="ar" dir="rtl"><head>
    <meta charset="utf-8"><title>ملصق كعب الكتاب</title>
    <style>
      @page{size:${width}mm ${height}mm;margin:0}
      *{box-sizing:border-box}
      html,body{width:${width}mm;height:${height}mm;margin:0;padding:0;background:#fff}
      body{display:flex;align-items:center;justify-content:center;color:#000}
      .label{width:${width}mm;height:${height}mm;border:.35mm solid #000;
        display:flex;flex-direction:column;align-items:center;justify-content:center;
        padding:2mm 1mm;text-align:center;font-family:Arial,"Times New Roman",sans-serif;
        font-size:${width <= 25 ? 11 : 13}pt;font-weight:700;line-height:1.25;
        direction:ltr;overflow:hidden}
      .label div{max-width:100%;overflow-wrap:anywhere}
      @media print{.label{border:.35mm solid #000}}
    </style></head><body><div class="label">${lines}</div>
    <script>window.onload=()=>{window.print();window.onafterprint=()=>window.close()}<\/script>
    </body></html>`);
  popup.document.close();
});

const downloadJsonBtn = byId("downloadJsonBtn");
if (downloadJsonBtn) {
  downloadJsonBtn.addEventListener("click", () => {
    if (!window.__lastBookJson) return;
    downloadBlob("aicc-record.json", JSON.stringify(window.__lastBookJson, null, 2), "application/json");
  });
}

const downloadMarcBtn = byId("downloadMarcBtn");
if (downloadMarcBtn) {
  downloadMarcBtn.addEventListener("click", () => {
    if (!window.__lastMarcXml) return;
    downloadBlob("aicc-record.marc.xml", window.__lastMarcXml, "application/xml");
  });
}

/* ============================================================
   إدارة السجلات المحفوظة: تعديل بإصدارات + حذف آمن
   ============================================================ */
const savedRecordsBody = byId("savedRecordsBody");
const recordEditDialog = byId("recordEditDialog");
const recordEditForm = byId("recordEditForm");
const recordEditMessage = byId("recordEditMessage");

function recordCell(value) {
  const td = document.createElement("td");
  td.textContent = value || "—";
  return td;
}

function recordActionButton(label, className, recordId) {
  const button = document.createElement("button");
  button.type = "button"; button.className = className;
  button.dataset.recordId = recordId; button.textContent = label;
  return button;
}

async function loadSavedRecords() {
  if (!savedRecordsBody) return;
  try {
    const response = await fetch("/api/records", {
      headers:{Authorization:"Bearer aicc-demo-token"}, cache:"no-store"
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "تعذر تحميل السجلات");
    savedRecordsBody.innerHTML = "";
    const items = data.items || [];
    if (!items.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td"); cell.colSpan = 7;
      cell.textContent = "لا توجد سجلات بعد."; row.appendChild(cell);
      savedRecordsBody.appendChild(row); return;
    }
    items.forEach(item => {
      const row = document.createElement("tr"); row.dataset.recordId = item.id;
      row.append(recordCell(item.id),recordCell(item.title),recordCell(item.author),
        recordCell(item.isbn),recordCell(item.language),recordCell(item.created_at));
      const actions = document.createElement("td"); actions.className = "record-actions";
      actions.append(
        recordActionButton("✏️ تعديل","record-edit-btn",item.id),
        recordActionButton("🗑️ حذف","record-delete-btn",item.id)
      );
      row.appendChild(actions); savedRecordsBody.appendChild(row);
    });
  } catch (error) {
    savedRecordsBody.innerHTML = "";
    const row=document.createElement("tr"); const cell=document.createElement("td");
    cell.colSpan=7; cell.textContent=error.message; row.appendChild(cell);
    savedRecordsBody.appendChild(row);
  }
}

function editSet(id,value) { const el=byId(id); if(el) el.value=value ?? ""; }

async function openRecordEditor(recordId) {
  const response=await fetch(`/api/records/${recordId}`,{
    headers:{Authorization:"Bearer aicc-demo-token"},cache:"no-store"});
  const data=await response.json();
  if(!response.ok) throw new Error(data.detail || "تعذر فتح السجل");
  const x=data.item;
  editSet("editRecordId",x.id); editSet("editTitle",x.title);
  editSet("editSubtitle",x.subtitle); editSet("editAuthor",x.author);
  editSet("editAuthorType",x.author_type || "personal"); editSet("editIsbn",x.isbn);
  editSet("editPublisher",x.publisher); editSet("editPublicationPlace",x.publication_place);
  editSet("editPublicationYear",x.publication_year); editSet("editEdition",x.edition);
  editSet("editLanguage",x.language); editSet("editDdc",x.ddc); editSet("editLcc",x.lcc);
  editSet("editCutter",x.cutter); editSet("editCallNumber",x.call_number);
  editSet("editSubjects",(x.subjects || []).join("\n"));
  editSet("editKeywords",(x.keywords || []).join("، "));
  editSet("editSummary",x.summary);
  recordEditMessage.className="message hidden";
  recordEditDialog.showModal();
}

async function deleteSavedRecord(recordId) {
  if (!window.confirm("هل تريد حذف هذا السجل من الفهرس؟ يمكن تتبع العملية في سجل التدقيق.")) return;
  const response=await fetch(`/api/records/${recordId}`,{
    method:"DELETE",headers:{Authorization:"Bearer aicc-demo-token"}});
  const data=await response.json();
  if(!response.ok) throw new Error(data.detail || "تعذر حذف السجل");
  setMessage(data.message,"success");
  await loadSavedRecords(); await refreshStats();
}

if (savedRecordsBody) savedRecordsBody.addEventListener("click",async event => {
  const edit=event.target.closest(".record-edit-btn");
  const remove=event.target.closest(".record-delete-btn");
  try {
    if(edit) await openRecordEditor(edit.dataset.recordId);
    if(remove) await deleteSavedRecord(remove.dataset.recordId);
  } catch(error) { setMessage(error.message,"error"); }
});

byId("recordEditClose")?.addEventListener("click",()=>recordEditDialog.close());
byId("recordEditCancel")?.addEventListener("click",()=>recordEditDialog.close());

if (recordEditForm) recordEditForm.addEventListener("submit",async event => {
  event.preventDefault();
  const save=byId("recordEditSave"); save.disabled=true;
  recordEditMessage.className="message hidden";
  const recordId=fieldValue("editRecordId");
  const payload={
    book:{title:fieldValue("editTitle"),subtitle:fieldValue("editSubtitle"),
      author:fieldValue("editAuthor"),author_type:fieldValue("editAuthorType"),
      isbn:fieldValue("editIsbn"),publisher:fieldValue("editPublisher"),
      publication_place:fieldValue("editPublicationPlace"),
      publication_year:fieldValue("editPublicationYear"),edition:fieldValue("editEdition"),
      language:fieldValue("editLanguage")},
    cataloging:{ddc:fieldValue("editDdc"),lcc:fieldValue("editLcc"),
      cutter:fieldValue("editCutter"),call_number:fieldValue("editCallNumber"),
      subject_headings:fieldValue("editSubjects").split("\n").map(x=>x.trim()).filter(Boolean)},
    subject:{keywords:fieldValue("editKeywords").split(/[،,]/).map(x=>x.trim()).filter(Boolean),
      summary_draft:fieldValue("editSummary")}
  };
  try {
    const response=await fetch(`/api/records/${recordId}`,{
      method:"PATCH",headers:{"Content-Type":"application/json",Authorization:"Bearer aicc-demo-token"},
      body:JSON.stringify(payload)});
    const data=await response.json();
    if(!response.ok) throw new Error(data.detail || "تعذر تعديل السجل");
    recordEditDialog.close(); setMessage(data.message,"success");
    await loadSavedRecords(); await refreshStats();
  } catch(error) {
    recordEditMessage.textContent=error.message; recordEditMessage.className="message error";
  } finally { save.disabled=false; }
});

/* ============================================================
   لوحة الإحصائيات الحية (رسم بياني مخصص بدون أي مكتبة خارجية)
   ============================================================ */
function renderBars(container, rows, labelKey, valueKey) {
  if (!container) return;
  container.innerHTML = "";
  if (!rows || rows.length === 0) {
    container.innerHTML = `<p class="bar-empty">لا توجد بيانات كافية بعد.</p>`;
    return;
  }
  const max = Math.max(...rows.map(r => r[valueKey]), 1);
  rows.forEach(row => {
    const wrap = document.createElement("div");
    wrap.className = "bar-row";
    const pct = Math.round((row[valueKey] / max) * 100);
    wrap.innerHTML = `
      <span>${row[labelKey] || "—"}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${pct}%"></span></span>
      <span>${row[valueKey]}</span>`;
    container.appendChild(wrap);
  });
}

async function refreshStats() {
  try {
    const response = await fetch("/api/stats", {cache: "no-store"});
    const data = await response.json();
    if (!data.ok) return;
    const stats = data.stats;

    const statTotal = byId("statTotal");
    const statLangs = byId("statLangs");
    const statTopDdc = byId("statTopDdc");
    if (statTotal) statTotal.textContent = stats.total;
    if (statLangs) statLangs.textContent = (stats.languages || []).length;
    if (statTopDdc) statTopDdc.textContent = stats.top_ddc ? stats.top_ddc[0] : "—";

    renderBars(byId("langChart"), stats.languages, "language", "count");
    renderBars(byId("ddcChart"), stats.top_ddc_list, "ddc", "count");

    window.__lastStats = stats;
  } catch (error) {
    console.warn("تعذر تحميل الإحصائيات:", error);
  }
}

/* ============================================================
   مساعد المحادثة الذكي (Chat Widget) — محلي بالكامل عبر /api/chat
   ============================================================ */
const chatFab = byId("chatFab");
const chatPanel = byId("chatPanel");
const chatClose = byId("chatClose");
const chatMessages = byId("chatMessages");
const chatForm = byId("chatForm");
const chatInput = byId("chatInput");
const chatSuggestions = byId("chatSuggestions");
const knowledgeForm = byId("knowledgeForm");
const knowledgeDocuments = byId("knowledgeDocuments");
const knowledgeStatus = byId("knowledgeStatus");
const knowledgeMessage = byId("knowledgeMessage");
const knowledgeTestBtn = byId("knowledgeTestBtn");
const knowledgeTestQuery = byId("knowledgeTestQuery");
const knowledgeTestResults = byId("knowledgeTestResults");
let chatHistory = [];

function addBubble(text, who) {
  if (!chatMessages) return;
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${who}`;
  bubble.textContent = text;
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return bubble;
}

function addTypingBubble() {
  if (!chatMessages) return null;
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble bot typing";
  bubble.innerHTML = "<span></span><span></span><span></span>";
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return bubble;
}

let chatOpened = false;
function openChat() {
  setHidden(chatPanel, false);
  if (!chatOpened) {
    chatOpened = true;
    addBubble("أهلًا بك 👋 أنا وكيل AICC المكتبي بنظام RAG. أستخدم فهرس الموقع ووثائق المكتبة، وأرفض الأسئلة خارج نطاق المكتبات. لن أخترع كتابًا أو سياسة أو موقع رف.", "bot");
  }
}
if (chatFab) chatFab.addEventListener("click", () => {
  const isHidden = chatPanel.classList.contains("hidden");
  if (isHidden) openChat(); else setHidden(chatPanel, true);
});
if (chatClose) chatClose.addEventListener("click", () => setHidden(chatPanel, true));

async function sendChatMessage(text) {
  if (!text.trim()) return;
  addBubble(text, "user");
  chatHistory.push({role:"user", content:text});
  const typing = addTypingBubble();

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: text, context: lastBookContext, history:chatHistory.slice(-8)}),
    });
    const data = await response.json();
    if (typing) typing.remove();
    const reply = data.reply || "تعذر توليد رد الآن.";
    addBubble(reply, "bot");
    chatHistory.push({role:"assistant", content:data.reply || ""});
  } catch (error) {
    if (typing) typing.remove();
    addBubble("تعذر الاتصال بخادم المحادثة المحلي.", "bot");
  }
}

async function loadKnowledgeDocuments() {
  if (!knowledgeDocuments) return;
  try {
    const response = await fetch("/api/knowledge/documents", {
      headers:{Authorization:"Bearer aicc-demo-token"}, cache:"no-store"
    });
    const data = await response.json();
    const items = data.items || [];
    knowledgeStatus.textContent = `${items.length} وثيقة · ${items.reduce((n,x)=>n+(x.chunk_count||0),0)} مقطع`;
    knowledgeDocuments.innerHTML = "";
    if (!items.length) {
      knowledgeDocuments.textContent = "لم تُضف وثائق بعد.";
      return;
    }
    items.forEach(item => {
      const row = document.createElement("article");
      row.className = "knowledge-item";
      const info = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = item.title;
      const details = document.createElement("small");
      details.textContent = `${item.category || "غير مصنف"} · ${item.language || "—"} · ${item.chunk_count} مقطع`;
      const status = document.createElement("span");
      status.textContent = item.status === "indexed" ? "مفهرسة ✓" : item.status;
      info.append(title, details); row.append(info, status); knowledgeDocuments.appendChild(row);
    });
  } catch (error) {
    knowledgeStatus.textContent = "تعذر تحميل RAG";
  }
}

if (knowledgeForm) knowledgeForm.addEventListener("submit", async event => {
  event.preventDefault();
  const file = byId("knowledgeFile")?.files?.[0];
  if (!file) return;
  const button = byId("knowledgeUploadBtn");
  button.disabled = true; button.textContent = "جارٍ استخراج النص والفهرسة...";
  knowledgeMessage.className = "message hidden";
  try {
    const response = await fetch("/api/knowledge/documents", {
      method:"POST", headers:{Authorization:"Bearer aicc-demo-token"},
      body:new FormData(knowledgeForm)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "تعذر فهرسة الوثيقة");
    knowledgeMessage.textContent = `${data.message} عدد المقاطع: ${data.chunk_count}.`;
    knowledgeMessage.className = "message success";
    knowledgeForm.reset(); await loadKnowledgeDocuments();
  } catch (error) {
    knowledgeMessage.textContent = error.message;
    knowledgeMessage.className = "message error";
  } finally {
    button.disabled = false; button.textContent = "إضافة الوثيقة إلى RAG";
  }
});

if (knowledgeTestBtn) knowledgeTestBtn.addEventListener("click", async () => {
  const query = knowledgeTestQuery.value.trim();
  if (!query) return;
  knowledgeTestBtn.disabled = true; knowledgeTestResults.textContent = "جارٍ الاسترجاع...";
  try {
    const response = await fetch("/api/knowledge/test", {
      method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer aicc-demo-token"},
      body:JSON.stringify({query})
    });
    const data = await response.json();
    knowledgeTestResults.innerHTML = "";
    (data.results || []).forEach(result => {
      const card = document.createElement("article");
      const title = document.createElement("strong"); title.textContent = `${result.citation} · درجة ${result.score}`;
      const text = document.createElement("p"); text.textContent = result.content.slice(0,500);
      card.append(title,text); knowledgeTestResults.appendChild(card);
    });
    if (!(data.results || []).length) knowledgeTestResults.textContent = "لم يعثر RAG على مقطع داعم.";
  } catch (error) {
    knowledgeTestResults.textContent = "تعذر اختبار الاسترجاع.";
  } finally { knowledgeTestBtn.disabled = false; }
});

if (chatForm) {
  chatForm.addEventListener("submit", event => {
    event.preventDefault();
    const text = chatInput.value;
    chatInput.value = "";
    sendChatMessage(text);
  });
}

if (chatSuggestions) {
  chatSuggestions.addEventListener("click", event => {
    const btn = event.target.closest(".suggestion-chip");
    if (!btn) return;
    sendChatMessage(btn.dataset.msg || btn.textContent);
  });
}

checkHealth();
refreshStats();
loadKnowledgeDocuments();
loadSavedRecords();
