"""Normalise the Japanese-specific surface forms that extraction errors hide behind: full-width digits, yen formats,
era dates (令和 / 平成 / 昭和 and R/H/S abbreviations) and company-form variants."""
import re
import unicodedata
from datetime import date

# era -> (first day, year offset): Gregorian year = era year + offset
ERAS = {
    "令和": (date(2019, 5, 1), 2018), "R": (date(2019, 5, 1), 2018),
    "平成": (date(1989, 1, 8), 1988), "H": (date(1989, 1, 8), 1988),
    "昭和": (date(1926, 12, 25), 1925), "S": (date(1926, 12, 25), 1925),
}
_ERA_END = {"令和": None, "R": None, "平成": date(2019, 4, 30), "H": date(2019, 4, 30), "昭和": date(1989, 1, 7), "S": date(1989, 1, 7)}


def nfkc(s):
    return unicodedata.normalize("NFKC", str(s))


def to_int_yen(text):
    """'¥1,234' / '￥１，２３４' / '1,234円' / '△500' -> int; None if no number is present."""
    s = nfkc(text).strip()
    neg = bool(re.search(r"^[△▲−-]|[△▲]", s)) and bool(re.search(r"\d", s))
    digits = re.sub(r"[^\d]", "", s)
    if not digits:
        return None
    return -int(digits) if neg else int(digits)


def parse_date(text):
    """Return an ISO date 'YYYY-MM-DD' or None. Handles Western and era forms; rejects dates outside the era."""
    s = nfkc(text).strip().replace("元年", "1年")
    m = re.match(r"^(令和|平成|昭和)\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?$", s) or \
        re.match(r"^([RHS])\s*\.?\s*(\d{1,2})\s*[./年-]\s*(\d{1,2})\s*[./月-]\s*(\d{1,2})\s*日?$", s, re.I)
    if m:
        era = m.group(1).upper() if m.group(1).isascii() else m.group(1)
        y, mo, d = int(m.group(2)), int(m.group(3)), int(m.group(4))
        start, offset = ERAS[era]
        try:
            dt = date(y + offset, mo, d)
        except ValueError:
            return None
        end = _ERA_END[era]
        if dt < start or (end and dt > end):
            return None
        return dt.isoformat()
    m = re.match(r"^(\d{4})\s*[./年-]\s*(\d{1,2})\s*[./月-]\s*(\d{1,2})\s*日?$", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    return None


_FORMS = ["株式会社", "有限会社", "合同会社", "合資会社", "合名会社", "一般社団法人", "一般財団法人", "公益社団法人", "公益財団法人", "医療法人", "社会福祉法人", "学校法人"]


def normalize_name(name):
    """Comparable form of an issuer name: NFKC, no spaces, (株)/㈱/（株） spelled out as 株式会社."""
    s = nfkc(name)
    s = s.replace("(株)", "株式会社").replace("(有)", "有限会社").replace("(合)", "合同会社")
    return re.sub(r"[\s　]+", "", s)


def strip_company_form(name):
    """normalize_name without the legal-form words (for 'same company' matching)."""
    s = normalize_name(name)
    for f in _FORMS:
        s = s.replace(f, "")
    return s
