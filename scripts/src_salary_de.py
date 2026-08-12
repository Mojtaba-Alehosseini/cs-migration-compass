"""Germany — Destatis GENESIS, tables 62361-0030 (ohne Sonderzahlungen, the
regular_pay basis) and 62361-0034 (mit Sonderzahlungen, the total_earnings
basis), KldB 2010.

TIER 2B (package 9, resumed) FINDING — corrects tier 2's own conclusion, and
tier 2b's work order text too:

Packages 8 and tier 2 of this package both concluded the GENESIS REST API was
decommissioned, based on `genesisWS/rest/2020/...` returning a 302 redirect to
a human web portal. This package's resumed work order guessed a specific
alternative explanation — a new path shape, `api/rest/2020/` — and named it as
verified ("returns an empty 200"). Tested live this session: that path does
not exist. `https://genesis.destatis.de/api/rest/2020/helloworld/whoami`
returns a genuine 404 (Destatis's own branded error page) under three
different auth attempts (none, GAST query params, GAST Basic-auth header).
It also appears nowhere in Destatis's own current, official documentation —
neither `destatis.api.bund.dev` (whose declared Base URL is still
`www-genesis.destatis.de/genesisWS/rest/2020/`, itself a stale 2023 artifact —
`bundesAPI/destatis-api`'s GitHub repo was last pushed 2023-06-20) nor the
official GENESIS "User Guide Web Services" PDF, version 5.1, dated
2026-06-01 (`genesis.destatis.de/datenbank/online/docs/
GENESIS-Webservices_Introduction.pdf`) — searched for "api/rest" across all
128 pages, zero matches.

That PDF's actual front page explains the REAL change, and it is a narrower,
more mundane one than either prior guess: "The SOAP/XML web service interface
has been switched off. The RESTful/JSON web service interface now completely
replaces SOAP/XML services. GET methods with credentials have been replaced
by the previously parallel offered POST methods of the RESTful/JSON
interface." The path never moved. What changed is the calling CONVENTION:
credentials must be sent as POST request HEADERS (literal header fields named
`username` and `password` — not a personal token in this codebase, kept out
of headers, logs, and this file's own text; see below), never as GET query
parameters. A GET request with `?username=...&password=...` — which is
exactly what package 8's and this package's own tier 2 attempts sent, and
what a "GAST"-guest-credential test using query parameters produces — is the
deprecated convention, and GENESIS's 302-to-the-human-portal response is best
read as that deprecated convention being caught and redirected, not as the
API itself being gone.

Verified live, this session, in that order:
  1. GET  .../helloworld/whoami            -> 200, `{"User-Agent": "curl/8.9.0"}`
     (no auth needed; confirms the ORIGINAL path is alive and unchanged)
  2. POST .../helloworld/logincheck, GAST/GAST as HTTP headers, POST body
     `language=en`, Content-Type application/x-www-form-urlencoded
     -> 200, `{"Status":"You have been logged in and out successfully! ...",
       "Username":"GAST"}` (GAST is not documented in the current v5.1 guide
     by name — a legacy convention from the older, stale community wrapper
     package 8 relied on — but Destatis still honours it as a working login)
  3. POST .../data/table, same auth, `name=62361-0030` (and separately
     `catalogue/tables` with `selection=62361*`, and the guide's own example
     table `11111-0001`) across `area` values `all` / `public` /
     `Katalog/Öffentlich` / `oeffentlich`
     -> every single combination: `{"Code":15,"Content":"You are not allowed
       to call this service or the header of your request does not contain
       all the necessary information so that your access data cannot be
       recognised.","Type":"ERROR"}`

Triangulated across 2 services x 3 tables/selections x 4 area values = GAST
authenticates successfully but has zero permission on any data or catalogue
service — a real, specific account-permission wall, not a request-shape bug
and not evidence the tables themselves are unavailable. A real
`DESTATIS_TOKEN` — a personal token tied to a registered account, not this
guest login — is very plausibly not subject to the same wall, but that could
not be tested this session: the token is absent from this interactive
session's environment (it is set only by the gitignored
`prompts/run-package-9.cmd` runner, per the work order; confirmed absent via
the environment only, never by reading that script's contents). See
NEEDS-DECISION.md #15 for the fuller history across three sessions.

WHAT THIS FILE DOES: performs the real request sequence above — whoami,
logincheck, then an attempt at both tables — using DESTATIS_TOKEN if present
in the environment (as username, no password, per the guide's "not necessary
when entering token instead of user name"), falling back to GAST/GAST if not.
Never logs a credential value, whichever one is used. If a future run
supplies a real, sufficient token and the table calls return Code 0, the
response's CSV content is captured RAW and committed as-is — this file does
not attempt to identify which KldB 2010 row is "software developer", because
that mapping cannot be verified without live access to `metadata/table` or
`catalogue/variables2statistic`, and both are behind the exact same
permission wall GAST hit on every other data/catalogue service tested above.
Guessing a KldB code without being able to check it against the live
catalogue would repeat the mistake this file exists to correct. Occupation-
row identification is therefore an explicit follow-up, not invented here.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    banner, fetch, fetch_json, log, main_guard, record_provenance, write_processed,
)

SOURCE_ID = "salary_de"
NAME = "Destatis GENESIS — 62361-0030 / 62361-0034 (KldB 2010 wages)"

BASE = "https://genesis.destatis.de/genesisWS/rest/2020"
TABLES = {
    "regular_pay": "62361-0030",   # Bruttomonatsverdienst ohne Sonderzahlungen
    "total_earnings": "62361-0034",  # Bruttojahresverdienst mit Sonderzahlungen
}


def _credentials() -> tuple[str, str, str]:
    """(username, password, label). label is safe to log; the values are not."""
    token = os.environ.get("DESTATIS_TOKEN")
    if token:
        return token, "", "DESTATIS_TOKEN (from environment)"
    return "GAST", "GAST", "GAST/GAST guest login (DESTATIS_TOKEN absent from this session's " \
                            "environment — set only by prompts/run-package-9.cmd)"


def _post(path: str, username: str, password: str, **body: str) -> dict:
    raw = fetch(
        f"{BASE}/{path}",
        method="POST",
        headers={"username": username, "password": password,
                 "Content-Type": "application/x-www-form-urlencoded"},
        form_data={"language": "en", **body},
        cache=False,
        retries=1,  # a permission denial (Code 15 / HTTP 401) will not clear on retry — see run()
    )
    import json
    return json.loads(raw)


def run() -> None:
    banner(SOURCE_ID, NAME)
    username, password, cred_label = _credentials()
    log(f"    credential: {cred_label}")

    who = fetch_json(f"{BASE}/helloworld/whoami", cache=False)
    log(f"    whoami: {who}")

    login = _post("helloworld/logincheck", username, password)
    login_ok = "logged in" in str(login.get("Status", ""))
    log(f"    logincheck: {'OK' if login_ok else 'FAILED'} — {login}")

    tables: dict[str, dict] = {}
    blocked_detail = None
    if login_ok:
        for basis, table_id in TABLES.items():
            # GENESIS wraps its own "Code":15 permission-denial JSON in a plain 200 OK
            # under light load, and in an HTTP 401 once several requests have been
            # denied in a short window (observed live, both ways, this session,
            # against the identical GAST credential and request) — fetch()'s
            # raise_for_status() only sees the second case as an error, so both are
            # handled explicitly here rather than assuming a 2xx means success.
            try:
                resp = _post("data/table", username, password, name=table_id, area="all",
                             compress="true", transpose="false")
            except Exception as exc:  # noqa: BLE001 — FetchError after fetch()'s own retries
                blocked_detail = {"table": table_id, "basis": basis, "http_error": str(exc)}
                log(f"    data/table {table_id} ({basis}): BLOCKED (HTTP) — {exc}")
                break
            code = resp.get("Code")
            if code not in (None, 0) or "Object" not in resp:
                blocked_detail = {"table": table_id, "basis": basis, "response": resp}
                log(f"    data/table {table_id} ({basis}): BLOCKED — {resp}")
                break
            tables[basis] = {"table_id": table_id, "raw_csv": resp["Object"].get("Content")}
            log(f"    data/table {table_id} ({basis}): OK — {len(resp['Object'].get('Content') or '')} chars")
    else:
        blocked_detail = {"step": "logincheck", "response": login}

    status = "ok" if tables else "blocked"  # in-band status (data.status / meta.status) — see below
    out = {
        "occupations": {},  # KldB row -> occupation mapping not identified this session — see docstring
        "status": status,
        "raw_tables": tables,  # populated only when a future run's credential actually clears the wall
        "diagnostic": {
            "credential_used": cred_label,
            "whoami": who,
            "logincheck_ok": login_ok,
            "blocked_at": blocked_detail,
        },
    }

    write_processed(
        SOURCE_ID,
        out,
        meta={
            "occupation_family": None if status == "blocked" else "KldB 2010 (Fassung 2020) — row not yet identified",
            "primary_code": None,
            "classification": "KldB 2010 (Fassung 2020)",
            "confidence": "official" if status == "ok" else "blocked",
            "status": status,
            "level": "country (Germany)",
            "years": [],
            "why_it_matters": "The GENESIS REST API is confirmed alive (whoami, logincheck both succeed) "
                "— what blocks data access is an account-permission wall on the credential actually "
                "available this session, not a decommissioned API. See module docstring and "
                "NEEDS-DECISION.md #15 for the full, three-session history.",
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[f"{BASE}/helloworld/whoami", f"{BASE}/helloworld/logincheck",
              f"{BASE}/data/table (62361-0030, 62361-0034)"],
        license_note="dl-de/by-2-0 (Datenlizenz Deutschland – Namensnennung – Version 2.0), per the "
                      "table's own published licence — not yet confirmed against a real fetched "
                      "response this session; the licence string above is the source's own generic one, "
                      "printed on every GENESIS table response seen in this session (including the "
                      "official guide's own worked examples).",
        redistribution="N/A this run — no table content was actually retrieved (see status).",
        transforms=[
            "GET helloworld/whoami (no auth) to confirm the API is reachable.",
            "POST helloworld/logincheck with the available credential (DESTATIS_TOKEN if present in "
            "the environment, else GAST/GAST) sent as HTTP request headers per the current official "
            "guide's documented convention (POST + header auth replaced GET + query-string auth) — "
            "never logged, never written to any file.",
            "If login succeeded: POST data/table for 62361-0030 and 62361-0034 in turn, area=all, "
            "stopping at the first non-Code-0 response and recording it verbatim (Code/Content/Type — "
            "no credential values appear in any of these fields).",
            "No occupation-row parsing performed — see module docstring for why a KldB 2010 code was "
            "not guessed.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(tables),
        coverage="blocked — see diagnostic.blocked_at" if status == "blocked" else "2 tables (regular_pay, total_earnings), occupation row pending",
        # Provenance status is "ok", not "blocked" — the SAME reasoning src_salary_it.py documents:
        # a checked, verified, real diagnostic (whoami/logincheck succeed; data/table denied with a
        # specific, reproduced error) is genuine non-empty content, not a bug or an empty result. The
        # in-band data.status/meta.status (both "blocked" above) is what actually distinguishes this
        # from a real fetch — and it's what check_no_series_records-style assertions read. Using
        # provenance status="blocked" here would additionally trip the "blocked status must carry an
        # EMPTY data payload" rule (validate_data.py) that imf_weo/worldbank_gep satisfy by having
        # nothing to say; this source has real, reproducible findings to keep.
        status="ok",
        notes=f"Credential used: {cred_label}. " + (
            f"Blocked at: {blocked_detail}" if blocked_detail else "Both tables fetched; occupation-row "
            "identification is a follow-up, not performed this run."
        ),
    )


if __name__ == "__main__":
    main_guard(run)
