"""Rule-based extraction from OCR text boxes (the 'OCR + rules' baseline).

Input: lines = [{"text": str, "box": [x0, y0, x1, y1], "vertical": bool}], from any OCR engine (or from the page DOM, which gives a
perfect-OCR upper bound for these rules). No learning; regexes plus geometry. Written for the layouts the generator produces.
"""
import re
from collections import Counter

from .checkdigit import is_valid_corporate_number, normalize_registration_number
from .normalize import nfkc, normalize_name, parse_date, to_int_yen

CO = r"(?:株式会社|有限会社|合同会社)"
NAME_RE = re.compile(rf"(?:{CO}[^\s：:（(\d]{{2,18}}|[^\s：:（(\d]{{2,18}}{CO})")
DATE_PATTERNS = [r"(?:令和|平成)\s*(?:元|\d{1,2})\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日", r"[RH]\s*\.?\s*\d{1,2}\s*[./]\s*\d{1,2}\s*[./]\s*\d{1,2}",
                 r"\d{4}\s*[/.]\s*\d{1,2}\s*[/.]\s*\d{1,2}", r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日"]
AMOUNT = re.compile(r"[¥￥]?\s*\d[\d,，]*\s*円?")
CONFUSIONS = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1", "S": "5", "B": "8"})


def _norm(lines):
    out = []
    for ln in lines:
        t = nfkc(ln["text"]).strip()
        if t:
            x0, y0, x1, y1 = ln["box"]
            out.append({"t": t, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2, "vertical": ln.get("vertical", False)})
    return out


def _registration(lines):
    cands = []
    for ln in lines:
        s = ln["t"]
        for m in re.finditer(r"T\s*[-－]?\s*([0-9OIl|SB][0-9OIl|SB\s-]{11,18})", s):
            digits = re.sub(r"[\s-]", "", m.group(1)).translate(CONFUSIONS)
            digits = re.sub(r"\D", "", digits)
            if len(digits) >= 13:
                cands.append(digits[:13])
    for c in cands:
        if is_valid_corporate_number(c):
            return "T" + c
    return "T" + cands[0] if cands else ""


def _date(lines):
    best = None
    for ln in lines:
        for pat in DATE_PATTERNS:
            for m in re.finditer(pat, ln["t"]):
                iso = parse_date(m.group(0))
                if iso:
                    if "発行日" in ln["t"]:
                        return iso
                    best = best or iso
    return best or ""


def _names(lines):
    """(issuer, recipient) from company-name occurrences, using 御中 / 口座名義 as cues. Handles '…御中' merged into one OCR line."""
    recipient, issuer_votes = "", Counter()
    for ln in lines:
        text = ln["t"].replace("(株)", "株式会社")
        for m in NAME_RE.finditer(re.sub(r"(御中|様)", r" \1 ", text)):
            nm = m.group(0)
            s2 = re.sub(r"(御中|様)", r" \1 ", text)
            neighbours = " ".join(l["t"] for l in lines if l is not ln and (
                (abs(l["cy"] - ln["cy"]) < 14 and -25 <= l["x0"] - ln["x1"] < 60) or
                (l["vertical"] and ln["vertical"] and 0 <= l["y0"] - ln["y1"] < 30 and abs(l["cx"] - ln["cx"]) < 14)))
            if re.match(r"\s*(御中|様)", s2[m.end():]) or neighbours.strip().startswith("御中") or "御中" in neighbours.split(" ")[:1]:
                recipient = recipient or nm
            elif "口座名義" in ln["t"]:
                issuer_votes[nm] += 1
            else:
                issuer_votes[nm] += 2
    issuer = issuer_votes.most_common(1)[0][0] if issuer_votes else ""
    return issuer, recipient


def _amounts(text):
    return [to_int_yen(m.group(0)) for m in AMOUNT.finditer(text) if re.search(r"\d", m.group(0))]


def _right_of(label, lines, tol=12):
    """Tokens in the same horizontal band as `label` and to its right, nearest first."""
    out = [l for l in lines if l is not label and not l["vertical"] and abs(l["cy"] - label["cy"]) <= tol and l["x0"] >= label["x1"] - 2]
    return sorted(out, key=lambda l: l["x0"])


def _totals_and_grand(L):
    totals, grand = [], None
    for ln in L:
        if ln["vertical"]:
            continue
        mt = re.match(r"(\d+)\s*%[対对]象", ln["t"])
        if mt:
            rest = ln["t"][mt.end():] + " " + " ".join(t["t"] for t in _right_of(ln, L))
            m2 = re.search(r"([¥￥]?\s*\d[\d,]*)\s*円?\s*消費税\s*([¥￥]?\s*\d[\d,]*)", rest)
            if m2:
                totals.append({"rate": int(mt.group(1)), "subtotal": to_int_yen(m2.group(1)), "tax": to_int_yen(m2.group(2))})
        elif "合計金額" in ln["t"] and grand is None:
            toks = [t for t in _right_of(ln, L) if re.search(r"\d", t["t"])]
            if toks:
                grand = to_int_yen(toks[0]["t"])
    return sorted(totals, key=lambda t: -t["rate"]), grand


def _deskew(L):
    """Remove the page tilt (scan rotation) using the four table-header cells; no-op when they are not all found."""
    cells = []
    for name in ("品名", "数量", "単価", "金額"):
        c = [l for l in L if l["t"] == name and not l["vertical"]]
        if not c:
            return L
        cells.append(c[0] if not cells else min(c, key=lambda l: abs(l["cy"] - cells[0]["cy"])))
    xs, ys = [c["cx"] for c in cells], [c["cy"] for c in cells]
    mx, my = sum(xs) / 4, sum(ys) / 4
    den = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else 0.0
    if abs(b) > 0.08:      # implausible tilt: header cells were mismatched
        return L
    out = []
    for l in L:
        d = b * (l["cx"] - mx)
        out.append({**l, "cy": l["cy"] - d, "y0": l["y0"] - d, "y1": l["y1"] - d})
    return out


def _items(L):
    hdr = {}
    for name in ("品名", "数量", "単価", "金額"):
        c = [l for l in L if l["t"] == name and not l["vertical"]]
        if not c:
            return []
        hdr[name] = c
    # header cells share a row: take the 品名 cell and the other headers closest to its y
    h0 = hdr["品名"][0]
    cols = []
    for name in ("品名", "数量", "単価", "金額"):
        cell = min(hdr[name], key=lambda l: abs(l["cy"] - h0["cy"]))
        cols.append(cell)
    y_top = max(c["y1"] for c in cols)
    stop = min([l["cy"] for l in L if l["cy"] > y_top + 10 and not l["vertical"] and re.match(r"\d+\s*%[対对]象|合計金額|お振込先|※は軽減", l["t"])] or [1e9])
    body = [l for l in L if y_top < l["cy"] < stop and not l["vertical"]]
    centers = [c["cx"] for c in cols]
    rows = []
    for ln in sorted(body, key=lambda l: (l["cy"], l["x0"])):
        if rows and abs(rows[-1][0] - ln["cy"]) <= 9:
            rows[-1][1].append(ln)
        else:
            rows.append([ln["cy"], [ln]])
    items = []
    for _, toks in rows:
        cells = [[] for _ in cols]
        for t in toks:
            j = min(range(4), key=lambda k: abs(t["cx"] - centers[k]) if k else (0 if t["cx"] < (centers[0] + centers[1]) / 2 else 1e9))
            cells[j].append(t["t"])
        desc = "".join(cells[0])
        nums = [to_int_yen(" ".join(c)) if c else None for c in cells[1:]]
        if desc and all(n is not None for n in nums):
            items.append({"description": desc, "quantity": nums[0], "unit_price": nums[1], "amount": nums[2], "rate": 8 if desc.startswith("※") else 10})
    return items


def extract(lines):
    L = _deskew(_norm(lines))
    full = " ".join(l["t"] for l in L)
    issuer, recipient = _names(L)
    m = re.search(r"請求書番号[:：]\s*(\S+)", full)
    norm_full = full.replace("(", "（").replace(")", "）")
    totals, grand = _totals_and_grand(L)
    return {"issuer_name": issuer, "registration_number": normalize_registration_number(_registration(L)) or "", "issue_date": _date(L),
            "recipient_name": recipient, "invoice_number": m.group(1) if m else "",
            "tax_included": bool(re.search(r"[対对]象（税込）", norm_full)), "grand_total": grand, "items": _items(L), "totals": totals}
