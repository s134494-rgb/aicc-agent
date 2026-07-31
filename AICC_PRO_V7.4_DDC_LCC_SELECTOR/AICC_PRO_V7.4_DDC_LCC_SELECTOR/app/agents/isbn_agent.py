import re

DIGIT_MAP=str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹","01234567890123456789")

def latin_digits(value):
    return (value or "").translate(DIGIT_MAP)

def normalize(value):
    return re.sub(r"[^0-9Xx]","",latin_digits(value)).upper()

def valid_isbn10(value):
    value=normalize(value)
    if len(value)!=10:return False
    # 978/979 are EAN prefixes for ISBN-13, not registration groups for ISBN-10.
    # This prevents a truncated ISBN-13 such as 9789948387 from passing merely
    # because its first ten digits happen to satisfy the ISBN-10 checksum.
    if value.startswith(("978","979")):return False
    total=0
    for i,ch in enumerate(value):
        digit=10 if ch=="X" and i==9 else int(ch) if ch.isdigit() else -1
        if digit<0:return False
        total+=(10-i)*digit
    return total%11==0

def valid_isbn13(value):
    value=normalize(value)
    if len(value)!=13 or not value.isdigit():return False
    total=sum((1 if i%2==0 else 3)*int(ch) for i,ch in enumerate(value[:12]))
    return (10-total%10)%10==int(value[-1])

def candidates(text):
    source=latin_digits(text)
    # Includes labeled ISBNs, bare hyphenated strings and OCR-spaced barcode digits.
    pattern=r"(?<!\d)(?:97[89][ \t\-–—.:]*)?[0-9](?:[ \t\-–—.:]*[0-9]){8,12}[ \t\-–—.:]*[0-9Xx](?!\d)"
    raw=[]
    for line in source.splitlines():
        raw.extend(re.findall(pattern,line))
    seen=[]; out=[]
    for item in raw:
        value=normalize(item)
        if value not in seen and len(value) in (10,13):
            seen.append(value)
            out.append({"candidate":item.strip(),"normalized":value,
              "valid":valid_isbn10(value) or valid_isbn13(value),
              "type":"ISBN-13" if len(value)==13 else "ISBN-10"})
    # OCR commonly confuses 0/O, 1/I/l, 5/S and 8/B. Repair only lines explicitly
    # labelled ISBN/ردمك, and accept a repair only when its checksum is valid.
    for line in source.splitlines():
        if not re.search(r"ISBN|ردمك|الرقم\s+الدولي",line,re.I):
            continue
        payload=re.split(r"ISBN|ردمك|الرقم\s+الدولي",line,flags=re.I)[-1]
        repaired=payload.upper().translate(str.maketrans({"O":"0","I":"1","L":"1","S":"5","B":"8"}))
        compact=re.sub(r"[^0-9X]","",repaired)
        for length in (13,10):
            for start in range(max(0,len(compact)-length+1)):
                value=compact[start:start+length]
                valid=valid_isbn13(value) if length==13 else valid_isbn10(value)
                if valid and value not in seen:
                    seen.append(value)
                    out.append({"candidate":line.strip(),"normalized":value,"valid":True,
                      "type":"ISBN-13" if length==13 else "ISBN-10","ocr_repaired":True})
    return out

def find_valid_isbn(text):
    valid=[x["normalized"] for x in candidates(text) if x["valid"]]
    valid.sort(key=lambda x:(len(x)!=13,x))
    return valid[0] if valid else ""

def status(value):
    value=normalize(value)
    valid=valid_isbn13(value) or valid_isbn10(value)
    return {"value":value,"valid":valid,
      "type":"ISBN-13" if len(value)==13 else "ISBN-10" if len(value)==10 else "غير صالح",
      "message":"تم التحقق رياضيًا" if valid else "لم يجتز التحقق الرياضي"}
