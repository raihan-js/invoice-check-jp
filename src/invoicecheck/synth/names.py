"""Fictitious Japanese issuers, recipients, addresses and products for synthetic invoices.

Everything here is invented. Company names are composed from parts and (when a registry snapshot is available) any name
that exactly matches a real registered name is rejected, so no synthetic invoice carries a real company's name.
"""
import random

from ..normalize import normalize_name

PREFIX = ["蒼嶺", "朱雀", "紫苑", "瑠璃", "翠光", "銀杏", "琥珀", "葵", "雪華", "碧海", "月詠", "星霜", "楓", "鶴亀", "紅梅", "白雲",
          "常盤", "霧島", "桔梗", "萌黄", "山吹", "藤波", "水無月", "夕凪", "初雁", "長閑", "朝凪", "彩雲", "東雲", "若竹"]
BUSINESS = ["電機", "商事", "工業", "食品", "製作所", "運輸", "建設", "印刷", "文具", "設備", "産業", "物産", "システムズ", "フーズ",
            "テクノ", "ロジスティクス", "エンジニアリング", "サービス", "メディカル", "オフィス", "デザイン", "ケミカル"]
FORMS = ["株式会社", "有限会社", "合同会社"]
PREFECTURES = [("東京都", ["千代田区", "港区", "新宿区", "渋谷区", "品川区", "大田区"]), ("大阪府", ["大阪市北区", "大阪市中央区", "堺市堺区"]),
               ("愛知県", ["名古屋市中区", "豊橋市", "岡崎市"]), ("福岡県", ["福岡市博多区", "北九州市小倉北区", "久留米市"]),
               ("北海道", ["札幌市中央区", "旭川市", "函館市"]), ("宮城県", ["仙台市青葉区", "石巻市"]), ("広島県", ["広島市中区", "福山市"]),
               ("神奈川県", ["横浜市西区", "川崎市川崎区", "相模原市中央区"]), ("京都府", ["京都市中京区", "宇治市"]), ("埼玉県", ["さいたま市大宮区", "川越市"])]
TOWNS = ["本町", "中央", "栄町", "緑町", "新町", "大手町", "旭町", "港町", "桜町", "富士見町", "南町", "北町"]
SURNAMES = ["佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤", "吉田", "山田", "松本", "井上", "木村", "林", "斎藤", "清水"]

# (description, unit-price range, rate): reduced-rate (8%) items are food and drink for take-away/delivery, newspapers
PRODUCTS = [
    ("コピー用紙 A4 500枚", (300, 700), 10), ("ボールペン 10本入", (200, 600), 10), ("ファイルボックス", (400, 1500), 10),
    ("ノートパソコン用スタンド", (1500, 4800), 10), ("USBメモリ 64GB", (900, 2400), 10), ("LANケーブル 5m", (500, 1200), 10),
    ("清掃サービス（月額）", (8000, 40000), 10), ("保守点検費用", (12000, 90000), 10), ("デザイン制作費", (20000, 150000), 10),
    ("運送料", (800, 6000), 10), ("会議室利用料", (3000, 15000), 10), ("ソフトウェア利用料", (5000, 60000), 10),
    ("※ミネラルウォーター 24本", (1200, 2400), 8), ("※弁当（幕の内）", (480, 1200), 8), ("※コーヒー豆 1kg", (1500, 3600), 8),
    ("※菓子折り", (1000, 3500), 8), ("※お茶 20袋", (600, 1800), 8), ("※新聞購読料（月額）", (3500, 4500), 8),
]


def company_name(rng):
    form = rng.choice(FORMS)
    core = rng.choice(PREFIX) + rng.choice(BUSINESS)
    pos = rng.random()
    return f"{form}{core}" if pos < 0.8 else f"{core}{form}"


def person_name(rng):
    return rng.choice(SURNAMES) + rng.choice(["商店", "工務店", "事務所", "設計室", "製作所"])


def address(rng):
    pref, cities = rng.choice(PREFECTURES)
    city = rng.choice(cities)
    return f"{pref}{city}{rng.choice(TOWNS)}{rng.randint(1, 9)}丁目{rng.randint(1, 30)}番{rng.randint(1, 20)}号"


def phone(rng):
    return f"0{rng.choice([3, 6, 52, 92, 11, 22])}-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"


def unique_company_names(rng, n, forbidden=frozenset()):
    """n distinct fictitious company names, none of them (normalised) in `forbidden` (a set of real registered names)."""
    out, seen = [], set()
    while len(out) < n:
        nm = company_name(rng)
        key = normalize_name(nm)
        if key in seen or key in forbidden:
            continue
        seen.add(key)
        out.append(nm)
    return out
