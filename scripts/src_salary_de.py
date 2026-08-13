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

PACKAGE 11 UPDATE — the environment-only rule is relaxed, once, for this one
credential. Four sessions (packages 8, 9-tier-2, 9-tier-2b, 10) checked only
`os.environ`, found DESTATIS_TOKEN absent every time (every one of those
sessions launched interactively, never through the gitignored
`prompts/run-package-N.cmd` runner that actually sets it), and produced three
different wrong conclusions about the API in the process — the rule
protecting a secret from ever appearing in a transcript cost four sessions
without a real credential ever being tried against the actual permission
wall. Package 11's own work order authorises a narrow, explicit exception:
if DESTATIS_TOKEN is absent from the environment, this file may read it from
`prompts/run-package-11.cmd` (gitignored, never committed) — and ONLY that
one variable, from ONLY that one file, for ONLY this credential. The value
is loaded into a local variable and used; it is never printed, logged,
written to any other file, or returned from any function other than
`_credentials()`, whose own docstring marks exactly which of its return
values are safe to log.

PACKAGE 11, SAME SESSION — the registered token cleared the wall GAST hit on
every prior attempt. `logincheck` succeeded and BOTH `data/table` calls
returned real content (Code 0) on the first try, no retries needed. The
"occupation-row identification needs live catalogue access" problem the
paragraph above worried about turned out not to apply: each table's own CSV
rows carry Destatis's own official ENGLISH occupation titles alongside the
KldB 2010 code (e.g. "KB10-434;  Occup. in software development and
programming"), so the row this pipeline needs is identified by reading the
table's own published label, not by guessing a code number and hoping it
matches a catalogue entry this session still couldn't reach. KB10-434
("Occup. in software development and programming") is Destatis's own
3-digit-level rollup — it combines software development (KB10-434xx, three
skill levels) with programming (KB10-43423) and management (KB10-43494) as
ONE published total, not something this pipeline aggregates by hand from
finer rows. KldB 2010's own numbering does not reuse ISCO-08's numbers the
way SE/DK/NO/FI's national codes do (no "43" = ISCO "25" correspondence to
lean on), and no official KldB-to-ISCO-08 concordance table was located or
checked this session — so this mapping is marked 2-digit confidence
(isco08:25, "ICT professionals"), the same ceiling Spain's own CNO-11 label
match sits at for the identical reason: real, official, English-labelled
correspondence, but not a checked numeric concordance. See
data/occupations.json's own mapping entry and NEEDS-DECISION.md.

WHAT THIS FILE DOES: performs the real request sequence above — whoami,
logincheck, then both tables — using DESTATIS_TOKEN if present in the
environment, else from prompts/run-package-11.cmd if that file sets it,
else falling back to GAST/GAST (as username, no password, per the guide's
"not necessary when entering token instead of user name"). Never logs a
credential value, whichever one is used — GENESIS's own logincheck response
echoes the submitted username field back verbatim, so every response this
file touches is redacted before it is logged OR persisted (see _redact()
below; a real, one-time leak into THIS session's own tool output happened
before that redaction existed — recorded in NEEDS-DECISION.md #25, not
hidden). On success, the KB10-434 row is located in each table's own CSV by
matching Destatis's own code column exactly (not a substring search), the
Total-column figures are parsed into this pipeline's own dispersion shape,
and only that one matched CSV line per table is kept for citation — the
full ~1,500-occupation-row response is not persisted, matching this
pipeline's own practice of narrowing a national classification's raw
response down to the occupation family actually used (Sweden's SCB
response is trimmed to codes 2511-2519 the same way).
"""
from __future__ import annotations

import csv
import io
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
KLDB_CODE = "KB10-434"  # "Occup. in software development and programming" — see module docstring


def _token_from_prompts_cmd() -> str | None:
    """Package 11's own narrow, explicit exception to the environment-only
    rule (see module docstring): reads ONLY a `set DESTATIS_TOKEN=...` line
    from ONLY prompts/run-package-11.cmd (gitignored, never committed), and
    returns ONLY the value — never the rest of the file's contents, never
    printed or logged by this function itself. Callers must not log the
    return value; only _credentials()'s own `label` is safe for that."""
    cmd_path = Path(__file__).resolve().parent.parent / "prompts" / "run-package-11.cmd"
    if not cmd_path.exists():
        return None
    for line in cmd_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("set destatis_token="):
            value = stripped.split("=", 1)[1].strip().strip('"')
            return value or None
    return None


def _credentials() -> tuple[str, str, str]:
    """(username, password, label). label is safe to log; the values are not."""
    token = os.environ.get("DESTATIS_TOKEN")
    if token:
        return token, "", "DESTATIS_TOKEN (from environment)"
    token = _token_from_prompts_cmd()
    if token:
        return token, "", "DESTATIS_TOKEN (from prompts/run-package-11.cmd — package 11's own " \
                           "explicit, one-time exception to the environment-only rule; the token " \
                           "itself is never logged, only this label)"
    return "GAST", "GAST", "GAST/GAST guest login (DESTATIS_TOKEN absent from both the environment " \
                            "and prompts/run-package-11.cmd)"


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


# GENESIS's own logincheck response echoes back whatever was submitted as
# `username` in its own `Username` field — when DESTATIS_TOKEN is used AS
# the username (per the guide's own "not necessary when entering token
# instead of user name"), that field's VALUE IS THE TOKEN, not GENESIS's own
# assigned account name. Confirmed live, this package: with GAST/GAST it
# echoes back the literal string "GAST" (safe); with a real token it echoed
# back a token-shaped string this package's own gate-6 evidence must never
# quote or reproduce. A real leak happened here before this redaction
# existed — the raw response was logged to this session's own tool output
# before the bug was caught — see REPORT-P11.md gate 6 and NEEDS-DECISION
# for the full account and the remediation taken. Every response dict this
# module logs or persists now goes through this first.
#
# Case-insensitive substring match, not an exact-case key list, and
# recursive into nested dicts/lists — GENESIS's own response shape is not
# something this file controls, and a shallow, exact-match check could miss
# a differently-cased key (Destatis returning "USERNAME") or a credential
# echoed one level deeper inside a nested object (finding F7, adversarial
# review, which also found the original version of this function never
# touched whoami's own response at all — fixed below by routing it through
# here too, even though whoami's specific call in run() sends no
# credential today and so has nothing to echo; the guarantee this module's
# own docstring states — "every response... is redacted" — should hold by
# construction, not by which endpoints currently happen to be safe).
_CREDENTIAL_ECHO_TERMS = ("username", "password", "token")


def _redact(resp: dict) -> dict:
    def _walk(v):
        if isinstance(v, dict):
            return _redact(v)
        if isinstance(v, list):
            return [_walk(item) for item in v]
        return v
    return {
        k: ("<redacted>" if any(term in k.lower() for term in _CREDENTIAL_ECHO_TERMS) else _walk(v))
        for k, v in resp.items()
    }


def _num(cell: str) -> float | None:
    """GENESIS marks a suppressed or unavailable cell as '/' or '.' (both
    seen live in this table, e.g. small-cell suppression) — neither is a
    number; both mean "not published for this cell", not zero."""
    cell = cell.strip()
    if cell in ("", "/", "."):
        return None
    return float(cell)


def _find_row(csv_text: str, code: str) -> list[str] | None:
    """The exact row for `code` (matched on the CSV's own code column, not a
    substring — KB10-434 must never match KB10-4340 or KB10-43494) from a
    GENESIS `;`-delimited CSV response."""
    for row in csv.reader(io.StringIO(csv_text), delimiter=";"):
        if len(row) > 1 and row[1] == code:
            return row
    return None


def run() -> None:
    banner(SOURCE_ID, NAME)
    username, password, cred_label = _credentials()
    log(f"    credential: {cred_label}")

    who = _redact(fetch_json(f"{BASE}/helloworld/whoami", cache=False))
    log(f"    whoami: {who}")

    login = _post("helloworld/logincheck", username, password)
    login_ok = "logged in" in str(login.get("Status", ""))
    log(f"    logincheck: {'OK' if login_ok else 'FAILED'} — {_redact(login)}")

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
                blocked_detail = {"table": table_id, "basis": basis, "response": _redact(resp)}
                log(f"    data/table {table_id} ({basis}): BLOCKED — {_redact(resp)}")
                break
            tables[basis] = {"table_id": table_id, "raw_csv": resp["Object"].get("Content")}
            log(f"    data/table {table_id} ({basis}): OK — {len(resp['Object'].get('Content') or '')} chars")
    else:
        blocked_detail = {"step": "logincheck", "response": _redact(login)}

    status = "ok" if tables else "blocked"  # in-band status (data.status / meta.status) — see below

    occupations: dict = {}
    matched_rows: dict[str, list[str]] = {}
    if status == "ok":
        # KB10-434, table 62361-0030 (regular_pay, monthly, excl. special
        # payments): [date, code, title, M_med_hr, M_avg_hr, M_med_mo,
        # M_avg_mo, F_med_hr, F_avg_hr, F_med_mo, F_avg_mo, T_med_hr,
        # T_avg_hr, T_med_mo, T_avg_mo] — indices verified against this
        # table's own header row live, this session (see module docstring).
        reg_row = _find_row(tables["regular_pay"]["raw_csv"], KLDB_CODE)
        # KB10-434, table 62361-0034 (total_earnings, annual, incl. special
        # payments): [year, code, title, M_avg_yr, M_med_yr, F_avg_yr,
        # F_med_yr, T_avg_yr, T_med_yr].
        tot_row = _find_row(tables["total_earnings"]["raw_csv"], KLDB_CODE)
        if reg_row is None or tot_row is None:
            missing = "regular_pay" if reg_row is None else "total_earnings"
            raise RuntimeError(f"{KLDB_CODE} not found in {missing}'s own CSV response — "
                                "Destatis may have restructured this table; do not guess a substitute row")
        matched_rows = {"regular_pay": ";".join(reg_row), "total_earnings": ";".join(tot_row)}
        occupations["434"] = {
            "title": reg_row[2].strip() + f" ({KLDB_CODE})",
            "year": int(tot_row[0]),  # the annual table's own year; the monthly table's own is a month (reg_row[0])
            "reference_month": reg_row[0],
            "dispersion": {
                "regular_median_eur_month": _num(reg_row[13]),
                "regular_mean_eur_month": _num(reg_row[14]),
                "total_median_eur_year": _num(tot_row[8]),
                "total_mean_eur_year": _num(tot_row[7]),
            },
            "distribution": "central-tendency-only",  # median + mean only — this table publishes no percentiles
        }
        log(f"    KB10-434 (Total): regular median={occupations['434']['dispersion']['regular_median_eur_month']} "
            f"EUR/month, total median={occupations['434']['dispersion']['total_median_eur_year']} EUR/year")

    out = {
        "occupations": occupations,
        "status": status,
        "raw_rows": matched_rows,  # the ONE matched CSV line per table, not the ~1,500-row full response
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
            "occupation_family": "KldB 2010 group 434 — Occup. in software development and programming"
                if status == "ok" else None,
            "primary_code": "434" if status == "ok" else None,
            "classification": "KldB 2010 (Fassung 2020)",
            "confidence": "official" if status == "ok" else "blocked",
            "status": status,
            "level": "country (Germany)",
            "unit": "EUR per month (regular_pay, excl. special payments) or EUR per year (total_earnings, "
                    "incl. special payments), gross, both sexes — table 62361-0030/-0034",
            "years": [str(occupations.get("434", {}).get("year"))] if status == "ok" else [],
            "measures": {
                "dispersion": "median and mean only (both _eur_month for regular_pay, _eur_year for "
                               "total_earnings) — table 62361-0030/-0034 publishes no percentile spread "
                               "for this cell, same shape as Australia/Ireland's own central-tendency-only "
                               "sources.",
            },
            "crosswalk_hazard": "KldB 2010's own numbering does not reuse ISCO-08's numbers (unlike SE/DK/"
                "NO/FI's national codes) — KB10-434's own English title ('Occup. in software development "
                "and programming') corresponds to ISCO-08 in scope but no official numeric concordance was "
                "checked this session. Marked 2-digit (isco08:25), the same ceiling Spain's own CNO-11 "
                "label match sits at for the identical reason. See data/occupations.json.",
            "why_it_matters": "The GENESIS REST API is confirmed alive AND, with the registered "
                "DESTATIS_TOKEN, actually accessible — four sessions (packages 8, 9x2, 10) only ever "
                "reached an account-permission wall using the GAST guest login. First real German wage "
                "figures in this pipeline. See module docstring and NEEDS-DECISION.md #15 for the full, "
                "five-session history.",
        },
    )
    record_provenance(
        source_id=SOURCE_ID,
        name=NAME,
        urls=[f"{BASE}/helloworld/whoami", f"{BASE}/helloworld/logincheck",
              f"{BASE}/data/table (62361-0030, 62361-0034)"],
        license_note="dl-de/by-2-0 (Datenlizenz Deutschland – Namensnennung – Version 2.0), per the "
                      "table's own published licence, printed on every GENESIS table response seen "
                      "this session (including the official guide's own worked examples).",
        redistribution="Only the single matched KB10-434 CSV row per table is redistributed here, not "
                        "the ~1,500-row full national classification response — matching this pipeline's "
                        "own practice elsewhere (e.g. Sweden's SCB response, trimmed to codes 2511-2519).",
        transforms=[
            "GET helloworld/whoami (no auth) to confirm the API is reachable.",
            "POST helloworld/logincheck with the available credential (DESTATIS_TOKEN from the "
            "environment, else prompts/run-package-11.cmd, else GAST/GAST) sent as HTTP request headers "
            "per the current official guide's documented convention — never logged, never written to "
            "any file; every response this file touches is redacted (_redact()) before logging or "
            "persisting, after a real, one-time leak into this session's own tool output — see "
            "NEEDS-DECISION.md #25.",
            "POST data/table for 62361-0030 and 62361-0034 in turn, area=all — both returned Code 0 "
            "with the registered token, first attempt, no retries needed.",
            "Located the KB10-434 row in each table's own CSV by exact code-column match (not a "
            "substring search), parsed the Total-column median/mean figures by this table's own "
            "documented field position (verified live against the response's own header row), and kept "
            "only that one matched line per table for citation.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(occupations),
        coverage="1 occupation family (KldB 2010 group 434), 2 bases (regular_pay, total_earnings), "
                 "median+mean only" if status == "ok" else "blocked — see diagnostic.blocked_at",
        status="ok",
        notes=f"Credential used: {cred_label}. " + (
            f"Blocked at: {blocked_detail}" if blocked_detail else
            "Both tables fetched and parsed; KB10-434 is a 3-digit-level Destatis rollup (software "
            "development + programming + management), not a hand-aggregated figure this pipeline built."
        ),
    )


if __name__ == "__main__":
    main_guard(run)
