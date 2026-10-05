#!/usr/bin/env python3
"""Render the hero chart (card light/dark 1200x750, cover 2000x840) from results/*.json with headless Chrome.
  python scripts/make_chart.py      -> images/invoice-check-jp.png (card, light), images/invoice-check-jp-cover.png, outputs/chart/*
"""
import json
import subprocess
from pathlib import Path

OUT = Path("outputs/chart")
OUT.mkdir(parents=True, exist_ok=True)
Path("images").mkdir(exist_ok=True)
SYSTEMS = [("ocr_rules", "OCR + rules"), ("zeroshot", "VLM zero-shot"), ("qlora", "VLM fine-tuned")]
rows = []
for key, label in SYSTEMS:
    e = json.load(open(f"results/eval_{key}_test.json"))
    v = json.load(open(f"results/verification_{key}_test.json"))["levels"]["tax"]
    cov = v["residual_covered_among_approved"]
    rows.append(dict(label=label, exact=100 * e["exact"]["mean"], auto=100 * v["automation_rate"]["mean"], k=cov["k"], n=cov["n"], hi=100 * cov["cp_hi"]))

THEMES = {
    "light": dict(bg="#fbfbfa", fg="#111111", muted="#6b6b6b", grid="#d8d6d0", grey="#b4b3ab", accent="#2a78d6", warn="#eb6834", border="#e4e2dc"),
    "dark": dict(bg="#0e0f11", fg="#ffffff", muted="#9a9a9a", grid="#3a3a3a", grey="#5a5a5a", accent="#3b82f0", warn="#f07a45", border="#2a2a2a"),
}


def card(t, w=1200, h=750):
    x0, x1 = 330, w - 90
    sx = lambda v: x0 + v / 100 * (x1 - x0)
    p = [f'<text x="48" y="74" font-size="40" font-weight="700" fill="{t["fg"]}">86.8% automated, 0 wrong covered fields</text>',
         f'<text x="48" y="116" font-size="23" fill="{t["muted"]}">Fine-tuned VLM + checks (Qwen2.5-VL-3B, QLoRA on 3,000 invoices), 600 synthetic test invoices.</text>']
    for v in (0, 25, 50, 75, 100):
        p.append(f'<line x1="{sx(v)}" y1="150" x2="{sx(v)}" y2="560" stroke="{t["grid"]}" stroke-width="1"/>')
        p.append(f'<text x="{sx(v)}" y="590" font-size="19" text-anchor="middle" fill="{t["muted"]}">{v}%</text>')
    for i, r in enumerate(rows):
        y = 175 + i * 132
        p.append(f'<text x="48" y="{y + 38}" font-size="26" font-weight="600" fill="{t["fg"]}">{r["label"]}</text>')
        for j, (lab, val, col) in enumerate([("all fields right (no checks)", r["exact"], t["grey"]), ("auto-approved by the checks", r["auto"], t["accent"])]):
            yy = y + j * 40
            p.append(f'<rect x="{x0}" y="{yy}" width="{max(sx(val) - x0, 2)}" height="30" rx="4" fill="{col}"/>')
            p.append(f'<text x="{sx(val) + 10}" y="{yy + 22}" font-size="21" font-weight="600" fill="{t["fg"]}">{val:.1f}%</text>')
        wrong = f'{r["k"]} of {r["n"]} approved had a wrong covered field' + (f' ({100 * r["k"] / r["n"]:.1f}%)' if r["k"] else f' (upper bound {r["hi"]:.1f}%)')
        p.append(f'<text x="{x0}" y="{y + 108}" font-size="19" fill="{t["warn"] if r["k"] else t["muted"]}">{wrong}</text>')
    p.append(f'<g transform="translate(48 690)"><rect x="0" y="-14" width="14" height="14" rx="3" fill="{t["grey"]}"/><text x="22" y="0" font-size="19" fill="{t["muted"]}">all fields right, no checks</text>'
             f'<rect x="300" y="-14" width="14" height="14" rx="3" fill="{t["accent"]}"/><text x="322" y="0" font-size="19" fill="{t["muted"]}">auto-approved by schema, check digit, registry, name and tax checks</text></g>')
    p.append(f'<text x="48" y="722" font-size="17" fill="{t["muted"]}">Covered fields: registration number, issuer, tax basis, totals, item numbers. Synthetic invoices; see Limitations.</text>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Inter, Helvetica, Arial, sans-serif"><rect width="{w}" height="{h}" fill="{t["bg"]}"/>{"".join(p)}</svg>'


def render(html, name, w, h):
    f = OUT / f"{name}.html"
    f.write_text(f'<!doctype html><meta charset="utf-8"><style>html,body{{margin:0;background:#fff}}</style>{html}')
    subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--hide-scrollbars", "--force-device-scale-factor=1", f"--window-size={w},{h}",
                    f"--screenshot={OUT / (name + '.png')}", f"file://{f.resolve()}"], check=True, capture_output=True, timeout=120)


for name, t in THEMES.items():
    render(card(t), f"card-{name}", 1200, 750)
t = THEMES["light"]
cover = f'''<div style="width:2000px;height:840px;background:{t["bg"]};position:relative;font-family:Inter,Helvetica,Arial,sans-serif;color:{t["fg"]}">
<div style="position:absolute;left:96px;top:290px;font-size:34px;color:{t["muted"]}">raihan-js / invoice-check-jp</div>
<div style="position:absolute;left:92px;top:350px;font-size:104px;font-weight:700;letter-spacing:-2px">Invoice-Check JP</div>
<div style="position:absolute;left:96px;top:490px;font-size:40px;color:{t["muted"]};width:820px;line-height:1.3">Japanese qualified-invoice extraction, verified instead of trusted</div>
<div style="position:absolute;left:1000px;top:150px;width:864px;height:540px;border:2px solid {t["border"]};border-radius:36px;overflow:hidden">
<div style="transform:scale(0.72);transform-origin:0 0;width:1200px;height:750px">{card(t)}</div></div></div>'''
render(cover, "cover", 2000, 840)
import shutil
shutil.copy(OUT / "card-light.png", "images/invoice-check-jp.png")
shutil.copy(OUT / "cover.png", "images/invoice-check-jp-cover.png")
print("wrote", sorted(p.name for p in OUT.glob("*.png")), [r["label"] + f" {r['exact']:.1f}/{r['auto']:.1f}" for r in rows])
