"""Generate Open Graph preview images — `python scripts/generate_og_images.py`.

Link previews are a distribution feature, not decoration: this project expects to
arrive through a Reddit, Telegram or X link, and a link that unfurls into a bare
logo wastes the click.

Static hosting cannot render an image per arbitrary comparison URL, so we
pre-render the cases that actually get shared:
  * one per city   (73)  — "Berlin · $104,000 · $1,100 · 15.0 yrs"
  * one per country(15)
  * one default
Arbitrary multi-city comparisons fall back to the default. That limit is real and
documented rather than hidden.

PNG, not SVG: X and Facebook do not render SVG previews.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, banner, log, main_guard  # noqa: E402

# Read the SITE bundle, not data/cities.json: the derived fields (savings,
# years-to-home) are added by build_site_data.py and only exist there. Reading
# the curated file directly silently produced "no data" for every city.
CORE = ROOT / "site" / "public" / "data" / "core.json"

OUT = ROOT / "site" / "public" / "og"
W, H = 1200, 630

# Palette A (Ledger), locked at the design checkpoint.
PAPER = (246, 243, 236)
INK1 = (25, 24, 19)
INK2 = (85, 82, 74)
INK3 = (116, 112, 95)
LINE = (226, 222, 210)
ACCENT = (12, 107, 84)


def font(size: int, serif: bool = False) -> ImageFont.FreeTypeFont:
    """Best-effort system font. Falls back to the bundled default rather than failing."""
    candidates = (
        ["georgia.ttf", "Georgia.ttf", "constan.ttf", "times.ttf"]
        if serif
        else ["segoeui.ttf", "SegoeUI.ttf", "arial.ttf", "Arial.ttf", "DejaVuSans.ttf"]
    )
    roots = [
        Path("C:/Windows/Fonts"),
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts"),
    ]
    for name in candidates:
        for r in roots:
            p = r / name
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size)
                except OSError:
                    continue
    return ImageFont.load_default(size)


def money(v: float | None) -> str:
    return "no data" if v is None else f"${round(v):,}"


def card(title: str, subtitle: str, rows: list[tuple[str, str]], footer: str, dest: Path) -> None:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # paper grain, matching the site's dot texture
    for y in range(0, H, 22):
        for x in range(0, W, 22):
            d.point((x, y), fill=(234, 230, 220))

    f_kicker = font(21)
    f_title = font(58, serif=True)
    f_sub = font(24)
    f_label = font(23)
    f_value = font(52, serif=True)
    f_foot = font(20)

    d.text((70, 62), "CS MIGRATION COMPASS", font=f_kicker, fill=INK3)
    d.text((70, 104), title[:36], font=f_title, fill=INK1)
    if subtitle:
        d.text((70, 176), subtitle[:70], font=f_sub, fill=INK2)

    d.line([(70, 224), (W - 70, 224)], fill=LINE, width=2)

    y = 268
    for label, value in rows[:3]:
        d.text((70, y + 12), label, font=f_label, fill=INK2)
        bbox = d.textbbox((0, 0), value, font=f_value)
        d.text((W - 70 - (bbox[2] - bbox[0]), y), value, font=f_value, fill=INK1)
        y += 104

    d.line([(70, H - 84), (W - 70, H - 84)], fill=LINE, width=2)
    d.text((70, H - 62), footer, font=f_foot, fill=INK3)

    # the conic brand dot, drawn as two half-discs
    d.pieslice([W - 118, H - 72, W - 70, H - 24], start=-90, end=126, fill=ACCENT)
    d.pieslice([W - 118, H - 72, W - 70, H - 24], start=126, end=270, fill=(181, 80, 47))

    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "PNG", optimize=True)


def run() -> None:
    banner("og_images", "Open Graph link previews")
    OUT.mkdir(parents=True, exist_ok=True)
    if not CORE.exists():
        raise FileNotFoundError(
            f"{CORE} missing — run `python scripts/build_site_data.py` first so the "
            "derived fields exist."
        )
    core = json.loads(CORE.read_text(encoding="utf-8"))
    cities = core["cities"]
    countries = {c["id"]: c for c in core["countries"]}

    card(
        "How far one developer salary goes",
        "15 countries · 73 cities · every number sourced and dated",
        [
            ("Cities compared", "73"),
            ("Countries", "15"),
            ("Rankings we publish", "none"),
        ],
        "We show the data. We never rank places or tell you where to go.",
        OUT / "default.png",
    )
    log("    default.png")

    n = 0
    for city in cities:
        mid = (city.get("computed") or {}).get("mid") or {}
        country = countries.get(city["country"])
        y2h = mid.get("years_to_home")
        card(
            city["name"],
            f"{country['name'] if country else ''} · developer pay, rent and years to a home",
            [
                ("Mid-level developer, per year", money((city.get("salary_usd_year") or {}).get("mid"))),
                ("Rent, 1-bed outside centre", money(city.get("rent_1br_outside_usd_month"))),
                ("Years to own a 90 m² flat", "no data" if y2h is None else f"{y2h:.1f}"),
            ],
            f"Sourced and dated · as of {city.get('as_of', '')}",
            OUT / f"city-{city['id']}.png",
        )
        n += 1

    for c in countries.values():
        e = c.get("enriched", {})
        fb = e.get("foreign_born") or {}
        hap = e.get("happiness") or {}
        card(
            c["name"],
            "visas, residency, jobs and daily life",
            [
                ("Years to permanent residency",
                 "no path" if c.get("pr_years_typical") is None else f"~{c['pr_years_typical']}"),
                ("Years to citizenship",
                 "no path" if c.get("citizenship_years_typical") is None else f"~{c['citizenship_years_typical']}"),
                ("People born abroad",
                 "no data" if fb.get("share_pct") is None else f"{fb['share_pct']}%"),
            ],
            f"Happiness {('#' + str(hap['rank']) + ' of ' + str(hap.get('of'))) if hap.get('rank') else 'no data'}"
            f" · as of {c.get('as_of', '')}",
            OUT / f"country-{c['id']}.png",
        )
        n += 1

    total_kb = sum(p.stat().st_size for p in OUT.glob("*.png")) / 1024
    log(f"    {n + 1} images, {total_kb / 1024:.1f} MB total")
    log("    note: arbitrary multi-city comparison URLs fall back to default.png —")
    log("          a static host cannot render one image per permutation.")


if __name__ == "__main__":
    main_guard(run)
