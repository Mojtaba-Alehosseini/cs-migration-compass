"""Pipeline orchestrator — `make pipeline`.

Runs every source script in dependency order, in-process, and prints one summary
table at the end. A failing source never aborts the run: it is recorded with its
status in data/provenance.json and reported here, because a half-updated dataset
with honest provenance beats a run that dies on source #3.

Usage:
    python scripts/pipeline.py                 # everything
    python scripts/pipeline.py world_bank rsf  # only sources matching these substrings
    python scripts/pipeline.py --list          # show what would run
"""
from __future__ import annotations

import importlib
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, load_provenance, log  # noqa: E402

# (module, human label). Order matters: world_bank must precede
# oecd_economic_outlook, which derives its actual/projection cutoff from it.
SOURCES: list[tuple[str, str]] = [
    ("src_city_coordinates", "City coordinates (GeoNames via Open-Meteo)"),
    ("src_world_bank", "World Bank economy history"),
    ("src_eurostat_ict", "Eurostat ICT specialists"),
    ("src_eurostat_employment", "Eurostat total employment"),
    ("src_bis_property", "BIS property prices"),
    ("src_oecd_indicators", "OECD house prices / wages / hours / tax wedge"),
    ("src_fhfa_metro_hpi", "FHFA US metro house prices"),
    ("src_uk_hpi", "UK HPI city house prices"),
    ("src_teranet_hpi", "Teranet Canadian city house prices"),
    ("src_indeed_postings", "Indeed job-postings index"),
    ("src_bls_oews", "BLS OEWS developer wages & employment"),
    ("src_salary_se", "SCB Sweden ICT-occupation wages"),
    ("src_salary_uk", "ONS ASHE UK IT-occupation wages"),
    ("src_salary_ca", "Job Bank Canada software-occupation wages"),
    ("src_salary_dk", "DST Denmark ICT-occupation wages"),
    ("src_salary_no", "SSB Norway ICT-occupation wages"),
    ("src_salary_fi", "Tilastokeskus Finland ICT-occupation wages"),
    ("src_salary_es", "INE Spain IT-occupation wages"),
    ("src_salary_nl", "CBS Netherlands software-developer wages"),
    ("src_salary_au", "ATO Australia software-occupation income"),
    ("src_salary_ie", "CSO Ireland Professional-group earnings"),
    ("src_salary_qa", "Qatar PSA Professionals wage series"),
    ("src_salary_ae", "UAE last-known (2009) wage figures"),
    ("src_salary_it", "Italy no-occupation-series record"),
    ("src_stackoverflow_salaries", "Stack Overflow developer salaries"),
    ("src_un_migrant_stock", "UN DESA migrant stock"),
    ("src_world_happiness", "World Happiness Report"),
    ("src_mipex", "MIPEX integration policy"),
    ("src_rsf_press_freedom", "RSF press freedom"),
    ("src_wikipedia_english", "Wikipedia English speakers"),
    ("src_pdf_indices", "EF EPI + WIPO GII"),
    ("src_numbeo_history", "Numbeo cost-of-living history"),
    # institutional forecasts
    ("src_oecd_economic_outlook", "OECD Economic Outlook (forecast)"),
    ("src_un_wpp", "UN World Population Prospects (forecast)"),
    ("src_imf_weo", "IMF World Economic Outlook (forecast)"),
    ("src_worldbank_gep", "World Bank Global Economic Prospects (forecast)"),
]


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--list" in sys.argv:
        for mod, label in SOURCES:
            print(f"  {mod:32s} {label}")
        return 0

    selected = [(m, l) for m, l in SOURCES if not args or any(a in m for a in args)]
    if not selected:
        log(f"no source matches {args}")
        return 1

    log(f"CS Migration Compass — running {len(selected)} source(s)")
    results: list[tuple[str, str, float]] = []

    for mod_name, label in selected:
        start = time.time()
        try:
            module = importlib.import_module(mod_name)
            importlib.reload(module)
            module.run()
            outcome = "ok"
        except SystemExit as exc:
            outcome = "failed" if exc.code else "ok"
        except Exception as exc:  # noqa: BLE001
            outcome = f"failed: {type(exc).__name__}"
            log(f"    FAILED: {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=3)
        results.append((label, outcome, time.time() - start))

    # Cross-check against what each script actually recorded.
    recorded = {e["source_id"]: e for e in load_provenance()["entries"]}

    log("")
    log("─" * 76)
    log(f"{'source':46s} {'run':10s} {'recorded':10s} {'secs':>6s}")
    log("─" * 76)
    ok = 0
    for label, outcome, secs in results:
        entry = next((e for sid, e in recorded.items() if e["name"].split("—")[0].strip()[:14] in label
                      or label[:14] in e["name"]), None)
        rec_status = entry["status"] if entry else "-"
        if outcome == "ok" and rec_status in ("ok", "partial"):
            ok += 1
        log(f"{label[:46]:46s} {outcome[:10]:10s} {rec_status[:10]:10s} {secs:6.1f}")
    log("─" * 76)
    log(f"{ok}/{len(results)} sources produced data. "
        f"provenance: {PROV_REL}")

    blocked = [e for e in recorded.values() if e["status"] in ("blocked", "unavailable", "failed")]
    if blocked:
        log("")
        log("Sources without data (recorded honestly, never estimated):")
        for e in blocked:
            log(f"  · {e['source_id']:26s} {e['status']:12s} {(e.get('notes') or '')[:90]}")
    return 0


PROV_REL = "data/provenance.json"

if __name__ == "__main__":
    sys.exit(main())
