"""Local cache of the NTA qualified-invoice-issuer registry (適格請求書発行事業者公表サイト), corporations only.

Source: monthly all-record download (https://www.invoice-kohyo.nta.go.jp/download/zenken), used under the Public Data
License 1.0 (公共データ利用規約 第1.0版): attribute the source, say when data was processed, and never present it as
government-made. Individuals' records (personal data) are deliberately not loaded. The cache is local only and the
registry is never republished; scraping the site's search function is prohibited and is not done here.

CSV layout (no header, 24 columns, 0-indexed): 1 registration number (T+13 digits), 2 process (01 active, 03 expired,
04 revoked), 4 kind (2 corporation), 6 latest (1 = current row), 7 registered, 9 revoked on, 10 expired on, 11 address,
18 name. A number can appear several times (history); only the latest=1 row is kept.
"""
import csv
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .normalize import normalize_name, strip_company_form

SOURCE_URL = "https://www.invoice-kohyo.nta.go.jp/download/zenken"
ATTRIBUTION = "出典：国税庁適格請求書発行事業者公表サイト（国税庁）(https://www.invoice-kohyo.nta.go.jp/) を加工して作成"
LICENCE = "公共データ利用規約（第1.0版）"

SCHEMA = """
CREATE TABLE IF NOT EXISTS registrants (
  reg_no TEXT PRIMARY KEY, name TEXT, address TEXT, process TEXT,
  registered TEXT, revoked TEXT, expired TEXT
) WITHOUT ROWID;
"""


@dataclass(frozen=True)
class Record:
    reg_no: str
    name: str
    address: str
    process: str          # 01 active, 03 expired, 04 revoked
    registered: str       # ISO date or ""
    revoked: str
    expired: str


def iter_rows(csv_path):
    """Yield (reg_no, name, address, process, registered, revoked, expired) for current corporate rows."""
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.reader(f):
            if len(row) < 19 or row[6] != "1" or row[4] != "2":
                continue
            yield (row[1], row[18], row[11], row[2], row[7], row[9], row[10])


def build_db(csv_paths, db_path, snapshot, downloaded):
    """Build the SQLite cache and return a provenance dict (counts only, no registry content)."""
    db_path = Path(db_path)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    n = 0
    for p in sorted(csv_paths):
        batch = []
        for r in iter_rows(p):
            batch.append(r)
            if len(batch) >= 50000:
                con.executemany("INSERT OR REPLACE INTO registrants VALUES (?,?,?,?,?,?,?)", batch)
                n += len(batch)
                batch = []
        if batch:
            con.executemany("INSERT OR REPLACE INTO registrants VALUES (?,?,?,?,?,?,?)", batch)
            n += len(batch)
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM registrants").fetchone()[0]
    by_process = dict(con.execute("SELECT process, COUNT(*) FROM registrants GROUP BY process").fetchall())
    con.close()
    return {"source": SOURCE_URL, "licence": LICENCE, "attribution": ATTRIBUTION, "snapshot": snapshot,
            "downloaded": downloaded, "scope": "corporations (h_all CSV); individuals and unincorporated associations not loaded",
            "files": [Path(p).name for p in sorted(csv_paths)], "rows_read": n, "registrants": total,
            "by_process": by_process, "redistribution": "none; local cache only"}


class Registry:
    def __init__(self, db_path):
        self.con = sqlite3.connect(str(db_path))

    @classmethod
    def from_records(cls, records):
        """In-memory registry from Record objects (tests, synthetic registries)."""
        self = cls(":memory:")
        self.con.executescript(SCHEMA)
        self.con.executemany("INSERT OR REPLACE INTO registrants VALUES (?,?,?,?,?,?,?)",
                             [(r.reg_no, r.name, r.address, r.process, r.registered, r.revoked, r.expired) for r in records])
        return self

    def count(self):
        return self.con.execute("SELECT COUNT(*) FROM registrants").fetchone()[0]

    def lookup(self, reg_no):
        row = self.con.execute("SELECT * FROM registrants WHERE reg_no = ?", (reg_no,)).fetchone()
        return Record(*row) if row else None

    def status(self, reg_no, on_date):
        """'not_found' | 'not_yet_registered' | 'valid' | 'revoked' | 'expired' on an ISO date (the invoice's date)."""
        rec = self.lookup(reg_no)
        if rec is None:
            return "not_found"
        if rec.registered and on_date < rec.registered:
            return "not_yet_registered"
        if rec.revoked and on_date >= rec.revoked:
            return "revoked"
        if rec.expired and on_date >= rec.expired:
            return "expired"
        return "valid"


def name_match(printed, registry_name):
    """'exact' (same after NFKC/space/(株) normalisation), 'same_core' (same without the legal form), else 'different'."""
    if normalize_name(printed) == normalize_name(registry_name):
        return "exact"
    core_a, core_b = strip_company_form(printed), strip_company_form(registry_name)
    return "same_core" if core_a and core_a == core_b else "different"


def save_provenance(meta, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
