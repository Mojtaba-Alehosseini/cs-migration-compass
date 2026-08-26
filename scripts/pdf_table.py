"""Column-table reconstruction for PDF ranking tables laid out in repeating
(rank, name, score) column groups -- EF EPI and WIPO GII both use this shape.

Both sources were previously read with `page.extract_text()`, which flattens
a page's columns into one stream of lines and interleaves them wherever two
columns share a physical line -- "23 Australia 48.1 22 6 90 Cabo Verde 22.3
13 4" is one flattened line carrying two unrelated countries' rows spliced
together. That silently drops countries whose true score is not the first
number after their name (WIPO GII lost the US and the Netherlands this way)
and glues a rank onto the next column's name when nothing but pixel position
ever separated them ("04Germany" -- rank 4, but no space to split on).

This module works from `page.extract_words()` instead: every word's own
bounding box (`x0`, `top`) is real geometry, so a table's column structure
can be recovered directly, and each column is then parsed independently --
a neighbouring column's trailing digits can never be read as this column's
score, because the x-ranges never overlap.

Order of construction matters and is preserved on purpose:
  * words within one physical subline are x0-sorted when first collected
    into a zone, giving correct left-to-right reading order for that line;
  * sublines are processed in TOP order and continuation sublines are
    APPENDED (never re-sorted) onto the preceding row's word list, so the
    final order is: subline-1's words (x0 order), then subline-2's words
    (x0 order), etc -- which is the correct reading order for a name
    wrapped across two physical lines.
  * Re-sorting the combined list by (top, x0) at the end is WRONG: two
    words on what is visually "the same line" can carry sub-pixel-different
    `top` values (their font baselines are not bit-identical), so a
    (top, x0) sort can put "01" after "Netherlands" -- silently scrambling
    the row into un-parseable text. This was caught by construction: the
    regex requires a leading digit, so a scrambled row produces zero
    matches rather than a wrong value, but it took the miss rate (should be
    123/123, got 5/123) to notice the bug at all.
"""
from __future__ import annotations

import re

RANK_RE = re.compile(r"^(\d{1,3})(.*)$")


def _is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def sub_lines(words: list[dict], tol: float = 2.5) -> list[tuple[float, list[dict]]]:
    """Cluster words into physical lines by `top`, tolerant of the sub-pixel
    baseline jitter between glyphs on what is visually one line."""
    ws = sorted(words, key=lambda w: w["top"])
    lines: list[tuple[float, list[dict]]] = []
    cur: list[dict] = []
    cur_top: float | None = None
    for w in ws:
        if cur_top is None or abs(w["top"] - cur_top) <= tol:
            cur.append(w)
            cur_top = w["top"] if cur_top is None else cur_top
        else:
            lines.append((cur_top, cur))
            cur, cur_top = [w], w["top"]
    if cur:
        lines.append((cur_top, cur))
    return lines


def find_columns(words: list[dict], min_top: float = 0, min_count: int = 10,
                  fields_per_group: int = 3, cluster_tol: float = 3.0
                  ) -> list[tuple[float, ...]]:
    """Detect repeating column-group anchors from x0 clustering. A real
    column start recurs once per table row; noise (an overflow word, a
    chart label) does not.

    Clustering is by MERGED INTERVAL, not `round(x0)` binning. A single
    logical column's x0 carries sub-pixel jitter row to row (different
    glyphs, different font hinting), and naive integer rounding can split
    one real column into two adjacent bins that each independently clear
    `min_count` -- caught by construction: on the WIPO GII page this
    produced a phantom third "column group" built from split income-rank
    digits, which then read a neighbouring field's trailing digits as if
    they were a country's score. That is the exact failure mode this whole
    module exists to prevent, reintroduced one level up in the column
    detector itself.

    The cluster width is capped from the CLUSTER'S OWN START, not chained
    from the last point added. Chaining (merge if within tol of the
    PREVIOUS point) looks reasonable but is exactly the bug that produced a
    phantom column here: the second word of a two-word country name lands
    at a different x0 for every row ("United States", "United Kingdom",
    "Hong Kong, China", "New Zealand", ...), and that smear of one-off
    positions chains edge-to-edge across 40+ px, absorbing the real "name"
    column anchor into a cluster whose mean is meaningless. Capping from
    the cluster's first point keeps a real column (all its points
    genuinely close to ONE x0, since it is a real left-justified line-up)
    tight, while a smear of scattered one-off positions breaks into many
    low-population clusters that `min_count` then filters out.

    `fields_per_group` is the field COUNT the table's own header declares --
    3 for a (rank, name, score) table like EF EPI, 5 for a table that also
    carries per-row income-group and region ranks like WIPO GII. Each
    returned tuple is (rank_x0, name_x0, score_x0, ...trailing field x0s),
    in left-to-right column order; only the first three positions are read
    by parse_table(), the rest exist so a caller can extend it later without
    another layout probe.
    """
    xs = sorted(w["x0"] for w in words if w["top"] > min_top)
    clusters: list[list[float]] = []
    for x in xs:
        if clusters and x - clusters[-1][0] <= cluster_tol:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    anchors = sorted(
        sum(c) / len(c) for c in clusters if len(c) >= min_count
    )
    # A leftover anchor after chunking fields_per_group at a time does not
    # mean "one field short" -- it means an anchor exists that should not
    # (a caption or legend block that happened to clear min_count), and
    # every group from that point on is silently built from the WRONG
    # words, because chunking is purely positional (found by an
    # adversarial review: five extra words at one existing sub-threshold
    # cluster position took a real 139/139 parse to 0). Refusing to guess
    # which anchor is the impostor is the safe failure here: an empty
    # result is a table this module could not confidently structure, and
    # the caller's own row-count self-check (audit_data.py) reports that
    # loudly rather than accepting a table built from misaligned columns.
    if fields_per_group == 0 or len(anchors) % fields_per_group != 0:
        return []
    groups: list[tuple[float, ...]] = []
    i = 0
    while i + fields_per_group <= len(anchors):
        groups.append(tuple(anchors[i:i + fields_per_group]))
        i += fields_per_group
    return groups


def parse_table(words: list[dict], groups: list[tuple[float, ...]],
                 min_top: float = 0, row_height_hint: float = 14.0
                 ) -> list[tuple[int, str, float, int]]:
    """Parse a column-group ranking table into (rank, name, score, group_index).

    Each column group is parsed INDEPENDENTLY -- a neighbouring group's
    trailing digits can never be read as this group's score, because the
    x-zone boundaries never overlap.
    """
    lines = sub_lines([w for w in words if w["top"] > min_top])
    # The score zone's own right edge is the group's OWN next field if it has
    # one (WIPO GII: income-group rank, right after score) -- never the next
    # GROUP's rank. Reading a neighbouring group's trailing digits as this
    # group's score is exactly the defect this module exists to remove, so
    # the boundary must come from THIS group's own layout, not an assumption
    # that score is always the last field before the next group starts.
    boundaries = []
    for i, g in enumerate(groups):
        rk, nm, sc = g[0], g[1], g[2]
        if len(g) > 3:
            nx = g[3]
        elif i + 1 < len(groups):
            nx = groups[i + 1][0]
        else:
            nx = 100_000
        boundaries.append((rk, nm, sc, nx))

    per_zone: dict[int, list[list]] = {i: [] for i in range(len(groups))}
    for top, lw in lines:
        lw_sorted = sorted(lw, key=lambda w: w["x0"])
        zone_hits = []
        for gi, (rk, nm, sc, nx) in enumerate(boundaries):
            name_w = [w for w in lw_sorted if rk - 3 <= w["x0"] < sc - 3]
            score_w = [w for w in lw_sorted if sc - 3 <= w["x0"] < nx - 3]
            if name_w or score_w:
                zone_hits.append((gi, name_w, score_w))
        # A genuine PACKED data row populates several column groups at once
        # by design -- that is the whole point of this layout, "1 Switzerland
        # 66.0 1 1 71 Colombia 28.5 18 5" is ONE subline carrying TWO
        # countries' entries. So "touches more than one zone" cannot be the
        # noise signal; a first attempt at this filter used it and wiped out
        # every real row along with the one bad line, dropping 139 parsed
        # rows to 1.
        #
        # The real signal is narrower: a footer legend or caption spans
        # several zones' NAME regions while carrying NO SCORE anywhere on
        # that line -- every genuine data row has at least one score, in
        # whichever zone(s) it actually populates. Caught by construction on
        # the WIPO GII page: "Low-income Sub-Saharan Africa Latin America and
        # the Caribbean" sits directly under the last row of the LEFT column,
        # has a word in group 0's name-zone ("Sub-Saharan") and a word in
        # group 1's name-zone ("Latin"), and NO score in either -- and was
        # merged into "Iran (Islamic Republic of)"'s name before this filter
        # existed.
        zones_with_names = [gi for gi, name_w, score_w in zone_hits if name_w]
        # A word landing in the score x-range by geometric coincidence is not
        # a score -- "Caribbean" (the tail of "Latin America and the
        # Caribbean") sits exactly at this table's score-column x-position,
        # which made an earlier version of this filter think that line had a
        # real score and let the footer through. Only a value that actually
        # PARSES as a number counts.
        zones_with_scores = [gi for gi, name_w, score_w in zone_hits
                              if any(_is_float(w["text"]) for w in score_w)]
        if len(zones_with_names) > 1 and not zones_with_scores:
            continue
        for gi, name_w, score_w in zone_hits:
            per_zone[gi].append([top, name_w, score_w])

    results: list[tuple[int, str, float, int]] = []
    for gi, entries in per_zone.items():
        entries.sort(key=lambda e: e[0])
        merged: list[list] = []
        for top, name_w, score_w in entries:
            if score_w or not merged:
                merged.append([top, list(name_w), list(score_w)])
            else:
                # An orphan subline -- name words with no score of its own --
                # is a wrapped continuation of the row directly above it in
                # THIS column. Append, do not re-sort: see module docstring.
                prev = merged[-1]
                if top - prev[0] < row_height_hint * 1.1:
                    prev[1].extend(name_w)
                    # Advance the reference top to THIS line, not the row's
                    # original one -- a name can wrap across three or more
                    # physical lines ("Democratic" / "Republic of the" /
                    # "Congo"), and each continuation must be judged against
                    # the line directly above it, not the row's first line.
                    prev[0] = top
                else:
                    merged.append([top, list(name_w), list(score_w)])
        for top, name_w, score_w in merged:
            if not name_w or not score_w:
                continue
            combined = " ".join(w["text"] for w in name_w)
            m = RANK_RE.match(combined)
            if not m:
                continue
            rank = int(m.group(1))
            name = m.group(2).strip()
            if not name:
                continue
            try:
                score = float(score_w[0]["text"])
            except (ValueError, IndexError):
                continue
            results.append((rank, name, score, gi))
    return sorted(results)
