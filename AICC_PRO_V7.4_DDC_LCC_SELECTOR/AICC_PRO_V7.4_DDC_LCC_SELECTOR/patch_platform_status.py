from pathlib import Path

p=Path("app/main.py")
text=p.read_text(encoding="utf-8")

if "import hashlib" not in text:
    text="import hashlib\n"+text

anchor='@app.get("/api/ai/status")\ndef ai_status(authorization:str|None=Header(None)):\n'
endpoint='@app.get("/api/platform/status")\ndef platform_status():\n    key=os.getenv("PLATFORM_SYNC_KEY","").strip()\n    return {\n      "ok":True,\n      "direct_url":os.getenv("PLATFORM_SYNC_URL","").strip(),\n      "browser_url":os.getenv("PLATFORM_BROWSER_SYNC_URL","").strip(),\n      "sync_key_configured":bool(key),\n      "sync_key_fingerprint":hashlib.sha256(key.encode("utf-8")).hexdigest()[:12] if key else "",\n    }\n\n'

if "/api/platform/status" not in text:
    if anchor not in text:
        raise SystemExit("anchor not found")
    text=text.replace(anchor,endpoint+anchor,1)

p.write_text(text,encoding="utf-8")
print("platform status endpoint added")
