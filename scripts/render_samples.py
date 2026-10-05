#!/usr/bin/env python3
"""Render one sample invoice per template structure (visual QA) into data/synth/samples/ and a contact sheet."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from playwright.sync_api import sync_playwright  # noqa: E402
from PIL import Image  # noqa: E402

from invoicecheck.synth.invoice import make_invoice  # noqa: E402
from invoicecheck.synth.issuers import build_issuers, build_registry  # noqa: E402
from invoicecheck.synth.render import render_page, H, W  # noqa: E402

rng = random.Random(7)
issuers = build_issuers(rng, {"train": 6})
registry = build_registry(rng, issuers, 40)
combos = [("h_classic", "k0"), ("h_banded", "k2"), ("h_compact", "k1"), ("v_header", "k3"), ("h_twocol", "k5"), ("v_columns", "k6")]
out = Path("data/synth/samples")
out.mkdir(parents=True, exist_ok=True)
paths = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    page = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1.25)
    for i, (s, k) in enumerate(combos):
        g = make_invoice(rng, i, "train", rng.choice(issuers), "株式会社テスト商会", f"{s}__{k}", registry)
        path = out / f"{s}__{k}.jpg"
        render_page(page, g, path, rng, noise=(i % 2 == 1))
        paths.append(path)
    b.close()
ims = [Image.open(p).resize((W // 2, H // 2)) for p in paths]
sheet = Image.new("RGB", (W // 2 * 3, H // 2 * 2), "white")
for i, im in enumerate(ims):
    sheet.paste(im, ((i % 3) * (W // 2), (i // 3) * (H // 2)))
sheet.save(out / "contact_sheet.jpg", quality=90)
print("wrote", [p.name for p in paths], sheet.size)
