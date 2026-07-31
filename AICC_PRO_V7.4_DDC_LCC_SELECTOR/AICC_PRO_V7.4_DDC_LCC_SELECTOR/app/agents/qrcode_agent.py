"""
وكيل رمز الاستجابة السريعة (QR Agent)
--------------------------------------
يولّد رمز QR محليًا (بدون إنترنت) يحتوي على بيانات بطاقة الفهرسة الأساسية
(رقم الطلب، ISBN، العنوان)، بحيث يمكن طباعته ولصقه على ظهر الكتاب أو على
بطاقة الرف، ومسحه لاحقًا بأي تطبيق جوال لعرض بيانات الكتاب بسرعة.

يعتمد على مكتبة qrcode المدرجة أصلًا ضمن requirements.txt.
"""

import base64
from io import BytesIO

try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:  # الحزمة قد لا تكون مثبتة بعد على بيئة المستخدم
    QR_AVAILABLE = False


def build_call_number_qr(call_number: str, isbn: str, title: str) -> str:
    """يعيد صورة QR كسلسلة base64 (data URL) أو نصًا فارغًا إن تعذر التوليد."""
    if not QR_AVAILABLE:
        return ""

    payload_lines = [line for line in [
        f"CallNumber: {call_number}" if call_number else "",
        f"ISBN: {isbn}" if isbn else "",
        f"Title: {title}" if title else "",
    ] if line]

    if not payload_lines:
        return ""

    payload = "\n".join(payload_lines)

    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
