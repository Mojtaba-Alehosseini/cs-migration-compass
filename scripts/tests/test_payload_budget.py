"""Package 37 — what the browser is asked to download, budgeted.

Lighthouse has run on the desktop preset against a localhost preview server for
fourteen routes since package 22, and that is precisely the condition under
which a large payload is free. `/openings` scored 100 while shipping 2.4 MiB
gzipped, because on localhost the transfer is instant and the desktop CPU parses
24 MiB in half a second.

Measured on a throttled phone (CDP, 390x844, CPU 4x):

    Slow 4G   fetch 42.0 s   parse 0.5 s   -> the fetch dominates by 79x
    Fast 4G   fetch  5.4 s   parse 0.6 s   -> the fetch dominates by 9.4x

So the cost is bytes on the wire, not parse time, and the gate has to be able
to see bytes. This test is deliberately a SIZE budget rather than a timing
assertion: a timing gate on a shared CI runner is a flake generator, and the
thing that actually regressed in package 16 was a payload growing, which is
exactly what a size budget catches.

Budgets are gzipped bytes, since that is what crosses the network, with
headroom for ordinary data growth. Raising one is a deliberate act: it means
someone decided the extra download is worth it, which is the decision this file
exists to force.
"""
from __future__ import annotations

import gzip
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVED = ROOT / "site" / "public" / "data"

# gzipped bytes. Recorded 2026-09-05 with ~12% headroom over the measured size.
BUDGETS = {
    "history/postings.json": 2_800_000,   # measured 2,462,613 — the site's heaviest by far
    "core.json": 110_000,                 # measured  ~89,000 — the only blocking fetch
    "history/oecd_indicators.json": 260_000,
    "history/postings_seed_summary.json": 90_000,
    "history/bis_property_prices.json": 90_000,   # measured 75,475
    "countries.json": 55_000,                     # measured 44,803
    "provenance.json": 50_000,                    # measured ~35,000
}


class TestPayloadBudget(unittest.TestCase):
    def test_no_served_payload_exceeds_its_budget(self) -> None:
        over = []
        for rel, budget in BUDGETS.items():
            p = SERVED / rel
            if not p.exists():
                over.append(f"{rel}: missing — a budgeted payload disappeared")
                continue
            size = len(gzip.compress(p.read_bytes(), 9))
            if size > budget:
                over.append(f"{rel}: {size:,} gzipped bytes exceeds the {budget:,} budget "
                            f"by {size - budget:,} ({100 * size / budget - 100:.0f}% over)")
        self.assertEqual(over, [],
                         "a served payload grew past its budget. On Slow 4G every 64 KB gzipped is "
                         "about another second of staring at a spinner:\n  " + "\n  ".join(over))

    def test_the_budget_still_covers_the_heaviest_files(self) -> None:
        """A budget nobody updates stops describing the site. If a served file
        is heavier than the smallest thing being budgeted and is not itself
        budgeted, the list has gone stale."""
        smallest_budgeted = min(BUDGETS.values())
        unbudgeted = []
        for p in SERVED.rglob("*.json"):
            rel = p.relative_to(SERVED).as_posix()
            if rel in BUDGETS:
                continue
            size = len(gzip.compress(p.read_bytes(), 9))
            if size > smallest_budgeted:
                unbudgeted.append(f"{rel}: {size:,} gzipped, heavier than the smallest budget "
                                  f"({smallest_budgeted:,}) and not budgeted")
        self.assertEqual(unbudgeted, [],
                         "these payloads are heavy enough to deserve a budget:\n  " + "\n  ".join(unbudgeted))


if __name__ == "__main__":
    unittest.main(verbosity=2)
