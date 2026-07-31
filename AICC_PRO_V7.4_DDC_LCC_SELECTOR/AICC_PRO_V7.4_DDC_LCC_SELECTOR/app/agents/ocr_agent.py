import os
import re
import shutil
from pathlib import Path
import pytesseract

from .image_agent import ocr_variants

DEFAULT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def configure():
    candidates = [
        os.getenv("TESSERACT_CMD", "").strip(),
        DEFAULT_CMD,
        shutil.which("tesseract"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            return
    raise FileNotFoundError(
        r"لم يتم العثور على Tesseract في C:\Program Files\Tesseract-OCR"
    )


def clean(text):
    text = text.replace("\x0c", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_language(text):
    arabic = len(re.findall(r"[\u0600-\u06FF]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if arabic > latin * 1.25:
        return "العربية"
    if latin > arabic * 1.25:
        return "الإنجليزية"
    return "مختلطة"


def extract_text(path):
    configure()
    attempts = []
    available=set(pytesseract.get_languages(config=""))
    if "ara" in available and "eng" in available:
        languages="ara+eng"
    elif "ara" in available:
        languages="ara"
    elif "eng" in available:
        languages="eng"
    else:
        raise FileNotFoundError("لا توجد حزمة OCR عربية أو إنجليزية مثبتة.")
    # Two complementary passes are materially faster than the former 12-pass
    # loop and preserve dense Arabic text plus sparse labels/ISBN evidence.
    variants = ocr_variants(path)
    for image, psm in ((variants[1], 6), (variants[2], 11)):
        try:
            result = pytesseract.image_to_string(
                image, lang=languages, config=f"--oem 3 --psm {psm}", timeout=25
            )
            result = clean(result)
            if result:
                attempts.append(result)
        except RuntimeError:
            # pytesseract raises RuntimeError on timeout; preserve any completed pass.
            continue

    # Keep the strongest reading order, then append unique evidence lines found
    # only by other layouts (especially ISBN/barcode, names and imprint data).
    def strength(value):
        chars=len(re.findall(r"[A-Za-z\u0600-\u06FF0-9٠-٩]",value))
        labels=len(re.findall(r"ISBN|ردمك|تأليف|المؤلف|الناشر|الطبعة|حقوق|العنوان",value,re.I))
        return chars + labels*35
    text = max(attempts, key=strength, default="")
    seen={re.sub(r"\W+","",x).lower() for x in text.splitlines() if x.strip()}
    extra=[]
    for attempt in attempts:
        for line in attempt.splitlines():
            key=re.sub(r"\W+","",line).lower()
            if len(key)>=4 and key not in seen:
                digit_count=len(re.findall(r"[0-9٠-٩]",line))
                if digit_count>=4 or re.search(r"ISBN|ردمك|تأليف|المؤلف|الناشر|الطبعة|حقوق",line,re.I):
                    seen.add(key); extra.append(line.strip())
    if extra:text=text+"\n\n[أدلة OCR إضافية]\n"+"\n".join(extra)
    agreement = 0
    if attempts:
        base=set(re.findall(r"[\w\u0600-\u06FF]{3,}",text.lower()))
        overlaps=[]
        for candidate in attempts:
            words=set(re.findall(r"[\w\u0600-\u06FF]{3,}",candidate.lower()))
            if base and words: overlaps.append(len(base & words)/len(base | words))
        agreement=round(100*sum(overlaps)/len(overlaps)) if overlaps else 0
    return text, detect_language(text), {"attempts":len(attempts),"agreement":agreement}
