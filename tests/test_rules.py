import json
import random
import shutil
from pathlib import Path

import pytest

from invoicecheck.checkdigit import make_corporate_number
from invoicecheck.rules import _date, _names, _norm, _registration, _totals_and_grand, extract


def L(text, x0, y0, x1=None, y1=None, vertical=False):
    return {"text": text, "box": [x0, y0, x1 or x0 + 8 * len(text), y1 or y0 + 16], "vertical": vertical}


def test_registration_number_survives_ocr_confusions():
    good = "T" + make_corporate_number("123456789012")
    assert _registration(_norm([L("登録番号：" + good, 10, 10)])) == good
    garbled = good.replace("0", "O", 1) if "0" in good else good
    assert _registration(_norm([L("登録番号 " + garbled, 10, 10)])) == good
    assert _registration(_norm([L("TEL 03-1234-5678", 10, 10)])) == ""


def test_date_prefers_the_labelled_line():
    lines = _norm([L("支払期限：2030/01/31", 10, 10), L("発行日：令和7年3月14日", 10, 40)])
    assert _date(lines) == "2025-03-14"
    assert _date(_norm([L("R7.3.14", 10, 10)])) == "2025-03-14"


def test_recipient_is_marked_by_onchu_and_bank_name_counts_for_the_issuer():
    lines = _norm([L("株式会社受取商会", 10, 10, 130, 26), L("御中", 135, 10, 160, 26),
                   L("有限会社発行産業", 300, 10), L("口座名義：有限会社発行産業", 300, 200)])
    issuer, recipient = _names(lines)
    assert recipient == "株式会社受取商会" and issuer == "有限会社発行産業"


def test_totals_use_only_tokens_to_the_right_in_the_same_band():
    lines = _norm([L("10%対象（税抜）", 300, 500, 400, 516), L("¥1,000", 450, 500), L("消費税", 520, 500), L("¥100", 600, 500),
                   L("TEL 03-9999-9999", 10, 500)])                       # unrelated token at the same height, to the left
    totals, grand = _totals_and_grand(lines)
    assert totals == [{"rate": 10, "subtotal": 1000, "tax": 100}] and grand is None
    lines = _norm([L("合計金額（税込）", 20, 200, 130, 216), L("¥1,100", 250, 200), L("登録番号：T1234567890123", 400, 200)])
    assert _totals_and_grand(lines)[1] == 1100


@pytest.mark.skipif(not Path("data/synth/gold_train.jsonl").exists() or not shutil.which("google-chrome"), reason="needs generated data and Chrome")
def test_rules_on_perfect_ocr_are_accurate_on_horizontal_layouts():
    from playwright.sync_api import sync_playwright

    from invoicecheck.evaluation import evaluate
    from invoicecheck.synth.render import H, W, dom_lines, render_html
    gold = [g for g in (json.loads(l) for l in open("data/synth/gold_train.jsonl")) if g["layout"] == "horizontal"][:40]
    preds = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": W, "height": H})
        for g in gold:
            pg.set_content(render_html(g, random.Random(g["invoice_id"])))
            preds.append({"id": g["invoice_id"], "parsed": extract(dom_lines(pg))})
        b.close()
    recs = evaluate(gold, preds)
    assert sum(r["exact"] for r in recs) / len(recs) >= 0.9
