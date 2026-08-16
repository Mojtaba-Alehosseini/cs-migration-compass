"""Package 12, tier 1.3 — Hacker News "Who is hiring?" thread. Monthly
first-of-month Ask HN thread by account `whoishiring`, read via the public
Firebase API (`hacker-news.firebaseio.com/v0/`) — no key, no terms-of-service
problem (HN's own API is explicitly public), and a meaningful share of
top-level comments state a real salary range in free text.

CONSERVATIVE PARSING BY DESIGN (the work order's own instruction): a comment
either yields a real {min,max,currency,period} via
postings_common.parse_compensation_text(), or it yields NO compensation at
all — never a guessed number. Most comments carry no parseable range; this
is expected and reported honestly (this file's own meta), not treated as a
parsing failure to fix by loosening the regex.

WHY THE TOP-LEVEL COMMENT'S OWN TEXT IS THE "POSTING": HN's own thread has
no structured job schema at all — every comment IS the posting, freeform
text a company pasted in themselves. `title` is therefore the comment's own
FIRST LINE (companies overwhelmingly lead with "Company | Role | Location |
Remote/Onsite" or similar), not a separately-labelled field this source
does not have.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import banner, fetch_json, log, main_guard, record_provenance, write_processed  # noqa: E402
from postings_common import country_from_location, parse_compensation_text  # noqa: E402

SOURCE_ID = "postings_hn"
FB = "https://hacker-news.firebaseio.com/v0"


def _find_current_thread() -> dict | None:
    user = fetch_json(f"{FB}/user/whoishiring.json", cache=False)
    for item_id in user.get("submitted", [])[:12]:  # the account's own most recent submissions
        item = fetch_json(f"{FB}/item/{item_id}.json", cache=False)
        if item and item.get("type") == "story" and "who is hiring" in (item.get("title") or "").lower():
            return item
    return None


def _strip_html(s: str) -> str:
    s = re.sub(r"<p>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    # html.unescape(), not five hand-picked .replace() calls — the earlier
    # version missed &#x2F; (forward slash), which is how HN's own API
    # encodes every "/" in a comment's text. That silently broke period
    # detection for every "$X/hr" or "$X/month" mention (parse_compensation
    # _text's own "/\s*hour" pattern can never match text that still reads
    # "&#x2F;hr" instead of "/hr") — found reading the actual extracted
    # values, not by inspecting this function in isolation.
    return html.unescape(s)


def run() -> None:
    banner(SOURCE_ID, 'Hacker News "Who is hiring?" — free-text advertised pay')
    thread = _find_current_thread()
    if not thread:
        log("    could not find a current 'Who is hiring?' thread among whoishiring's recent submissions")
        write_processed(SOURCE_ID, {"postings": []}, meta={"thread_found": False})
        record_provenance(
            source_id=SOURCE_ID, name='Hacker News "Who is hiring?" thread',
            urls=[f"{FB}/user/whoishiring.json"], license_note="Public HN API, no redistribution terms beyond normal fair use of a public comment thread.",
            transforms=["Searched whoishiring's recent submissions for a story titled 'Who is hiring?' — none found this run."],
            output=f"data/processed/{SOURCE_ID}.json", rows=0, status="ok", coverage="0 — thread not found this run",
        )
        return

    log(f"    thread: {thread.get('title')!r} (id {thread['id']}, {len(thread.get('kids', []))} top-level comments)")
    postings = []
    parsed_comp_count = 0
    for kid_id in thread.get("kids", []):
        c = fetch_json(f"{FB}/item/{kid_id}.json", cache=False)
        if not c or c.get("deleted") or c.get("dead") or not c.get("text"):
            continue
        text = _strip_html(c["text"])
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            continue
        title_line = lines[0][:200]
        comp = None
        # scan the whole comment for a parseable range, not just the first line
        for line in lines:
            comp = parse_compensation_text(line)
            if comp:
                parsed_comp_count += 1
                break
        loc_guess = None
        for line in lines[:3]:
            if any(k in line.lower() for k in ("remote", "onsite", "hybrid", "|")):
                loc_guess = line[:150]
                break
        postings.append({
            "id": f"hn:{c['id']}",
            "provider": "hn", "company": None,  # HN's own free text has no separately-labelled company field
            "company_slug": "hn",
            "title": title_line, "location_raw": loc_guess, "country": country_from_location(loc_guess),
            "remote": ("remote" in text.lower()) if "remote" in text.lower() or "onsite" in text.lower() else None,
            "url": f"https://news.ycombinator.com/item?id={c['id']}",
            "posted_at": None,
            "compensation": comp,
            "occupation": None,
        })

    log(f"    {len(postings)} top-level comments kept, {parsed_comp_count} "
        f"({parsed_comp_count/len(postings)*100 if postings else 0:.0f}%) with a parseable compensation range")

    write_processed(SOURCE_ID, {"postings": postings, "thread_id": thread["id"], "thread_title": thread.get("title")},
                     meta={"thread_found": True, "thread_id": thread["id"], "postings_count": len(postings),
                           "compensation_present_count": parsed_comp_count})
    record_provenance(
        source_id=SOURCE_ID,
        name='Hacker News "Who is hiring?" — free-text advertised pay',
        urls=[f"https://news.ycombinator.com/item?id={thread['id']}"],
        license_note="Public HN API (hacker-news.firebaseio.com) — each comment is the poster's own "
                      "public submission to a public forum thread; redistributed here as individual "
                      "job-posting text, matching how HN's own site displays it.",
        redistribution="Comment text stored as posted; no HTML beyond simple <p> paragraph breaks kept.",
        transforms=[
            "Found the current month's 'Who is hiring?' thread from whoishiring's own recent submissions.",
            "Read every top-level comment via the public Firebase API.",
            "Parsed a compensation range from comment text ONLY where a clear "
            "currency-symbol-plus-two-numbers pattern matched (parse_compensation_text) — most comments "
            "carry no parseable range and are kept with compensation: null, not a guess.",
        ],
        output=f"data/processed/{SOURCE_ID}.json",
        rows=len(postings),
        coverage=f"{len(postings)} postings from 1 thread ({thread.get('title')})",
        notes="Advertised pay — NEVER merged with survey-earnings data. Free text, not a structured "
              "ATS field; disclosed as such downstream.",
    )


if __name__ == "__main__":
    main_guard(run)
