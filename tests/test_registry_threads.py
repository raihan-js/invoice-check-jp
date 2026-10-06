"""Registry reads from several threads (the FastAPI thread pool) must be correct. Unserialised, 8 threads over 20,000 records produced thousands of
sqlite3.InterfaceError / SystemError and wrong "not_found" answers for registered numbers."""
import random
from concurrent.futures import ThreadPoolExecutor

from invoicecheck.checkdigit import make_corporate_number
from invoicecheck.registry import Record, Registry


def test_concurrent_reads_are_correct():
    rng = random.Random(1)
    recs = [Record("T" + make_corporate_number("".join(rng.choice("0123456789") for _ in range(12))), f"会社{i}", "", "01", "2023-10-01", "", "")
            for i in range(20000)]
    reg = Registry.from_records(recs)
    numbers = [r.reg_no for r in recs]
    bad = []

    def work(seed):
        r = random.Random(seed)
        for _ in range(1500):
            n = r.choice(numbers)
            try:
                if reg.status(n, "2025-01-01") != "valid" or reg.lookup(n) is None:
                    bad.append(("wrong", n))
            except Exception as e:                                  # noqa: BLE001
                bad.append((type(e).__name__, n))

    with ThreadPoolExecutor(8) as ex:
        list(ex.map(work, range(8)))
    assert not bad, f"{len(bad)} bad reads, e.g. {bad[:3]}"
    assert reg.count() == len(recs)
