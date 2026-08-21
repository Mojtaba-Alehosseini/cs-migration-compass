"""Package 14, Tier 0.3 — one-time recovery for companies a destructive
refresh already erased BEFORE the Tier 0.2 additive fix existed to protect
them. Not part of the regular weekly harvest (postings-refresh.yml): this
is for the specific, disclosed incident Finding 3 describes, and for any
future one like it, run by hand.

WHAT THIS DOES: given a provider and a git ref to treat as "known good,"
diffs that ref's own committed verified_companies against the CURRENTLY
committed set, re-probes exactly the tokens present in the ref but absent
now — live, against the real API, using that provider's OWN fetch/parse
functions (imported, never reimplemented) — and restores whichever still
respond. A token that no longer responds is left alone: 0.3's own
instruction is "restore the ones that still respond," not resurrect one
that is genuinely gone.

Currently wired for Ashby only, the provider this incident actually hit
(the other three seed-hint-driven providers had 0 lost companies at the
time this was written — see REPORT-P14.md gate 1). Extending to another
provider means importing its own per-token fetch+normalise functions the
same way and adding one branch to _PROVIDER_FETCHERS below; the merge and
reporting logic is already provider-agnostic.

    python scripts/recover_lost_postings_companies.py ashby 34acb04
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, banner, log, record_provenance, write_processed  # noqa: E402
from postings_common import merge_verified_companies  # noqa: E402


def _committed_verified_companies_at_ref(source_id: str, ref: str) -> dict[str, dict]:
    proc = subprocess.run(
        ["git", "show", f"{ref}:data/processed/{source_id}.json"],
        capture_output=True, text=True, encoding="utf-8", cwd=Path(__file__).resolve().parent.parent,
    )
    if proc.returncode != 0:
        raise SystemExit(f"git show {ref}:data/processed/{source_id}.json failed: {proc.stderr.strip()}")
    doc = json.loads(proc.stdout)
    return doc.get("data", {}).get("verified_companies", {}) or {}


def _committed_verified_companies_now(source_id: str) -> dict[str, dict]:
    p = PROCESSED / f"{source_id}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("data", {}).get("verified_companies", {}) or {}


def _recover_ashby(lost_tokens: list[str]) -> tuple[dict[str, dict], list[dict]]:
    import src_postings_ashby as ashby  # noqa: E402  (module-level state, e.g. OUT_DIR — import, don't reimplement)
    this_run_verified: dict[str, dict] = {}
    new_postings: list[dict] = []
    responded, still_gone = 0, 0
    for i, token in enumerate(lost_tokens, start=1):
        # "Re-probe... restore the ones that still respond" means a REAL
        # liveness check today, not a replay of _fetch_board's own normal
        # cache (found live while running this the first time: the local
        # cache for these tokens was from 16 August, 5 days stale by the
        # time this recovery ran, and every one of the 558 "responded" —
        # 100% is a red flag for "this actually just read old files," not
        # a real re-probe). Delete any existing cache entry first so
        # _fetch_board has no choice but to hit the live API.
        cache_file = ashby.OUT_DIR / f"{token}.json"
        cache_file.unlink(missing_ok=True)
        doc = ashby._fetch_board(token)
        if not doc or not doc.get("jobs"):
            still_gone += 1
        else:
            rows = ashby._normalise(token, doc)
            if rows:
                new_postings.extend(rows)
                this_run_verified[token] = {
                    "company": doc.get("organizationName") or None, "provider": "ashby",
                    "job_count": len(rows),
                }
                responded += 1
            else:
                still_gone += 1
        if i % 50 == 0:
            log(f"    ...{i}/{len(lost_tokens)} re-probed, {responded} responded, {still_gone} still gone")
    log(f"    recovery probe complete: {responded} of {len(lost_tokens)} lost companies still respond")
    return this_run_verified, new_postings


_PROVIDER_FETCHERS = {"ashby": _recover_ashby}


def run(provider: str, baseline_ref: str) -> None:
    source_id = f"postings_{provider}"
    banner(f"recover:{provider}", f"Tier 0.3 — restore companies verified at {baseline_ref} but lost since")
    if provider not in _PROVIDER_FETCHERS:
        raise SystemExit(f"no recovery fetcher wired for {provider!r} — see this file's own module docstring")

    baseline = _committed_verified_companies_at_ref(source_id, baseline_ref)
    current = _committed_verified_companies_now(source_id)
    lost_tokens = sorted(set(baseline.keys()) - set(current.keys()))
    log(f"    {baseline_ref}: {len(baseline)} verified — currently committed: {len(current)} verified "
        f"— {len(lost_tokens)} lost, re-probing all of them live")

    if not lost_tokens:
        log("    nothing lost relative to this baseline — nothing to recover")
        return

    this_run_verified, new_postings = _PROVIDER_FETCHERS[provider](lost_tokens)

    # merge_verified_companies is the SAME additive merge the regular
    # harvester now uses — a recovered company enters exactly like a
    # brand-new one (it is not in `current`, the "previous" argument
    # here), no special-casing needed; a lost token that still doesn't
    # respond is simply never added, matching "restore the ones that
    # still respond" precisely.
    merged_companies, _removed = merge_verified_companies(current, probed_tokens=set(lost_tokens),
                                                            this_run_verified=this_run_verified)

    existing = json.loads((PROCESSED / f"{source_id}.json").read_text(encoding="utf-8"))
    existing_postings = existing.get("data", {}).get("postings", [])
    combined_postings = existing_postings + new_postings

    write_processed(source_id, {
        "postings": combined_postings,
        "verified_companies": merged_companies,
    }, meta={
        **{k: v for k, v in (existing.get("meta") or {}).items()
           if k not in ("verified_companies", "postings_count")},
        "verified_companies": len(merged_companies),
        "postings_count": len(combined_postings),
        "compensation_present_count": sum(1 for p in combined_postings if p.get("compensation")),
        "tier_0_3_recovery": {
            "baseline_ref": baseline_ref, "lost_tokens_probed": len(lost_tokens),
            "restored": len(this_run_verified), "still_gone": len(lost_tokens) - len(this_run_verified),
        },
    })
    record_provenance(
        source_id=source_id,
        name=f"{provider.title()} — Tier 0.3 one-time recovery of companies lost before the Tier 0.2 fix",
        urls=[],
        license_note="Inherits the provider's own regular harvester license terms — no new source, "
                      "just a re-probe of previously-legitimate boards.",
        redistribution="Same as the regular harvester for this provider.",
        transforms=[
            f"Diffed {baseline_ref}'s own committed verified_companies against the current file: "
            f"{len(lost_tokens)} companies present then, absent now.",
            f"Re-probed every one of those {len(lost_tokens)} tokens live against the real API, using "
            "the provider's own regular harvester fetch/normalise functions.",
            f"Restored {len(this_run_verified)} that still respond; left {len(lost_tokens) - len(this_run_verified)} "
            "absent — genuinely gone, not resurrected with stale data.",
        ],
        output=f"data/processed/{source_id}.json",
        rows=len(combined_postings),
        coverage=f"{len(merged_companies)} verified companies after recovery",
        notes="One-time recovery run (Package 14, Tier 0.3) — not part of the regular scheduled harvest.",
    )
    log(f"    DONE — verified_companies {len(current)} -> {len(merged_companies)}, "
        f"postings {len(existing_postings)} -> {len(combined_postings)}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: python {Path(__file__).name} <provider> <baseline_git_ref>")
    run(sys.argv[1], sys.argv[2])
