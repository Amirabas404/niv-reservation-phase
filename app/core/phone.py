import re

from app.domain.errors import InvalidPhoneError

_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "0123456789" * 2)
_MOBILE = re.compile(r"09\d{9}")


def normalize_phone(raw: str) -> str:
    """Accept Persian/Arabic digits, spaces, +98, 0098, or 9xxxxxxxxx; return 09xxxxxxxxx."""
    s = raw.translate(_DIGIT_MAP)
    s = re.sub(r"[\s\-()]", "", s)
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    elif len(s) == 10 and s.startswith("9"):
        s = "0" + s
    if not _MOBILE.fullmatch(s):
        raise InvalidPhoneError("شماره موبایل معتبر نیست. لطفاً شماره‌ای مانند 09xxxxxxxxx وارد کنید.")
    return s
