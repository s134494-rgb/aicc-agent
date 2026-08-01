"""Push an approved AICC record into the PHP library platform."""
import json
import os
import urllib.request
import urllib.error

def sync_config():
    return {
        "url": os.getenv("PLATFORM_SYNC_URL", "").strip(),
        "key": os.getenv("PLATFORM_SYNC_KEY", "").strip(),
    }

def sync_to_platform(payload: dict) -> dict:
    cfg = sync_config()
    if not cfg["url"] or not cfg["key"]:
        return {"ok": False, "skipped": True, "error": "not_configured"}

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        cfg["url"],
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-AICC-Sync-Key": cfg["key"],
            "User-Agent": "AICC-Platform-Sync/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as res:
            raw = res.read().decode("utf-8", errors="replace")
            result = json.loads(raw or "{}")
            result["http_status"] = getattr(res, "status", 200)
            return result
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body)
        except Exception:
            detail = {"body": body[:1000]}
        return {"ok": False, "error": "http_error", "http_status": exc.code, "detail": detail}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)}
