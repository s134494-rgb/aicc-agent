from pathlib import Path
from PIL import Image
import cv2
import numpy as np

SUPPORTED = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def validate_image(path):
    suffix = Path(path).suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError("نوع الصورة غير مدعوم.")
    try:
        with Image.open(path) as image:
            image.verify()
    except Exception as exc:
        raise ValueError("الصورة تالفة أو يتعذر فتحها.") from exc


def image_quality(path):
    """Return measurable capture quality; never pretend an unreadable photo is reliable."""
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError("تعذر قراءة الصورة.")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape[:2]
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    megapixels = (width * height) / 1_000_000
    warnings = []
    if megapixels < 0.7:
        warnings.append("دقة الصورة منخفضة؛ أعد الالتقاط بدقة أعلى.")
    if sharpness < 55:
        warnings.append("الصورة مهزوزة أو غير حادة؛ ثبّت الكاميرا وأعد الالتقاط.")
    if brightness < 45:
        warnings.append("الصورة مظلمة؛ حسّن الإضاءة وأعد الالتقاط.")
    if brightness > 235:
        warnings.append("الصورة شديدة السطوع؛ تجنب انعكاس الضوء.")
    if contrast < 22:
        warnings.append("التباين ضعيف؛ صوّر الصفحة على سطح مستوٍ وإضاءة موزعة.")
    score = 100
    score -= 28 if megapixels < 0.7 else 0
    score -= 32 if sharpness < 55 else 0
    score -= 22 if brightness < 45 or brightness > 235 else 0
    score -= 18 if contrast < 22 else 0
    return {
        "score": max(0, score), "width": width, "height": height,
        "megapixels": round(megapixels, 2), "sharpness": round(sharpness, 1),
        "brightness": round(brightness, 1), "contrast": round(contrast, 1),
        "warnings": warnings, "acceptable": score >= 60,
    }


def preprocess_image(path):
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError("تعذر قراءة الصورة.")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    height, width = gray.shape[:2]
    max_side = max(height, width)
    if max_side > 2200:
        scale = 2200 / max_side
        gray = cv2.resize(
            gray,
            (int(width * scale), int(height * scale)),
            interpolation=cv2.INTER_AREA,
        )

    gray = cv2.bilateralFilter(gray, 7, 55, 55)
    return Image.fromarray(gray)


def ocr_variants(path):
    """Independent renderings improve Arabic OCR and preserve barcode digits."""
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError("تعذر قراءة الصورة.")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape[:2]
    if max(height, width) < 1800:
        scale = min(2.2, 1800 / max(height, width))
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    denoised = cv2.fastNlMeansDenoising(gray, None, 8, 7, 21)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(denoised)
    threshold = cv2.adaptiveThreshold(
        clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 13
    )
    return [Image.fromarray(gray), Image.fromarray(clahe), Image.fromarray(threshold)]
