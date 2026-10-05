"""Visual skins and template registry. A template id is '<structure>__<skin>', e.g. 'h_classic__k2'.

Train/val/test use TRAIN_STRUCTURES x TRAIN_SKINS (20 templates). The hold-out uses structures and skins never seen in
training (HOLDOUT), so it measures layout generalisation.
"""
GOTHIC = '"Noto Sans CJK JP","Noto Sans JP",sans-serif'
MINCHO = '"Noto Serif CJK JP","Noto Serif JP",serif'

SKINS = {
    "k0": dict(accent="#1f3a68", ink="#111", paper="#ffffff", font=GOTHIC, title="請求書", rule="1px solid #1f3a68", head_bg="#e8edf6", size=13),
    "k1": dict(accent="#7a1f1f", ink="#1a1a1a", paper="#fffdf8", font=MINCHO, title="請 求 書", rule="2px double #7a1f1f", head_bg="#f6ece9", size=13),
    "k2": dict(accent="#146c43", ink="#102016", paper="#fbfffc", font=GOTHIC, title="適格請求書", rule="1px solid #146c43", head_bg="#e5f3ea", size=12),
    "k3": dict(accent="#333333", ink="#000", paper="#ffffff", font=MINCHO, title="御請求書", rule="1px solid #333", head_bg="#eeeeee", size=14),
    "k4": dict(accent="#5b3a8c", ink="#181022", paper="#fdfcff", font=GOTHIC, title="Invoice　請求書", rule="1px dashed #5b3a8c", head_bg="#efe9f8", size=12),
    # hold-out only
    "k5": dict(accent="#b45309", ink="#1c1208", paper="#fffaf3", font=MINCHO, title="請求明細書", rule="2px solid #b45309", head_bg="#fbeedd", size=13),
    "k6": dict(accent="#0e7490", ink="#08202a", paper="#f7fdff", font=GOTHIC, title="適格請求書（兼 納品書）", rule="1px solid #0e7490", head_bg="#dff3f8", size=12),
}
TRAIN_STRUCTURES = ["h_classic", "h_banded", "h_compact", "v_header"]
TRAIN_SKINS = ["k0", "k1", "k2", "k3", "k4"]
HOLDOUT = [("h_twocol", "k5"), ("h_twocol", "k6"), ("v_columns", "k5"), ("v_columns", "k6")]

TRAIN_TEMPLATES = [f"{s}__{k}" for s in TRAIN_STRUCTURES for k in TRAIN_SKINS]
HOLDOUT_TEMPLATES = [f"{s}__{k}" for s, k in HOLDOUT]


def layout_of(template_id):
    return "vertical" if template_id.startswith("v_") else "horizontal"
