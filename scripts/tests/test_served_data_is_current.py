"""Package 36 — the data the browser is served must be the data the pipeline
built.

Thirty-eight JSON files ship under `site/public/data/`, and twenty-eight of
them differ byte-for-byte from the source they derive from. A hash comparison
cannot tell a deliberate transformation from a stale copy: both look like
"differs". Those are opposite conclusions, and one of them means every figure
verified since package 25 was verified against an older file than the pipeline
computed.

Established by reading `build_site_data.py`, all 28 are transformations:

  * 27 are the same content re-encoded. The publish step writes
    `json.dumps(..., separators=(",", ":"))`, so a pretty-printed source
    becomes a minified served copy. Canonical content — sorted keys, no
    whitespace — is identical in every one.
  * 1 is `history/postings.json`, whose 48,758 rows are deliberately slimmed:
    `title_class` and `duplicate_of` are dropped and `sw: true` is added where
    the classifier says software. Packages 16 and 17 did that because the full
    block cost 15 Lighthouse points and nothing renders it. The served file
    documents the reshape in its own `meta.shipped_row_shape`.

So nothing was stale. This test exists so that stays true, and it is
deliberately NOT a hash comparison: it re-applies the publish step's own
transform to the source and requires the result to match what is served. A
check that merely allowlisted "postings.json may differ" would pass a genuinely
stale postings.json, which is the failure it is here to prevent.

Package 35 shipped a fix to `data/provenance.json` while the served copy stayed
stale, and only noticed by accident. That is the class.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

DATA = ROOT / "data"
PROCESSED = DATA / "processed"
SERVED = ROOT / "site" / "public" / "data"

# Copied byte-for-byte by build_site_data.py's own tail; see the shutil.copyfile
# calls there. provenance.json is the one package 35 left stale.
VERBATIM = (
    "provenance.json", "countries.json", "cities.json", "metrics.json",
    "data-pipeline-sources.json", "pay_composition.json", "occupations.json",
)

# Assembled by the publish step rather than copied, so they have no single
# source file to compare against:
#   core.json            build_core() — countries + cities + metrics + defaults
#   history/openings.json _openings_summary() — a small slice of postings
#   history-manifest.json the index of the history files
GENERATED = ("core.json", "history/openings.json", "history-manifest.json")

# Package 38 (#71): the postings monolith was replaced by a filter index plus
# row chunks. These are compared by RE-APPLYING the real split to the source,
# below — not allowlisted, for the same reason the monolith never was: an
# allowlist would pass a stale index just as happily as a fresh one.
POSTINGS_INDEX = "history/postings_index.json"
POSTINGS_ROWS_PREFIX = "history/postings_rows_"


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def served_files() -> list[Path]:
    return sorted(SERVED.rglob("*.json"))


class TestServedDataIsCurrent(unittest.TestCase):
    def _source_for(self, served: Path) -> Path | None:
        rel = served.relative_to(SERVED).as_posix()
        if rel in GENERATED or rel == POSTINGS_INDEX or rel.startswith(POSTINGS_ROWS_PREFIX):
            return None
        name = served.name
        for cand in (PROCESSED / name, DATA / name):
            if cand.exists():
                return cand
        return None

    def test_the_postings_index_and_chunks_match_the_source(self) -> None:
        """The index and its row chunks are compared by re-running the real
        publish transform on data/processed/postings.json. An allowlist saying
        "these files are allowed to differ" would pass a stale index without
        noticing, which is exactly what this file exists to prevent."""
        from build_site_data import _slim_postings, _split_postings  # noqa: PLC0415

        src = PROCESSED / "postings.json"
        self.assertTrue(src.exists(), "data/processed/postings.json is missing")
        index_doc, chunks = _split_postings(_slim_postings(json.loads(src.read_bytes())))

        served_index = SERVED / POSTINGS_INDEX
        self.assertTrue(served_index.exists(), f"{POSTINGS_INDEX} is not being published")
        self.assertEqual(canon(json.loads(served_index.read_bytes())), canon(index_doc),
                         f"{POSTINGS_INDEX} does not match what the publish step produces from "
                         f"the source — the served index is stale")

        served_chunks = sorted(SERVED.glob("history/postings_rows_*.json"))
        self.assertEqual(len(served_chunks), len(chunks),
                         f"{len(served_chunks)} row chunks served, {len(chunks)} produced from the "
                         f"source — a chunk was added, dropped or left behind")
        bad = []
        for n, (path, expected) in enumerate(zip(served_chunks, chunks)):
            if canon(json.loads(path.read_bytes())) != canon(expected):
                bad.append(path.relative_to(SERVED).as_posix())
        self.assertEqual(bad, [], "row chunks that do not match the source:\n  " + "\n  ".join(bad))

    def test_every_served_file_matches_its_source_after_the_publish_transform(self) -> None:
        problems: list[str] = []
        for served in served_files():
            rel = served.relative_to(SERVED).as_posix()
            src = self._source_for(served)
            if src is None:
                continue
            if served.name in VERBATIM:
                if src.read_bytes() != served.read_bytes():
                    problems.append(f"{rel}: copied verbatim from {src.name} but the bytes differ "
                                    f"— the served copy is stale")
                continue
            source_doc = json.loads(src.read_bytes())
            # Re-apply the real transform, so a genuinely stale postings.json
            # cannot hide behind "that file is allowed to differ".
            if canon(source_doc) != canon(json.loads(served.read_bytes())):
                problems.append(f"{rel}: does not match {src.relative_to(ROOT).as_posix()} "
                                f"after the publish step's own transform")
        self.assertEqual(problems, [],
                         "served data differs from what the pipeline built:\n  " + "\n  ".join(problems))

    def test_no_source_is_newer_than_the_file_served_from_it(self) -> None:
        late = []
        for served in served_files():
            src = self._source_for(served)
            if src is None:
                continue
            # One second of slack: a copy and its source can land in the same
            # write, and filesystems differ on sub-second resolution.
            if src.stat().st_mtime > served.stat().st_mtime + 1:
                late.append(f"{served.relative_to(SERVED).as_posix()}: "
                            f"{src.relative_to(ROOT).as_posix()} is newer by "
                            f"{(src.stat().st_mtime - served.stat().st_mtime) / 60:.1f} min")
        self.assertEqual(late, [],
                         "a source has been rebuilt without republishing — run `npm run build`, "
                         "which runs build_site_data.py:\n  " + "\n  ".join(late))

    def test_every_served_file_is_accounted_for(self) -> None:
        """A served file that nothing generates and nothing copies is its own
        question — it would be data reaching readers from outside the pipeline."""
        orphans = []
        for served in served_files():
            rel = served.relative_to(SERVED).as_posix()
            if rel in GENERATED or self._source_for(served) is not None:
                continue
            # The index and its row chunks are accounted for by
            # test_the_postings_index_and_chunks_match_the_source, which
            # re-derives every one of them from the source.
            if rel == POSTINGS_INDEX or rel.startswith(POSTINGS_ROWS_PREFIX):
                continue
            orphans.append(rel)
        self.assertEqual(orphans, [],
                         "served files with no source and no generator:\n  " + "\n  ".join(orphans))


if __name__ == "__main__":
    unittest.main(verbosity=2)
