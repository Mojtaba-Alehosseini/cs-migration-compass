"""Package 13, Tier 0 — one command for the whole regression suite: every
`test_*.py` in this directory (pipeline-side bugs, real Python functions
called directly) plus `test_ui_regressions.mjs` (client-side TypeScript
bugs, driven against a real served build via Chrome DevTools Protocol —
see that file's own header for why this half can't be a plain Node import
test). Exits non-zero if either half fails or the JS suite is missing, so
CI and a human both get one honest signal rather than two to remember.

    python scripts/tests/run_all.py
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
JS_SUITE = TESTS_DIR / "test_ui_regressions.mjs"


def run_python_suite() -> bool:
    print("=== Python suite (scripts/tests/test_*.py) ===")
    loader = unittest.TestLoader()
    suite = loader.discover(str(TESTS_DIR), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()


def run_js_suite() -> bool:
    print()
    print("=== UI regression suite (scripts/tests/test_ui_regressions.mjs) ===")
    if not JS_SUITE.exists():
        # Explicit, not a silent pass — a missing suite is a coverage gap,
        # not a green run (this project's own no-silent-caps discipline).
        print(f"MISSING: {JS_SUITE} does not exist — UI regression coverage is NOT running.")
        return False
    print("Requires a live preview server: `cd site && npm run build && npm run preview` "
          "(http://localhost:4173/), left running in another shell.")
    proc = subprocess.run(["node", str(JS_SUITE)], cwd=str(TESTS_DIR))
    return proc.returncode == 0


def main() -> int:
    py_ok = run_python_suite()
    js_ok = run_js_suite()
    print()
    print("=== Summary ===")
    print(f"  Python suite: {'PASS' if py_ok else 'FAIL'}")
    print(f"  UI suite:     {'PASS' if js_ok else 'FAIL'}")
    return 0 if (py_ok and js_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
