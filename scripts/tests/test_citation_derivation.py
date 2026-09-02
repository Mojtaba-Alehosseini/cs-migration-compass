"""Package 27, Tier 5 — make the citation-heuristic class of defect harder to
reintroduce. NEEDS-DECISION #59/#60 found four shapes of the same root cause
(a citation picked by substring, array position, or a hardcoded literal,
instead of derived from a per-entity record): "talent.com + PayScale" on
every city regardless of what its own note said (defect A); GulfTalent
matched as "talent.com" because `'gulftalent.com'.includes('talent.com')` is
true (also A); `country.sources[0]`/`city.sources[0]` linking whichever URL a
country's harvesters appended first, regardless of the metric asking
(defect C); real arithmetic rendered through the bare-citation component
instead of the disclosed-calculation one (defect D).

These are source-code-shape assertions (grep site/src, not render the site) —
proportionate to what package 25's own C1-C6 already do: narrow, mechanical,
targeted at a specific defect shape, not a general-purpose linter. Paths are
resolved from this file's own location, not the working directory CI or a
local run happens to be invoked from — package 25's own Gate 12 lost time to
exactly that class of bug (REPORT-P25.md).

Run directly (`python scripts/tests/test_citation_derivation.py`) or via
scripts/tests/run_all.py.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE_SRC = ROOT / "site" / "src"
CITIES = ROOT / "data" / "cities.json"
WAGE_DIST = ROOT / "data" / "processed" / "wage_distribution.json"

# Files where a bare `.includes(<host-fragment>)` or a literal company name is
# the SANCTIONED implementation, not a regression — format.ts's own
# sourceName() host map, and registry.ts's own citySalarySource()/
# countryImmigrationSource(), which are what every other component is
# supposed to call instead of matching a URL themselves.
ALLOWLISTED_FOR_LITERALS = {"format.ts", "registry.ts"}


def _ts_files() -> list[Path]:
    return [p for p in SITE_SRC.rglob("*.ts*") if p.is_file()]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _code_lines(p: Path) -> list[tuple[int, str]]:
    """(line_number, text) for lines that are not a `//` or `/* ... */`-style
    comment line — a crude, line-based filter (no real tokenizer), good
    enough to keep this file's own explanatory comments (which have to be
    able to name the exact pattern they warn about) from tripping the checks
    below on themselves."""
    out = []
    for i, line in enumerate(_read(p).splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue
        out.append((i, line))
    return out


class TestNoSubstringHostMatching(unittest.TestCase):
    """Defect A's own mechanism: `s.includes('talent.com')` is also true for
    `s.includes('gulftalent.com')`, because the substring is *contained*, not
    matched as a host. `sourceUrlByHost()` (format.ts) is the sanctioned
    replacement — exact hostname equality, never substring. This test does
    not care WHAT the substring is; it looks for the SHAPE (`.find(` +
    `.includes(` on what would be a URL list), because the exact string that
    breaks next time will not be "talent.com" again."""

    def test_no_find_includes_pattern_in_a_sources_lookup(self) -> None:
        pattern = re.compile(r"\.find\(\s*\(?\w*\)?\s*=>\s*\w*\.includes\(")
        offenders = []
        for f in _ts_files():
            for i, line in _code_lines(f):
                if pattern.search(line):
                    offenders.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()}")
        self.assertEqual(offenders, [],
                          "a `.find(s => s.includes(...))` lookup over a sources[] array can match "
                          "a different company whose domain merely CONTAINS the search string (the "
                          "GulfTalent defect) — use sourceUrlByHost() (format.ts), exact host only:\n"
                          + "\n".join(offenders))


class TestNoPositionalSourcePick(unittest.TestCase):
    """Defect C: `country.sources[0]` / `city.sources[0]` links whichever URL
    a country or city's own harvesters happened to append first — no
    ordering by relevance is recorded, so position 0 is arbitrary with
    respect to any specific figure. DataMethods.tsx's own `e.urls[0]` is
    deliberately NOT the same risk (see its own module comment) — `e` there
    is one provenance.json entry already scoped to a single source_id, so
    every URL in it is that one source's own; excluded by file name, not by
    blanket exemption."""

    ALLOWLISTED_FILES = {"DataMethods.tsx"}

    def test_no_bare_positional_index_into_a_sources_array(self) -> None:
        pattern = re.compile(r"\bsources\??\.\[0\]|\bsources\[0\]")
        offenders = []
        for f in _ts_files():
            if f.name in self.ALLOWLISTED_FILES:
                continue
            for i, line in _code_lines(f):
                if pattern.search(line):
                    offenders.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()}")
        self.assertEqual(offenders, [],
                          "country.sources[0] / city.sources[0] links whichever URL a harvester "
                          "happened to append first, regardless of which figure is asking — the "
                          "same defect as the GulfTalent match, a position standing in for a "
                          "recorded relationship. Record which source belongs to which figure "
                          "instead (see citySalarySource(), countryImmigrationSource() in "
                          "registry.ts):\n" + "\n".join(offenders))


class TestNoHardcodedMultiCompanyLiteral(unittest.TestCase):
    """Defect A's own surface symptom: `name: 'talent.com + PayScale'`
    hardcoded in three separate components, asserted for every city
    regardless of what that city's own record said. A literal naming two-plus
    companies joined by "+"/"and", OUTSIDE the one function that is now
    allowed to know company names (citySalarySource(), which switches on
    per-city recorded data, not a constant), is exactly that shape
    recurring."""

    def test_no_compound_company_literal_outside_the_sanctioned_source(self) -> None:
        pattern = re.compile(r"""['"][^'"]*\b\w+\.\w{2,4}\s*\+\s*\w+['"]""")
        offenders = []
        for f in _ts_files():
            if f.name in ALLOWLISTED_FOR_LITERALS:
                continue
            for i, line in _code_lines(f):
                if pattern.search(line):
                    offenders.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()}")
        self.assertEqual(offenders, [],
                          "a citation name that hardcodes two-plus company names joined by '+' is "
                          "asserted for every entity it renders on, regardless of what that "
                          "entity's own record says was actually used — the exact shape of the "
                          "'talent.com + PayScale' defect. Derive it per-entity instead:\n"
                          + "\n".join(offenders))


class TestEveryCityHasAVerifiedSalarySource(unittest.TestCase):
    """Regression pin for Tier 1's own data completeness — a city added later
    without a primary_source silently falls into citySalarySource()'s
    default branch (name: 'Compiled estimate'), which is honest but should
    be a deliberate classification, not a silent gap. Every one of the 73
    cities this pipeline currently carries must have one."""

    def test_every_city_declares_a_primary_source(self) -> None:
        cities = json.loads(CITIES.read_text(encoding="utf-8"))["records"]
        valid = {
            "payscale_nolink", "payscale_linked", "talentcom_nolink", "levelsfyi_linked",
            "bls_linked", "indeed_linked", "indeed_seek_linked", "compiled",
        }
        missing = [c["id"] for c in cities if c.get("salary_usd_year", {}).get("primary_source") not in valid]
        self.assertEqual(missing, [], f"cities with no (or an invalid) primary_source: {missing}")


class TestNativeBasisDistinguishesRealCases(unittest.TestCase):
    """Regression pin for Tier 3 — a coarser version of
    test_wage_distribution_extraction.py's own dedicated tests, checked here
    against the actual COMMITTED wage_distribution.json rather than the
    extractor in isolation, so a rebuild that silently drops the field is
    also caught."""

    def test_committed_file_carries_native_basis_and_it_varies(self) -> None:
        countries = json.loads(WAGE_DIST.read_text(encoding="utf-8"))["data"]["countries"]
        by_source = {c["source_id"]: c["native"].get("native_basis") for c in countries}
        self.assertIn("native_basis", next(c for c in countries if c["source_id"] == "salary_no")["native"],
                       "native_basis is missing from the committed file — did the build run?")
        self.assertEqual(by_source.get("salary_no"), "total_earnings")
        self.assertEqual(by_source.get("salary_fi"), "regular_pay")
        self.assertEqual(by_source.get("salary_dk"), None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
