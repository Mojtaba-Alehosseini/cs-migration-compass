"""Generate per-place share pages — run after `vite build`.

The site is a hash-routed SPA, which means a crawler fetching
`/#/city/berlin` never sees anything but the root index.html: the fragment is
not sent to the server, and Reddit/Telegram/X do not execute JavaScript. So
per-page link previews cannot work from the SPA alone.

Fix: emit a tiny static HTML shell per city and per country at a real path
(`/city/berlin/index.html`). Crawlers read its meta tags; humans are redirected
into the app a moment later. This is the whole reason the OG images exist.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, banner, log, main_guard  # noqa: E402

CORE = ROOT / "site" / "public" / "data" / "core.json"
DIST = ROOT / "site" / "dist"

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{base}#{route}">

<meta property="og:type" content="website">
<meta property="og:site_name" content="CS Migration Compass">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{base}og/{image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:url" content="{base}#{route}">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{og_title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{base}og/{image}">

<meta http-equiv="refresh" content="0; url={rel}#{route}">
<script>location.replace({rel_js} + "#{route}");</script>
</head>
<body style="font-family:system-ui,sans-serif;max-width:34rem;margin:4rem auto;padding:0 1.2rem">
<h1 style="font-size:1.3rem">{heading}</h1>
<p>{desc}</p>
<p><a href="{rel}#{route}">Continue to CS Migration Compass &rarr;</a></p>
</body>
</html>
"""


def clip(text: str, limit: int = 120) -> str:
    """OG descriptions over ~120 chars get truncated by the platforms anyway."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip(" ,.;:") + "…"


def money(v: float | None) -> str:
    return "no data" if v is None else f"${round(v):,}"


def write(path: Path, **kw: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE.format(**kw), encoding="utf-8")


def run() -> None:
    banner("share_pages", "static link-preview shells")
    if not DIST.exists():
        raise FileNotFoundError(f"{DIST} missing — run `npm run build` in site/ first.")
    core = json.loads(CORE.read_text(encoding="utf-8"))
    countries = {c["id"]: c for c in core["countries"]}

    # BASE_PATH is what the Pages workflow builds with; default to root.
    import os
    base_path = os.environ.get("BASE_PATH", "/")
    base = os.environ.get("SITE_URL", base_path)

    n = 0
    for city in core["cities"]:
        mid = (city.get("computed") or {}).get("mid") or {}
        country = countries.get(city["country"])
        y2h = mid.get("years_to_home")
        y2h_txt = "no data" if y2h is None else f"{y2h:.1f} years to own a flat"
        desc = clip(
            f"{city['name']}, {country['name'] if country else ''}: "
            f"{money((city.get('salary_usd_year') or {}).get('mid'))} mid-level dev pay, "
            f"{money(city.get('rent_1br_outside_usd_month'))} rent, {y2h_txt}."
        )
        write(
            DIST / "city" / city["id"] / "index.html",
            title=html.escape(f"{city['name']} — CS Migration Compass"),
            og_title=html.escape(f"{city['name']}: pay, rent and years to a home"),
            heading=html.escape(city["name"]),
            desc=html.escape(desc),
            image=f"city-{city['id']}.png",
            route=f"/city/{city['id']}",
            base=base,
            rel="../../",
            rel_js='"../../"',
        )
        n += 1

    for c in countries.values():
        pr = c.get("pr_years_typical")
        cit = c.get("citizenship_years_typical")
        desc = clip(
            f"{c['name']}: "
            f"{'no permanent path' if pr is None else f'~{pr} years to residency'}, "
            f"{'no citizenship path' if cit is None else f'~{cit} years to a passport'}. "
            "Visas, jobs and daily life, every number sourced."
        )
        write(
            DIST / "country" / c["id"] / "index.html",
            title=html.escape(f"{c['name']} — CS Migration Compass"),
            og_title=html.escape(f"{c['name']}: visas, jobs and daily life"),
            heading=html.escape(c["name"]),
            desc=html.escape(desc),
            image=f"country-{c['id']}.png",
            route=f"/country/{c['id']}",
            base=base,
            rel="../../",
            rel_js='"../../"',
        )
        n += 1

    log(f"    {n} share pages written under {DIST.name}/city/ and {DIST.name}/country/")
    log("    crawlers read these; humans are redirected into the app")

    # The root index.html ships relative og:image paths so it works from any
    # location during development. Crawlers do not resolve those, so once we know
    # the deployed origin we rewrite them to absolute.
    root = DIST / "index.html"
    if root.exists() and base.startswith("http"):
        html_text = root.read_text(encoding="utf-8")
        before = html_text
        html_text = html_text.replace('content="./og/default.png"', f'content="{base}og/default.png"')
        if html_text != before:
            root.write_text(html_text, encoding="utf-8")
            log(f"    rewrote root og:image to absolute ({base}og/default.png)")
    elif root.exists():
        log("    SITE_URL not set — root og:image left relative "
            "(set SITE_URL to the deployed origin for link previews to unfurl)")


if __name__ == "__main__":
    main_guard(run)
