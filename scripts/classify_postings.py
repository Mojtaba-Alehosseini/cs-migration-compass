"""Package 12, tier 3 — classifies each posting's own title into the shared
ISCO-08 occupation vocabulary data/occupations.json already defines. THE ONE
PLACE IN THIS PROJECT AN LLM TOUCHES THE DATA, and it is safe for a specific,
narrow reason stated plainly: a job posting's TITLE is public business
information a company chose to publish, not personal data — the paid-tier
requirement that governs the (separate, not-yet-built) CV feature does not
apply here, so the free Gemini tier is fine for this specific task. See
phase-4-salary-and-cv-plan.md S1.3 for why the CV path is different.

THE HARD LIMIT, ENFORCED STRUCTURALLY, NOT JUST BY INSTRUCTION: the model's
own response schema (CLASSIFICATION_SCHEMA below) has no numeric field of
any kind — no salary, no min, no max, nothing a model could fabricate a pay
figure into even if the prompt asked it to. Pay comes ONLY from what a
provider harvester already parsed off the employer's own real data
(postings_common.py's structured/parsed_text compensation, never touched by
this file). A posting's own `compensation` field, once set by its harvester,
is never read OR written here.

BATCHING DISCIPLINE (data-scraper-agent skill, cited by the work order):
batch_size postings per call (never one call per posting — postings_classify
_config.yaml sets this, currently 25), a model fallback chain tried in order
on a 429, max_output_tokens >= 2048, every user-facing filter (which
occupation codes exist to assign, which models to try) in the YAML config,
never a string literal in this file.

REQUIRES GEMINI_API_KEY. If absent, this script logs that plainly and exits
0 with nothing classified — the SAME "environment-only, no silent skip
disguised as success" discipline this pipeline already applies to
DESTATIS_TOKEN (src_salary_de.py). Not run this session: no key was present
in this environment. See NEEDS-DECISION.md for what running it later needs.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, banner, fetch, log, main_guard, record_provenance, write_processed  # noqa: E402

SOURCE_ID = "postings_classifications"
CONFIG_PATH = Path(__file__).resolve().parent / "postings_classify_config.yaml"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _load_postings() -> list[dict]:
    p = PROCESSED / "postings.json"
    if not p.exists():
        log(f"    {p} does not exist yet — run build_postings.py first")
        return []
    doc = json.loads(p.read_text(encoding="utf-8"))
    return doc.get("data", {}).get("postings", [])


def _schema(valid_keys: list[str]) -> dict:
    """Gemini structured-output schema — NO numeric field exists anywhere in
    this shape, on purpose (this file's own module docstring)."""
    return {
        "type": "object",
        "properties": {
            "classifications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "posting_id": {"type": "string"},
                        "occupation_key": {"type": "string", "enum": valid_keys},
                        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    },
                    "required": ["posting_id", "occupation_key", "confidence"],
                },
            },
        },
        "required": ["classifications"],
    }


def _classify_batch(batch: list[dict], cfg: dict, api_key: str) -> list[dict]:
    valid_keys = [o["key"] for o in cfg["target_occupations"]]
    occ_list = "\n".join(f"- {o['key']}: {o['title']}" for o in cfg["target_occupations"])
    titles = "\n".join(f"{p['id']}: {p['title']}" for p in batch)
    prompt = (
        "Classify each job posting title below into EXACTLY ONE of these occupation codes. "
        "A posting's own title is the ONLY information you are given — do not infer or state a "
        "salary figure of any kind; there is no field in your response for one.\n\n"
        f"Occupation codes:\n{occ_list}\n\nPostings (id: title):\n{titles}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": _schema(valid_keys),
            "maxOutputTokens": cfg["max_output_tokens"],
        },
    }
    last_exc = None
    for model in cfg["model_fallback_chain"]:
        try:
            raw = fetch(
                f"{GEMINI_BASE}/{model}:generateContent?key={api_key}",
                method="POST", json_body=body, cache=False, retries=1,
                headers={"Content-Type": "application/json"},
            )
            resp = json.loads(raw)
            text = resp["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)["classifications"]
        except Exception as exc:  # noqa: BLE001 — a 429 or schema miss falls through to the next model
            last_exc = exc
            log(f"    {model} failed ({type(exc).__name__}: {exc}) — trying next in fallback chain")
            time.sleep(1)
    raise RuntimeError(f"every model in the fallback chain failed; last error: {last_exc}")


def _merge_into_postings(classifications: dict[str, dict]) -> None:
    """Writes each posting's own `occupation` field in data/processed/
    postings.json directly -- found missing by this package's own
    adversarial review: NEEDS-DECISION.md #30 originally claimed setting
    GEMINI_API_KEY alone would make classification "run automatically... no
    code change needed," but nothing anywhere actually merged this file's
    own output back into postings.json, so the panel's own Category filter
    would have stayed permanently empty even with a real key. Reads and
    rewrites postings.json's own existing envelope in place (same source_id,
    same meta, same seed_companies/provider_summary/country_counts) --
    this is an enrichment of build_postings.py's own output, not a second
    writer of it, so it does not go through write_processed() under a new
    source_id."""
    if not classifications:
        return
    path = PROCESSED / "postings.json"
    if not path.exists():
        return
    doc = json.loads(path.read_text(encoding="utf-8"))
    updated = 0
    for p in doc.get("data", {}).get("postings", []):
        c = classifications.get(p["id"])
        if c:
            p["occupation"] = c
            updated += 1
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"    merged {updated} occupation classifications into postings.json directly")


def run() -> None:
    banner(SOURCE_ID, "classify posting titles -> ISCO-08 (Gemini, titles only, no pay field)")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log("    GEMINI_API_KEY absent from the environment — not run this session, same "
            "environment-only discipline as DESTATIS_TOKEN. See NEEDS-DECISION.md.")
        write_processed(SOURCE_ID, {"classifications": {}}, meta={
            "status": "not_run", "reason": "GEMINI_API_KEY absent from environment",
        })
        record_provenance(
            source_id=SOURCE_ID, name="Postings occupation classifier (Gemini, titles only)",
            urls=[f"{GEMINI_BASE}/{{model}}:generateContent"],
            license_note="N/A — not run this session.",
            transforms=["Checked for GEMINI_API_KEY; absent, so no classification calls were made."],
            output=f"data/processed/{SOURCE_ID}.json", rows=0, status="blocked",
            coverage="0 — key absent", notes="Run again once GEMINI_API_KEY is set.",
        )
        return

    cfg = _load_config()
    postings = _load_postings()
    if not postings:
        log("    no postings to classify")
        return

    batch_size = cfg["batch_size"]
    classifications: dict[str, dict] = {}
    for i in range(0, len(postings), batch_size):
        batch = postings[i:i + batch_size]
        try:
            results = _classify_batch(batch, cfg, api_key)
        except Exception as exc:  # noqa: BLE001 — one failed batch must not lose every other batch
            log(f"    batch {i // batch_size} failed entirely: {exc}")
            continue
        for r in results:
            classifications[r["posting_id"]] = {"occupation_key": r["occupation_key"], "confidence": r["confidence"]}
        log(f"    batch {i // batch_size + 1}/{-(-len(postings) // batch_size)}: "
            f"{len(results)} classified ({len(classifications)} total so far)")

    write_processed(SOURCE_ID, {"classifications": classifications}, meta={
        "status": "ok", "postings_classified": len(classifications), "postings_total": len(postings),
    })
    _merge_into_postings(classifications)
    record_provenance(
        source_id=SOURCE_ID, name="Postings occupation classifier (Gemini, titles only)",
        urls=[f"{GEMINI_BASE}/{{model}}:generateContent"],
        license_note="Derived — classifies this pipeline's own already-committed posting titles; "
                      "introduces no new redistribution terms.",
        transforms=[
            f"Batched {batch_size} posting titles per call (never one call per posting).",
            "Sent ONLY each posting's own title (no description, no company, no pay data) to Gemini, "
            "with a response schema carrying no numeric field of any kind.",
            f"Tried models in order on failure: {', '.join(cfg['model_fallback_chain'])}.",
        ],
        output=f"data/processed/{SOURCE_ID}.json", rows=len(classifications), status="ok",
        coverage=f"{len(classifications)} of {len(postings)} postings classified",
        notes="Confidence recorded per posting so a wrong mapping is auditable, not invisible.",
    )


if __name__ == "__main__":
    main_guard(run)
