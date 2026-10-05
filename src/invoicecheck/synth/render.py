"""Gold invoice -> HTML -> PNG/JPEG. Shared blocks are built here; structure templates (templates/*.html.j2) only arrange them.

render_page() also returns the page's visible text so a caller can assert every gold value is printed on the page.
"""
import io
import random
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .invoice import yen
from .skins import SKINS, layout_of

TEMPLATE_DIR = Path(__file__).parent / "templates"
ENV = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=select_autoescape(["html", "j2"]))
W, H = 794, 1123          # A4 at 96 dpi (CSS px)


def _seal_html(g, rng):
    if not g["seal"]:
        return ""
    core = g["issuer"]["name"].replace("株式会社", "").replace("有限会社", "").replace("合同会社", "")
    chars = (core + "之印")[:6]
    cols = [chars[i:i + 3] for i in range(0, len(chars), 3)]
    rot = rng.uniform(-6, 6)
    top = 46 if g.get("seal_overlap") else -6    # an overlapping stamp lands on the address / registration lines
    return (f'<div class="seal" style="transform:rotate({rot:.1f}deg);right:{rng.randint(-4, 8)}px;top:{top}px">' +
            "".join(f"<span>{c}</span>" for c in cols) + "</div>")


def build_blocks(g, rng):
    ys = g["yen_style"]
    m = lambda n: yen(n, ys)
    rows = "".join(
        f'<tr><td class="d">{it["description"]}</td><td class="n">{it["quantity"]}</td>'
        f'<td class="n">{m(it["unit_price"])}</td><td class="n">{m(it["amount"])}</td></tr>' for it in g["items"])
    items = f'<table class="items"><thead><tr><th>品名</th><th>数量</th><th>単価</th><th>金額</th></tr></thead><tbody>{rows}</tbody></table>'
    basis = "税込" if g["tax_included"] else "税抜"
    srows = "".join(
        f'<tr><td>{t["rate"]}%対象（{basis}）</td><td class="n">{m(t["subtotal"])}</td><td>消費税</td><td class="n">{m(t["tax"])}</td></tr>'
        for t in g["totals"])
    summary = f'<table class="summary"><tbody>{srows}</tbody></table><div class="note">※は軽減税率（8%）対象品目です。</div>'
    total_label = "合計金額（税込）"
    total_box = f'<div class="totalbox"><span>{total_label}</span><b>{m(g["grand_total"])}</b></div>'
    iss = g["issuer"]
    issuer = (f'<div class="issuer"><div class="iname">{iss["name"]}</div><div>{iss["address"]}</div><div>TEL {iss["phone"]}</div>'
              f'<div class="reg">登録番号：{iss["registration_number"]}</div></div>')
    recipient = f'<div class="recipient"><span class="rname">{g["recipient"]["name"]}</span> 御中</div>'
    meta = (f'<div class="meta"><div>請求書番号：{g["invoice_number"]}</div><div>発行日：{g["printed"]["issue_date"]}</div></div>')
    bank = (f'<div class="bank">お振込先<br>{rng.choice(["みずき", "あおぞら", "さくら", "ひので"])}銀行 {rng.choice(["本店", "中央支店", "駅前支店"])} '
            f'普通 {rng.randint(1000000, 9999999)}<br>口座名義：{iss["name"]}</div>')
    return {"bank": bank, "item_table": items, "summary": summary, "total_box": total_box, "issuer": issuer, "recipient": recipient, "meta": meta,
            "seal": _seal_html(g, rng)}


def render_html(g, rng=None):
    rng = rng or random.Random(g["invoice_id"])
    struct, skin = g["template"].split("__")
    t = ENV.get_template(f"{struct}.html.j2")
    return t.render(g=g, blocks=build_blocks(g, rng), skin=SKINS[skin], title=SKINS[skin]["title"], layout=layout_of(g["template"]))


def noise_image(png_bytes, rng, strength):
    """Scan-like degradation: small rotation, blur, brightness/contrast, grain, fold line, JPEG. Returns a PIL image."""
    import numpy as np
    from PIL import Image, ImageFilter
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    if strength <= 0:
        return im
    paper = tuple(int(x) for x in np.array(im)[2:6, 2:6].reshape(-1, 3).mean(0))
    im = im.rotate(rng.uniform(-1.4, 1.4) * strength, resample=Image.BICUBIC, expand=False, fillcolor=paper)
    if rng.random() < 0.6:
        im = im.filter(ImageFilter.GaussianBlur(rng.uniform(0.2, 0.8) * strength))
    a = np.asarray(im).astype("float32")
    a = (a - 128) * rng.uniform(0.85, 1.1) + 128 + rng.uniform(-12, 8) * strength
    a += np.random.default_rng(rng.randrange(1 << 30)).normal(0, rng.uniform(2, 7) * strength, a.shape)
    if rng.random() < 0.5:                                   # fold line
        y = rng.randrange(int(a.shape[0] * 0.25), int(a.shape[0] * 0.75))
        a[y - 1:y + 2, :, :] *= rng.uniform(0.86, 0.95)
    if rng.random() < 0.4:                                   # edge shadow
        x = np.linspace(0, 1, a.shape[1])[None, :, None]
        a *= 1 - 0.12 * strength * np.maximum(x - 0.85, 0) / 0.15 * rng.choice([0, 1])
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8"))


def render_page(page, g, out_path, rng, dpr_note=1.25, noise=True):
    """Render one gold invoice to a JPEG; returns (page text, content_fits_on_page) for gold-alignment checks."""
    html = render_html(g, rng)
    page.set_content(html)
    text = page.inner_text("body")
    fits = page.evaluate("() => { const e = document.querySelector('.page'); return e.scrollHeight <= e.clientHeight + 1 && e.scrollWidth <= e.clientWidth + 1; }")
    png = page.screenshot(type="png", full_page=False)
    strength = rng.uniform(0.3, 1.0) if (noise and rng.random() < 0.7) else 0
    im = noise_image(png, rng, strength)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path, "JPEG", quality=rng.randint(78, 92) if strength else 92)
    return text, fits


DOM_LINES_JS = """() => {
  const out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const n = walker.currentNode, t = n.textContent;
    if (!t.trim()) continue;
    const vertical = getComputedStyle(n.parentElement).writingMode.startsWith('vertical');
    let cur = null;
    for (let i = 0; i < t.length; i++) {
      const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1);
      const rects = r.getClientRects(); if (!rects.length) continue;
      const b = rects[0]; if (b.width === 0 && b.height === 0) continue;
      const key = vertical ? Math.round(b.left / 6) : Math.round(b.top / 6);
      if (cur && cur.key === key) { cur.text += t[i]; cur.x0 = Math.min(cur.x0, b.left); cur.y0 = Math.min(cur.y0, b.top); cur.x1 = Math.max(cur.x1, b.right); cur.y1 = Math.max(cur.y1, b.bottom); }
      else { if (cur) out.push(cur); cur = {text: t[i], key, vertical, x0: b.left, y0: b.top, x1: b.right, y1: b.bottom}; }
    }
    if (cur) out.push(cur);
  }
  return out.map(o => ({text: o.text.trim(), vertical: o.vertical, box: [o.x0, o.y0, o.x1, o.y1]})).filter(o => o.text);
}"""


def dom_lines(page):
    """Perfect-OCR text boxes of the current page: [{text, vertical, box=[x0,y0,x1,y1]}], one per text line/cell fragment."""
    return page.evaluate(DOM_LINES_JS)
