"""Generate docs/SOURCES.md from data/provenance.json — `make docs`.

The source list is never hand-maintained: it is whatever the pipeline actually
recorded on its last run, including the sources that failed. A hand-written list
drifts, and a list that omits failures is the dishonest version.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA, ROOT, load_provenance, log  # noqa: E402

OUT = ROOT / "docs" / "SOURCES.md"

STATUS_LABEL = {
    "ok": "live",
    "partial": "partial",
    "blocked": "blocked",
    "unavailable": "unavailable",
    "failed": "failed",
}


def main() -> int:
    prov = load_provenance()
    entries = sorted(prov["entries"], key=lambda e: (e["status"] != "ok", e["source_id"]))
    live = [e for e in entries if e["status"] in ("ok", "partial")]
    missing = [e for e in entries if e["status"] not in ("ok", "partial")]

    spec = json.loads((DATA / "data-pipeline-sources.json").read_text(encoding="utf-8"))
    spec_by_id = {s["id"]: s for s in spec["sources"]}

    L: list[str] = []
    L.append("# Sources")
    L.append("")
    L.append("<!-- GENERATED FILE — do not edit by hand.")
    L.append("     Regenerate with `make docs` (scripts/generate_sources_doc.py).")
    L.append("     Content comes from data/provenance.json, written by the pipeline itself. -->")
    L.append("")
    L.append(f"Last pipeline run: **{prov.get('updated_at', 'unknown')}**")
    L.append("")
    L.append(f"{len(live)} datasets produced data. {len(missing)} did not — those are listed too, "
             "because a source list that hides its failures is not a source list.")
    L.append("")
    L.append("Every figure on the site traces to one of these. Where a source is missing, the site "
             "shows “no data” and names the absent figure; it never substitutes an estimate.")
    L.append("")

    # ---- licence summary -------------------------------------------------
    L.append("## Licences at a glance")
    L.append("")
    L.append("The MIT licence in `LICENSE` covers the **code** only. Data belongs to the "
             "organisations below and carries their terms.")
    L.append("")
    L.append("| Dataset | Licence / terms | What this repo redistributes |")
    L.append("| --- | --- | --- |")
    for e in entries:
        L.append(f"| {e['name']} | {e['license']} | {e.get('redistribution') or 'raw committed'} |")
    L.append("")

    # ---- working sources -------------------------------------------------
    L.append("## Live sources")
    L.append("")
    for e in live:
        s = spec_by_id.get(e["source_id"], {})
        L.append(f"### {e['name']}")
        L.append("")
        L.append(f"- **Status** — {STATUS_LABEL.get(e['status'], e['status'])}")
        L.append(f"- **Coverage** — {e.get('coverage') or 'not recorded'}")
        if e.get("rows") is not None:
            L.append(f"- **Rows processed** — {e['rows']:,}")
        L.append(f"- **Fetched** — {e['fetched_at']}")
        L.append(f"- **Licence** — {e['license']}")
        L.append(f"- **Output** — `{e.get('output')}`")
        L.append(f"- **Fetch script** — `scripts/src_{e['source_id']}.py`"
                 if (ROOT / "scripts" / f"src_{e['source_id']}.py").exists()
                 else "- **Fetch script** — see `scripts/`")
        if s.get("historical_range"):
            L.append(f"- **Historical range** — {s['historical_range']}")
        L.append("")
        L.append("**URLs**")
        L.append("")
        for u in e["urls"][:6]:
            L.append(f"- <{u}>" if u.startswith("http") else f"- `{u}`")
        if len(e["urls"]) > 6:
            L.append(f"- …and {len(e['urls']) - 6} more of the same shape")
        L.append("")
        L.append("**What we do to it**")
        L.append("")
        for t in e["transforms"]:
            L.append(f"1. {t}")
        L.append("")
        if e.get("notes"):
            L.append(f"> {e['notes']}")
            L.append("")
        if s.get("notes"):
            L.append(f"<details><summary>Verification notes from the source survey</summary>\n\n{s['notes']}\n\n</details>")
            L.append("")

    # ---- missing sources -------------------------------------------------
    if missing:
        L.append("## Sources we could not get")
        L.append("")
        L.append("These are documented at the same level of detail as the working ones. The site "
                 "renders nothing for them rather than filling the gap.")
        L.append("")
        for e in missing:
            L.append(f"### {e['name']} — {STATUS_LABEL.get(e['status'], e['status'])}")
            L.append("")
            L.append(f"- **Why** — {e.get('notes') or 'not recorded'}")
            L.append(f"- **Attempted** — {e['fetched_at']}")
            for u in e["urls"][:4]:
                L.append(f"- Tried: <{u}>" if u.startswith("http") else f"- Tried: `{u}`")
            L.append("")

    # ---- manual drop-ins -------------------------------------------------
    L.append("## Manual drop-in sources")
    L.append("")
    L.append("Some well-known datasets are paid, gated, or unreachable from automated builds. They "
             "are supported as documented hand-placed files rather than pretended-away.")
    L.append("")
    L.append("| Source | How to obtain it | Where to put it |")
    L.append("| --- | --- | --- |")
    L.append("| IMF World Economic Outlook | imf.org → Publications → WEO → *World Economic Outlook "
             "Databases* → download the entire database (free, tab-delimited). | `data/manual/imf_weo.json` "
             "— see the shape documented at the top of `scripts/src_imf_weo.py`. |")
    L.append("| EIU liveability & cost of living | Paid report. Quote the headline figure only. | "
             "Forecast card in `data/manual/forecast_cards.json` with source and date. |")
    L.append("| Knight Frank / CBRE / JLL housing outlooks | Free registration, per-report PDFs. | "
             "Forecast card, attributed and dated. |")
    L.append("| Gartner / IDC tech market forecasts | Paid. Press releases carry citable headline numbers. | "
             "Forecast card, attributed and dated. |")
    L.append("| StatCan occupation counts | Table 14-10-0335-01, inactive since 2022. | "
             "`data/manual/` drop-in; documented as historical only. |")
    L.append("| Jobs and Skills Australia / ABS | ABS labour-force releases. | `data/manual/` drop-in. |")
    L.append("")
    L.append("Forecast cards are rendered as attributed quote-cards — a headline figure, the "
             "institution, and the date — never merged into a chart line.")
    L.append("")

    L.append("## Confidence tiers")
    L.append("")
    metrics = json.loads((DATA / "metrics.json").read_text(encoding="utf-8"))
    for tier, desc in metrics["meta"]["confidence_tiers"].items():
        L.append(f"- **{tier}** — {desc}")
    L.append("")
    L.append("## Staleness rules")
    L.append("")
    L.append("A figure older than its rule shows a warning on the site rather than being hidden.")
    L.append("")
    for k, v in metrics["meta"]["staleness_rules_months"].items():
        L.append(f"- `{k}` — warn after {v} months")
    L.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    log(f"wrote {OUT.relative_to(ROOT)} ({len(live)} live, {len(missing)} missing)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
