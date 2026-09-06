"""Resolve every repository file this site NAMES to a reader into a path they
can open.

NEEDS-DECISION #70, the owner's ruling: the reader-facing copy keeps naming
these files -- this project shows its workings on purpose -- but a named file
should be a file you can go and read, not a string you have to take on faith.
C3b already guarantees each one resolves to a *tracked* file; this turns that
guarantee into a link.

Why a generated map rather than a link built in the component:

  A bare `salary_es.json` does not say where it lives, and 30 of the 425
  candidate files share a basename with another -- almost every dataset exists
  twice, once under `data/` and once as its served copy under
  `site/public/data/`. Guessing in the component would send readers to the
  copy about half the time. The preference rule below is stated once, here,
  and the check downstream reads the same map.

  It carries paths only, never the commit. Baking a SHA into a tracked file
  would make every commit dirty the file it just described. The ref is injected
  at build time instead -- see __REPO_REF__ in vite.config.ts.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# The repo's console-encoding convention: cp1252 stdout cannot print the box
# rule these scripts all use for their summary line.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: F401,E402  (imported for its stdout reconfiguration)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "site" / "src"
OUT = SRC / "data" / "fileRefs.generated.ts"

# The same shape C3b scans for, so the two cannot drift apart in what counts
# as a file token.
FILE_TOKEN = re.compile(
    r"\b[A-Za-z][A-Za-z0-9_./-]*\.(?:json|md|py|csv|ts|tsx|jsonc|yml|yaml)\b"
)

# Named endpoints that belong to somebody else. Teamtailor publishes a
# per-subdomain feed AT /jobs.json; that is the vendor's URL, not a claim about
# a file in this repository. Kept in step with C3b's own exemption list.
EXTERNAL = {"jobs.json"}


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [line for line in out.stdout.splitlines() if line]


def resolve(token: str, tracked: list[str]) -> str | None:
    """Which tracked path a reader means by `token`.

    An exact path wins outright. Otherwise the basename has to match, and where
    several do, the SOURCE copy wins over the served one: `data/cities.json` is
    the file the pipeline writes and the sentence is about, while
    `site/public/data/cities.json` is a build artefact of it. Preferring the
    shorter remaining path breaks any further tie deterministically rather than
    by directory-listing order.
    """
    if token in tracked:
        return token
    matches = [p for p in tracked if p.endswith("/" + token)]
    if not matches:
        return None
    served = "site/public/"
    source_copies = [p for p in matches if not p.startswith(served)]
    pool = source_copies or matches
    return sorted(pool, key=lambda p: (len(p), p))[0]


def tokens_in_source() -> set[str]:
    """Every file token that could reach a reader.

    A superset of what is rendered, deliberately: a reference added to a card
    tomorrow is linked without anyone remembering to update a list. The cost of
    the superset is a few unused entries in a map measured in hundreds of
    bytes, which is the right side of that trade.

    Two places, not one. Scanning only `site/src` missed `hours_worked.json`,
    which a card on /explore/money shows and no TypeScript file contains: that
    sentence is written by the Python pipeline and shipped as DATA. A generator
    that reads only the components would keep linking most of the names and
    silently leave the pipeline-authored ones bare, which is the failure that
    is hardest to notice — some of them are links, so the ones that are not
    look deliberate.
    """
    found: set[str] = set()
    for path in sorted(SRC.rglob("*")):
        if path.suffix not in {".ts", ".tsx"} or path.name == OUT.name:
            continue
        found.update(FILE_TOKEN.findall(path.read_text(encoding="utf-8")))
    for path in sorted((ROOT / "site" / "public" / "data").rglob("*.json")):
        found.update(FILE_TOKEN.findall(path.read_text(encoding="utf-8")))
    return {t for t in found if t not in EXTERNAL}


def main() -> int:
    tracked = tracked_files()
    resolved: dict[str, str] = {}
    unresolved: list[str] = []
    for tok in sorted(tokens_in_source()):
        # An import specifier is not a reference a reader reads; only tokens
        # that name something tracked get a link, and C3b is what guarantees
        # the ones a reader actually SEES are all in this set.
        path = resolve(tok, tracked)
        if path:
            resolved[tok] = path
        else:
            unresolved.append(tok)

    body = "\n".join(f"  {tok!r}: {path!r}," for tok, path in resolved.items())
    OUT.write_text(
        "/* GENERATED by scripts/generate_file_refs.py -- do not edit.\n"
        " *\n"
        " * Every repository file this site names to a reader, mapped to the path\n"
        " * that file actually lives at, so the name can be a link (#70). Paths\n"
        " * only: the commit to pin them to is injected at build time, because a\n"
        " * SHA in a tracked file would dirty that file on every commit.\n"
        " */\n"
        "export const FILE_REF: Record<string, string> = {\n"
        f"{body}\n"
        "}\n".replace("'", "'"),
        encoding="utf-8",
        newline="",
    )

    print("\n── file_refs — repository files named in reader-facing copy")
    print(f"    {len(resolved)} token(s) resolved to a tracked path")
    ambiguous = [
        (t, p) for t, p in resolved.items() if t != p and "/" not in t
    ]
    print(f"    {len(ambiguous)} of them were bare filenames resolved by the preference rule")
    if unresolved:
        print(f"    {len(unresolved)} token(s) in source resolve to nothing and are NOT linked:")
        for t in unresolved[:12]:
            print(f"      {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
