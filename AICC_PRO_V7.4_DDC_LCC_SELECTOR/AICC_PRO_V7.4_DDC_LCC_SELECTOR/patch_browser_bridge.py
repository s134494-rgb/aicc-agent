from pathlib import Path

p=Path("app/static/app.js")
text=p.read_text(encoding="utf-8")
marker = '''      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "تعذر اعتماد السجل");
      setMessage(`تم اعتماد السجل وحفظه. رقم السجل: ${data.record_id}`, "success");
      approveBtn.textContent = "تم الاعتماد ✓";
      refreshStats();
'''
replacement = '''      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "تعذر اعتماد السجل");

      if (data.platform_browser_fallback?.url && data.platform_browser_fallback?.payload && data.platform_browser_fallback?.signature) {
        const frameName = "aicc-platform-sync-" + Date.now();
        const iframe = document.createElement("iframe");
        iframe.name = frameName;
        iframe.style.display = "none";
        document.body.appendChild(iframe);

        const bridgeForm = document.createElement("form");
        bridgeForm.method = "POST";
        bridgeForm.action = data.platform_browser_fallback.url;
        bridgeForm.target = frameName;
        bridgeForm.style.display = "none";

        for (const [name,value] of Object.entries({
          payload: data.platform_browser_fallback.payload,
          signature: data.platform_browser_fallback.signature
        })) {
          const hidden = document.createElement("input");
          hidden.type = "hidden";
          hidden.name = name;
          hidden.value = value;
          bridgeForm.appendChild(hidden);
        }
        document.body.appendChild(bridgeForm);
        bridgeForm.submit();
        setTimeout(() => { bridgeForm.remove(); iframe.remove(); }, 15000);
      }

      setMessage(`تم اعتماد السجل وحفظه. رقم السجل: ${data.record_id}. جارٍ إضافته إلى منصة المكتبة...`, "success");
      approveBtn.textContent = "تم الاعتماد ✓";
      refreshStats();
'''
if marker not in text:
    if "platform_browser_fallback" not in text:
        raise SystemExit("Could not find approve UI block in app/static/app.js")
else:
    text=text.replace(marker,replacement,1)
p.write_text(text,encoding="utf-8")

p=Path("app/main.py")
text=p.read_text(encoding="utf-8")
if "import hmac, hashlib" not in text:
    text=text.replace("import json, logging, os, time","import json, logging, os, time, hmac, hashlib",1)

marker = '''    return {"ok":True,"record_id":bid,"message":message,"platform_sync":platform}
'''
replacement = '''    fallback={}
    fallback_url=os.getenv("PLATFORM_BROWSER_SYNC_URL","").strip()
    fallback_key=os.getenv("PLATFORM_SYNC_KEY","").strip()
    if fallback_url and fallback_key:
      fallback_payload=json.dumps(platform_payload,ensure_ascii=False,separators=(",",":"))
      fallback_signature=hmac.new(
        fallback_key.encode("utf-8"), fallback_payload.encode("utf-8"), hashlib.sha256
      ).hexdigest()
      fallback={"url":fallback_url,"payload":fallback_payload,"signature":fallback_signature}

    return {"ok":True,"record_id":bid,"message":message,"platform_sync":platform,
      "platform_browser_fallback":fallback}
'''
if marker not in text:
    if "platform_browser_fallback" not in text:
        raise SystemExit("Could not find patched approve return in app/main.py")
else:
    text=text.replace(marker,replacement,1)
p.write_text(text,encoding="utf-8")
print("Browser bridge patch applied")
