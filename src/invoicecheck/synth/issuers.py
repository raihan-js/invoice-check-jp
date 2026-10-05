"""Fictitious issuers and the synthetic registry that verifies them.

Registration numbers are minted (12 random digits + the real corporate-number check digit) and rejected if they exist in
the real registry snapshot, so no synthetic invoice carries a real company's number. The synthetic registry holds the
issuers plus decoys (other fictitious companies, some expired or revoked) so that 'valid number, wrong company' and
status errors can occur and be detected, and is small enough to publish with the dataset.
"""
from dataclasses import asdict, dataclass

from ..checkdigit import make_corporate_number
from ..registry import Record
from . import names

REG_START, REG_END = "2023-10-01", "2026-09-30"


@dataclass
class Issuer:
    reg_no: str
    name: str
    address: str
    phone: str
    rounding: str          # floor | half_up | ceil: this issuer's convention, fixed
    seal: bool
    split: str
    registered: str = "2023-10-01"


def mint_numbers(rng, n, real_numbers=frozenset()):
    out, seen = [], set()
    while len(out) < n:
        twelve = str(rng.randint(1, 9)) + "".join(rng.choice("0123456789") for _ in range(11))
        num = "T" + make_corporate_number(twelve)
        if num in seen or num in real_numbers:
            continue
        seen.add(num)
        out.append(num)
    return out


def build_issuers(rng, counts, real_numbers=frozenset(), real_names=frozenset()):
    """counts: {split: n_issuers}. Returns issuers (disjoint across splits) and the number of names/numbers rejected."""
    total = sum(counts.values())
    nums = mint_numbers(rng, total, real_numbers)
    nms = names.unique_company_names(rng, total, real_names)
    issuers, i = [], 0
    for split, n in counts.items():
        for _ in range(n):
            issuers.append(Issuer(nums[i], nms[i], names.address(rng), names.phone(rng),
                                  rng.choices(["floor", "half_up", "ceil"], [0.5, 0.35, 0.15])[0], rng.random() < 0.7, split,
                                  rng.choice(["2023-10-01", "2023-10-01", "2024-04-01", "2025-01-15"])))
            i += 1
    return issuers


def build_registry(rng, issuers, n_decoys, real_numbers=frozenset(), real_names=frozenset()):
    """Records for every issuer (active) plus decoys: ~85% active, ~9% expired, ~6% revoked."""
    recs = [Record(i.reg_no, i.name, i.address, "01", i.registered, "", "") for i in issuers]
    taken = {i.reg_no for i in issuers}
    dnums = mint_numbers(rng, n_decoys, real_numbers | taken)
    dnames = names.unique_company_names(rng, n_decoys, real_names | {i.name for i in issuers})
    for num, nm in zip(dnums, dnames):
        r = rng.random()
        reg = rng.choice(["2023-10-01", "2024-04-01"])
        if r < 0.85:
            recs.append(Record(num, nm, names.address(rng), "01", reg, "", ""))
        elif r < 0.94:
            recs.append(Record(num, nm, names.address(rng), "03", reg, "", rng.choice(["2025-03-31", "2026-03-31"])))
        else:
            recs.append(Record(num, nm, names.address(rng), "04", reg, rng.choice(["2025-06-30", "2026-01-31"]), ""))
    return recs


def record_dict(r):
    return asdict(r)
