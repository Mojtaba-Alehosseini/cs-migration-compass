# Sources

<!-- GENERATED FILE — do not edit by hand.
     Regenerate with `make docs` (scripts/generate_sources_doc.py).
     Content comes from data/provenance.json, written by the pipeline itself. -->

Last pipeline run: **2026-08-12T00:46:25+00:00**

38 datasets produced data. 2 did not — those are listed too, because a source list that hides its failures is not a source list.

Every figure on the site traces to one of these. Where a source is missing, the site shows “no data” and names the absent figure; it never substitutes an estimate.

## Licences at a glance

The MIT licence in `LICENSE` covers the **code** only. Data belongs to the organisations below and carries their terms.

| Dataset | Licence / terms | What this repo redistributes |
| --- | --- | --- |
| BIS — Selected residential property prices (quarterly) | BIS statistics are free to use with attribution for non-commercial purposes. Cite: Bank for International Settlements, Selected residential property prices. | raw committed |
| BLS Occupational Employment and Wage Statistics (OEWS) — software developers | US federal government work — public domain. Cite: U.S. Bureau of Labor Statistics, OEWS. | processed derivative only — the raw batch responses are cached under data/raw/bls_oews/ but that directory is gitignored, so this repo does not redistribute the raw API responses. Only the derived data/processed/bls_oews.json is committed (US government data is public domain, so this is a choice, not a licence requirement). |
| Open-Meteo geocoding (GeoNames) — city coordinates | Open-Meteo's geocoding API serves GeoNames data — GeoNames is CC BY 4.0, Open-Meteo's own API terms are CC BY 4.0. Cite: GeoNames / Open-Meteo. | lat/lon per city committed in data/cities.json |
| EF English Proficiency Index 2025 | EF publishes the EPI report freely; cite EF Education First, EF English Proficiency Index 2025. | raw committed |
| Eurostat — Employed ICT specialists (isoc_sks_itspt) | Eurostat re-use policy — free re-use with attribution (Commission Decision 2011/833/EU). Cite: Eurostat, isoc_sks_itspt. | raw committed |
| Eurostat — Population and employment, national accounts (nama_10_pe) | Eurostat re-use policy — free re-use with attribution (Commission Decision 2011/833/EU). Cite: Eurostat, nama_10_pe. | raw committed |
| FHFA House Price Index — All-Transactions, Metropolitan Areas (quarterly) | US federal government work — public domain. Cite: FHFA House Price Index. | raw committed |
| Indeed Hiring Lab — Job Postings Index (US metros) | Indeed Hiring Lab publishes this tracker publicly on GitHub for free use with attribution. Cite: Indeed Hiring Lab Job Postings Index. | monthly aggregate committed; the 61 MB daily raw file is cached locally but not committed |
| levels.fyi — Software Engineer total compensation by metro | levels.fyi publishes these metro pages publicly and its robots.txt explicitly invites agent access. Data is crowd-sourced and remains theirs; we store derived per-city figures and cite levels.fyi on every one. No bulk redistribution. | derived per-city figures committed; cited on every figure |
| MIPEX — Migrant Integration Policy Index (EU policy indicators 2020-2024) | MIPEX is published under CC BY-NC-SA. Cite: Solano & Huddleston, Migrant Integration Policy Index. | raw committed |
| Natural Earth 110m physical land — map outline | Public domain. Natural Earth asks for attribution but imposes no restriction: "Made with Natural Earth." | derived outline committed in site/src/data/land.ts |
| Numbeo — yearly country indices and per-city cost-of-living history | Numbeo data is crowd-sourced and its terms restrict bulk redistribution. We commit the derived per-year/per-city aggregates and the fetch script, and cite Numbeo on every figure. | derived aggregates committed (Numbeo terms restrict bulk redistribution) |
| OECD Economic Outlook 119 — projections | OECD terms and conditions — free re-use with attribution for non-commercial use. Cite: OECD Economic Outlook 119. | raw committed |
| OECD Data Explorer (SDMX) — house prices, wages, hours, tax wedge | OECD terms and conditions — free re-use with attribution for non-commercial use. Cite: OECD Data Explorer, dataflow IDs listed per block. | raw committed |
| Reporters Without Borders — World Press Freedom Index | RSF publishes the index openly; cite Reporters Without Borders (RSF), World Press Freedom Index. | raw committed |
| UAE — no occupation-level wage series since 2009 (ILOSTAT last known figures) | ILOSTAT open data terms (ILO). Cite: International Labour Organization (ILO), ILOSTAT, flow DF_EAR_EMTA_SEX_OCU_NB. Underlying national source: UAE Federal Competitiveness and Statistics Centre (FCSC), 2009 Labour Force Survey. | the four cited 2009 figures are reproduced directly in data/processed/salary_ae.json (there is no larger raw payload to separately redistribute — see module docstring; this source does not fetch a raw file at run time). |
| ATO Taxation Statistics 2023-24, Table 15A — income by 6-digit ANZSCO occupation | CC BY 2.5 AU. Cite: Australian Taxation Office (ATO), Taxation statistics 2023-24, Table 15A, via data.gov.au. | processed derivative only — the raw 700 KB ATO workbook is cached under data/raw/salary_au/ but that directory is gitignored, so this repo does not redistribute the raw download (CC BY 2.5 AU would permit it; the repo simply doesn't). Only the derived data/processed/salary_au.json is committed. |
| Job Bank Wages (Canada) — NOC 2021, software occupations, by economic region | Open Government Licence - Canada 2.0. Cite: Employment and Social Development Canada (ESDC) / Job Bank, Wages. | processed derivative only — the raw 18 MB wages CSV is cached under data/raw/salary_ca/ but that directory is gitignored, so this repo does not redistribute the raw download (OGL-Canada 2.0 would permit it; the repo simply doesn't). Only the derived data/processed/salary_ca.json is committed. |
| Danmarks Statistik (DST) LONS20 — ICT occupation wage dispersion (DISCO-08) | CC BY 4.0 (Danmarks Statistik open data licence). Cite: Statistics Denmark (DST), table LONS20. | processed derivative only — the raw StatBank JSON-stat payload is cached under data/raw/salary_dk/ but that directory is gitignored, so this repo does not redistribute the raw source (CC BY 4.0 would permit it; the repo simply doesn't). Only the derived data/processed/salary_dk.json is committed. |
| INE Encuesta Cuatrienal de Estructura Salarial (EES) — IT wages by CNO-11 | Attribution required under Ley 37/2007 (Spain's statistics law) — INE does not publish these tables under a named Creative Commons licence; recorded exactly as that, not labelled CC BY. Cite: Instituto Nacional de Estadistica (INE), Encuesta Cuatrienal de Estructura Salarial (EES). | processed derivative only — the raw Tempus3 JSON payloads are cached under data/raw/salary_es/ but that directory is gitignored, so this repo does not redistribute the raw source. Only the derived data/processed/salary_es.json is committed. |
| Tilastokeskus (Statistics Finland) — ICT occupation wages, full-time earners (AL2010) | CC BY 4.0 (Statistics Finland open data licence). Cite: Statistics Finland (Tilastokeskus), table StatFin/pra/15au. | processed derivative only — the raw json-stat2 payload is cached under data/raw/salary_fi/ but that directory is gitignored, so this repo does not redistribute the raw source. Only the derived data/processed/salary_fi.json is committed. |
| CSO Ireland — SES06 earnings, 'Professional' 1-digit SOC major group | CC BY 4.0 (CSO Ireland open data licence, PxStat). Cite: Central Statistics Office (CSO) Ireland, table SES06. | processed derivative only — the raw JSON-stat2 payload is cached under data/raw/salary_ie/ but that directory is gitignored, so this repo does not redistribute the raw source. Only the derived data/processed/salary_ie.json is committed. |
| Italy — no occupation-level wage earnings flow exists (ISTAT) | N/A — no data fetched. If a future session locates a genuine CP2011 earnings flow, record its actual licence then. | N/A — no raw data fetched or cached. |
| CBS (Statistics Netherlands) — software/application developer wages (BRC 2014) | CC BY 4.0 (CBS StatLine open data licence). Cite: Statistics Netherlands (CBS), table 85517NED. | processed derivative only — the raw OData JSON payload is cached under data/raw/salary_nl/ but that directory is gitignored, so this repo does not redistribute the raw source. Only the derived data/processed/salary_nl.json is committed. |
| SSB (Statistics Norway) — ICT occupation wage dispersion (STYRK-08) | CC BY 4.0 (Statistics Norway open data licence, data.norge.no / SSB API terms). Cite: Statistics Norway (SSB), tables 11418 and 11658. | processed derivative only — the raw JSON-stat2 payloads are cached under data/raw/salary_no/ but that directory is gitignored, so this repo does not redistribute the raw source. Only the derived data/processed/salary_no.json is committed. |
| Qatar Planning and Statistics Authority — wages by ISCO major group, via data.gov.qa | CC BY 4.0 (data.gov.qa open data licence). Cite: Qatar Planning and Statistics Authority (PSA), via data.gov.qa. | processed derivative only — the raw OpenDataSoft JSON payload is cached under data/raw/salary_qa/ but that directory is gitignored, so this repo does not redistribute the raw source (CC BY 4.0 would permit it; the repo simply doesn't). Only the derived data/processed/salary_qa.json is committed. |
| SCB wage structure statistics — ICT occupations (SSYK 2012) | CC0 1.0 Universal (SCB adopted CC0 for all open data 2021-07-01; no attribution required). Cite: Statistics Sweden (SCB), wage and salary structures, private and public sector. | processed derivative only — the raw PxWeb JSON payloads are cached under data/raw/salary_se/ but that directory is gitignored, so this repo does not redistribute the raw source (CC0 would permit it; the repo simply doesn't). Only the derived data/processed/salary_se.json is committed. |
| ONS ASHE Table 14.7 — Annual pay (Gross), IT occupations, SOC 2020 4-digit | Open Government Licence v3.0. Cite: Office for National Statistics (ONS), Annual Survey of Hours and Earnings (ASHE), Table 14. | processed derivative only — the raw 11 MB ASHE zip is cached under data/raw/salary_uk/ but that directory is gitignored, so this repo does not redistribute the raw download (OGL v3.0 would permit it; the repo simply doesn't). Only the derived data/processed/salary_uk.json is committed. |
| Stack Overflow Annual Developer Survey — salaries by country | Stack Overflow releases survey results under the Open Database License (ODbL). Cite: Stack Overflow Annual Developer Survey. | aggregates committed; raw survey CSVs not committed (size) |
| Teranet–National Bank House Price Index (Canada) | Teranet & National Bank of Canada. Free public access for non-commercial use with attribution; index values are proprietary. We commit the derived per-city series. | derived per-city series committed; raw payload also committed (public endpoint) |
| UK House Price Index — full file (HM Land Registry) | Contains HM Land Registry data © Crown copyright and database right. Open Government Licence v3.0. | raw committed |
| UN DESA — International Migrant Stock 2024 (by destination and origin) | UN public data, free to use with attribution. Cite: United Nations Department of Economic and Social Affairs, Population Division (2024). International Migrant Stock 2024. | raw committed |
| UN World Population Prospects 2024 — bulk CSV | CC BY 3.0 IGO. Cite: United Nations, Department of Economic and Social Affairs, Population Division (2024). World Population Prospects 2024. | raw committed |
| Wikipedia — List of countries by English-speaking population | Wikipedia text is CC BY-SA 4.0. Underlying figures belong to the cited national sources. | raw committed |
| WIPO Global Innovation Index 2024 | WIPO publishes the GII under CC BY 4.0 (some content excepted); cite WIPO, Global Innovation Index 2024. | raw committed |
| World Bank Open Data — Indicators API | CC BY 4.0 — World Bank Open Data. Cite: World Bank, World Development Indicators. | raw committed |
| World Happiness Report 2026 — Figure 2.1 data panel | World Happiness Report data is free to use with attribution. Cite: Helliwell et al., World Happiness Report 2026. | raw committed |
| Open-Meteo ERA5 archive — 1991-2020 monthly climate normals | Open-Meteo data is CC BY 4.0; underlying ERA5 is Copernicus Climate Change Service information. Cite: Open-Meteo / Copernicus ERA5. | raw committed |
| IMF World Economic Outlook — country projections | IMF WEO database is free to download and use with attribution. | raw committed |
| World Bank Global Economic Prospects — growth forecasts | CC BY 4.0 — World Bank. Cite: World Bank, Global Economic Prospects. | raw committed |

## Live sources

### BIS — Selected residential property prices (quarterly)

- **Status** — live
- **Coverage** — 13/15 countries (BIS excludes AE, QA), quarterly from 1927-Q1
- **Rows processed** — 11,952
- **Fetched** — 2026-08-04T19:23:39+00:00
- **Licence** — BIS statistics are free to use with attribution for non-commercial purposes. Cite: Bank for International Settlements, Selected residential property prices.
- **Output** — `data/processed/bis_property_prices.json`
- **Fetch script** — see `scripts/`
- **Historical range** — 1970-2026 Q1 (Australia; start year varies by country)

**URLs**

- <https://stats.bis.org/api/v2/data/dataflow/BIS/WS_SPP/1.0/Q.AU+US+CA+GB+IE+DE+NL+IT+ES+SE+DK+NO+FI?format=csv>

**What we do to it**

1. One SDMX-CSV request for all 13 covered countries (key Q.<A>+<B>+...).
1. Split into four series per country by VALUE (real/nominal) x UNIT_MEASURE (index / YoY %).
1. Kept TIME_PERIOD verbatim as 'YYYY-Qn'; sorted ascending.
1. Dropped non-numeric observations. No rebasing — BIS bases differ by country.
1. AE and QA are not published in this dataflow and are recorded as uncovered.

> Index bases differ by country — comparable in shape, not in level.

<details><summary>Verification notes from the source survey</summary>

Human page https://www.bis.org/statistics/pp.htm 302-redirects to a JS-heavy dashboard (dataportal/pp.htm); the old flat-file guess full_pp_csv.zip is dead (404). Use the SDMX v2 REST API instead - confirmed working, returns both nominal and real index series (UNIT_MEASURE 628/771) back to 1970-Q1 through 2026-Q1 for Australia. Full API docs: https://stats.bis.org/api-doc/v2/.

</details>

### BLS Occupational Employment and Wage Statistics (OEWS) — software developers

- **Status** — live
- **Coverage** — 30/30 US cities, current reference year only
- **Rows processed** — 256
- **Fetched** — 2026-08-11T22:19:16+00:00
- **Licence** — US federal government work — public domain. Cite: U.S. Bureau of Labor Statistics, OEWS.
- **Output** — `data/processed/bls_oews.json`
- **Fetch script** — `scripts/src_bls_oews.py`

**URLs**

- `POST https://api.bls.gov/publicAPI/v2/timeseries/data/ (25 series)`
- `POST https://api.bls.gov/publicAPI/v2/timeseries/data/ (25 series)`
- `POST https://api.bls.gov/publicAPI/v2/timeseries/data/ (25 series)`
- `POST https://api.bls.gov/publicAPI/v2/timeseries/data/ (25 series)`
- `POST https://api.bls.gov/publicAPI/v2/timeseries/data/ (25 series)`
- `POST https://api.bls.gov/publicAPI/v2/timeseries/data/ (25 series)`
- …and 5 more of the same shape

**What we do to it**

1. Constructed OEWS series IDs for 30 metros (+ San Jose, + national) x 8 datatypes (employment, hourly mean, annual mean, annual P10/P25/median/P75/P90).
1. Requested them from the v2 API in batches of 25 (the keyless per-request limit).
1. Kept employment counts and all seven wage measures where the API returned data.
1. Series returning 'No Data Available' are counted and omitted — never back-filled or estimated.
1. Relabelled datatype 04 from 'hourly_mean_usd' to 'annual_mean_usd', and added datatype 03 as the new 'hourly_mean_usd' (see module docstring) — 04's stored number is unchanged, only its key; 03 is a genuinely new field sourced from the correct series.

> Snapshot only — the API exposes no OEWS history. Stated on the page, not hidden.

### Open-Meteo geocoding (GeoNames) — city coordinates

- **Status** — live
- **Coverage** — 73/73 cities
- **Rows processed** — 73
- **Fetched** — 2026-08-10T07:48:14+00:00
- **Licence** — Open-Meteo's geocoding API serves GeoNames data — GeoNames is CC BY 4.0, Open-Meteo's own API terms are CC BY 4.0. Cite: GeoNames / Open-Meteo.
- **Output** — `data/processed/city_coordinates.json`
- **Fetch script** — `scripts/src_city_coordinates.py`

**URLs**

- <https://geocoding-api.open-meteo.com/v1/search?name=<city>&count=10&language=en>

**What we do to it**

1. Geocoded each of the 73 cities by name, accepting only hits whose country code matches the city's own and preferring the largest by population — the same rule, and the same cached responses, as the climate-normals step, so the two can never disagree about where a city is.
1. Kept latitude/longitude as decimal degrees (WGS 84), rounded to 4 dp. GeoNames populated-place point (the settlement's principal point, roughly the city centre) — not a metro-area centroid.
1. Recorded the matched place name in geocoded_as, so the two region-named records (sf_bay_area -> San Francisco, washington_dc -> Washington) show their substitution.
1. Added lat and lon to each record in data/cities.json. No existing field was read, moved or modified; the step refuses to move a point it did not itself add.

> Feeds the Compare map only. Every figure on the site remains reachable without it — the country list under the map is the canonical browser.

### EF English Proficiency Index 2025

- **Status** — live
- **Coverage** — 10/15 countries
- **Rows processed** — 10
- **Fetched** — 2026-08-04T19:46:08+00:00
- **Licence** — EF publishes the EPI report freely; cite EF Education First, EF English Proficiency Index 2025.
- **Output** — `data/processed/ef_epi.json`
- **Fetch script** — see `scripts/`
- **Historical range** — 2025 edition (report appendix also lists prior-year scores back to ~2011)

**URLs**

- <https://www.ef.com/assetscdn/WIBIwq6RdJvcD9bc8RMd/cefcom-epi-site/reports/2025/ef-epi-2025-english.pdf>

**What we do to it**

1. Downloaded the published PDF with a browser User-Agent (both hosts 403 otherwise).
1. Extracted text from the first 60 pages with pdfplumber.
1. For each country, took the first line containing its name and a number in (300.0, 750.0).
1. Recorded the originating line with every value for auditability.
1. Countries not confidently matched are omitted rather than guessed.

> PDF scraping is fragile by nature; every value carries its source line.

<details><summary>Verification notes from the source survey</summary>

https://www.ef.com/wwen/epi/ loads fine (200, needs a browser-like UA) and links directly to the full PDF report. HEAD confirmed 200, content-type application/pdf, 10,797,848 bytes, last-modified Nov 2025. No structured CSV/XLSX export found - pipeline needs to parse the PDF's score table/appendix.

</details>

### Eurostat — Employed ICT specialists (isoc_sks_itspt)

- **Status** — live
- **Coverage** — 10/15 countries (EU/EFTA only), 2004-2025 annual
- **Rows processed** — 400
- **Fetched** — 2026-08-04T19:12:06+00:00
- **Licence** — Eurostat re-use policy — free re-use with attribution (Commission Decision 2011/833/EU). Cite: Eurostat, isoc_sks_itspt.
- **Output** — `data/processed/eurostat_ict_specialists.json`
- **Fetch script** — see `scripts/`
- **Historical range** — 2004-2025 annual (22 years), 37 areas (EU27_2020 aggregate + individual EU/EFTA/candidate countries)

**URLs**

- <https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/isoc_sks_itspt?format=JSON&lang=en>

**What we do to it**

1. Fetched full JSON-stat 2.0 cube (freq x unit x geo x time).
1. Decoded the sparse row-major value map to explicit (unit, geo, year) rows.
1. Kept the 15 covered countries plus the EU27_2020 aggregate as a benchmark line.
1. Mapped Eurostat geo 'UK' to our ISO2 'GB'; dropped all other geographies.
1. Split the two units into separate series: absolute count and share of employment.

> Non-EU countries genuinely have no series here; recorded as missing, not imputed.

<details><summary>Verification notes from the source survey</summary>

Task's exact sample URL worked as-is (HTTP 200, real data, 30KB) - no variant needed. Confirmed via dimension inspection that the 'unit' dimension includes BOTH THS_PER (Thousand persons, actual headcount) and PC_EMP (Percentage of total employment), so this single dataset gives both the raw CS/IT employment COUNT and the share metric, per country per year. This directly satisfies the CS/IT-specific employment requirement at country level with 22 years of history.

</details>

### Eurostat — Population and employment, national accounts (nama_10_pe)

- **Status** — live
- **Coverage** — 9/15 countries (EU/EFTA only), 1975-2025 annual
- **Rows processed** — 1,280
- **Fetched** — 2026-08-04T19:12:11+00:00
- **Licence** — Eurostat re-use policy — free re-use with attribution (Commission Decision 2011/833/EU). Cite: Eurostat, nama_10_pe.
- **Output** — `data/processed/eurostat_total_employment.json`
- **Fetch script** — see `scripts/`
- **Historical range** — 1975-2025 annual (51 years), 44 countries

**URLs**

- <https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nama_10_pe?format=JSON&lang=en>

**What we do to it**

1. Fetched full JSON-stat 2.0 cube (freq x unit x na_item x geo x time).
1. Kept unit THS_PER only; dropped the percentage-change unit.
1. Kept 4 na_items: total employment, employees, self-employed, population (national concept).
1. Mapped Eurostat geo 'UK' to ISO2 'GB'; dropped aggregates (EU27, EA*) and other geographies.

> Pairs with eurostat_ict_specialists to give IT jobs as a share of a real total.

<details><summary>Verification notes from the source survey</summary>

Task suggested une_rt_a or lfsi_emp_a as the total-employment dataset; both return HTTP 200 valid JSON, but neither is a clean raw headcount: une_rt_a is an unemployment RATE, and lfsi_emp_a's unit dimension is THS_PER+PC_POP i.e. mixes a real headcount with a %-of-population rate (2003-2025, 38 geos). nama_10_pe is the better match - it has an explicit na_item='Total employment national concept' (EMP_NC) in Thousand persons, covering 44 countries back to 1975 (7 na_item categories total, incl. EMP_DC domestic concept, SAL_NC/SAL_DC employees, SELF_NC/SELF_DC self-employed - useful sub-breakdowns). All three endpoints verified live (200, real JSON) this session; nama_10_pe recommended as the primary 'total employment' series.

</details>

### FHFA House Price Index — All-Transactions, Metropolitan Areas (quarterly)

- **Status** — live
- **Coverage** — 30/30 US cities, 1975Q1-latest quarterly
- **Rows processed** — 6,154
- **Fetched** — 2026-08-04T19:16:07+00:00
- **Licence** — US federal government work — public domain. Cite: FHFA House Price Index.
- **Output** — `data/processed/fhfa_hpi_metro.json`
- **Fetch script** — see `scripts/`
- **Historical range** — 1975 Q1 - 2026 Q1

**URLs**

- <https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_at_metro.csv>

**What we do to it**

1. Downloaded the headerless all-transactions metro CSV (410 metros, 84k rows).
1. Selected the 30 metros matching our US cities, plus San Jose as the Bay Area's second series.
1. Dropped rows where the index is '-' (period before a metro's series begins).
1. Sorted each series by (year, quarter); recorded the published area name and an is_metro_division flag rather than silently treating a division as the whole metro.
1. No rebasing, no smoothing, no interpolation.

> Real city-level history — not a country trend applied to a city.

<details><summary>Verification notes from the source survey</summary>

Task's guessed URL https://www.fhfa.gov/hpi/download/monthly/hpi_at_metro.csv is WRONG (404) - metro data lives under 'quarterly_datasets', not 'monthly', in the path. The legacy hpi/datasets.aspx page now returns 503, and fhfa.gov/DataTools/Downloads 301-redirects through /data/datasets -> /data/hpi -> /data/hpi/datasets, a modern page listing ~30 dataset files across monthly/quarterly/annual tabs. Verified the correct URL directly: HTTP 200, 4.17MB CSV, no header row (columns: metro name, CBSA code, year, quarter, index value, annual %-change-in-parens), 84,050 rows, 410 distinct metro names, spanning 1975 Q1 to 2026 Q1.

</details>

### Indeed Hiring Lab — Job Postings Index (US metros)

- **Status** — live
- **Coverage** — 30/30 US cities, monthly 2020-02 → latest
- **Rows processed** — 73,563
- **Fetched** — 2026-08-04T19:19:18+00:00
- **Licence** — Indeed Hiring Lab publishes this tracker publicly on GitHub for free use with attribution. Cite: Indeed Hiring Lab Job Postings Index.
- **Output** — `data/processed/indeed_hiring_lab_job_postings.json`
- **Fetch script** — see `scripts/`
- **Historical range** — 2020-02-01 to present, daily (repo self-updates weekly; latest row observed 2026-07-24)

**URLs**

- <https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/US/metro_job_postings_us.csv>

**What we do to it**

1. Downloaded the ~61 MB daily US-metro postings CSV.
1. Kept only rows whose cbsa_code matches our 30 US metros (plus San Jose for the Bay Area).
1. Aggregated daily values to monthly arithmetic means, retaining the observation count per month.
1. No smoothing beyond that mean; no gap filling.

> All-postings index, not software-specific — labelled as such in the UI.

<details><summary>Verification notes from the source survey</summary>

Task's guessed https://github.com/hiring-lab/data 301-redirects to the real, current repo hiring-lab/job_postings_tracker. IMPORTANT: this is a seasonally-adjusted INDEX (% change vs the Feb 1 2020 baseline), NOT raw posting counts - note this distinction for the pipeline. Confirmed live: US metro_job_postings_us.csv has 1,403,039 rows spanning 2020-02-01 to 2026-07-24 across US metro areas (by CBSA code); US job_postings_by_sector_US.csv (194,013 rows) confirms a 'Software Development' category with daily values across the same range. Australia's AU folder only has country+sector files (no city/metro breakdown), and its sector taxonomy uses 'IT Infrastructure' / 'IT Systems & Solutions' / 'Data & Analytics' instead of 'Software Development'. The UK's GB folder DOES include city_postings_gb.csv for city-level data. Ireland is explicitly excluded from sector-level data per the repo README.

</details>

### levels.fyi — Software Engineer total compensation by metro

- **Status** — live
- **Coverage** — 63/73 cities (10 explicitly unavailable)
- **Rows processed** — 63
- **Fetched** — 2026-08-04T21:01:37+00:00
- **Licence** — levels.fyi publishes these metro pages publicly and its robots.txt explicitly invites agent access. Data is crowd-sourced and remains theirs; we store derived per-city figures and cite levels.fyi on every one. No bulk redistribution.
- **Output** — `data/processed/levels_fyi.json`
- **Fetch script** — `scripts/src_levels_fyi.py`

**URLs**

- <https://www.levels.fyi/t/software-engineer/locations/toronto-can>
- <https://www.levels.fyi/t/software-engineer/locations/vancouver-can>
- <https://www.levels.fyi/t/software-engineer/locations/montreal-can>
- <https://www.levels.fyi/t/software-engineer/locations/ottawa-can>
- <https://www.levels.fyi/t/software-engineer/locations/calgary-can>
- <https://www.levels.fyi/t/software-engineer/locations/halifax-can>
- …and 3 more of the same shape

**What we do to it**

1. Read server-rendered /t/software-engineer/locations/<slug> pages in a browser session; captured median, 25th and 75th percentile total comp verbatim per metro.
1. Converted local currency to USD using the FX rates pinned in data/metrics.json.
1. Wrote a NEW salary_levels_fyi field on each city; salary_usd_year was left untouched.
1. 7 metros had no resolvable route and 3 returned an implausible value from a different page layout; all 10 are written with an explicit unavailable_reason instead of a number.

> Second salary band — top employers, total comp. Never merged with the market band.

### MIPEX — Migrant Integration Policy Index (EU policy indicators 2020-2024)

- **Status** — live
- **Coverage** — 9/15 countries, 2020-2024
- **Rows processed** — 41
- **Fetched** — 2026-08-04T19:40:08+00:00
- **Licence** — MIPEX is published under CC BY-NC-SA. Cite: Solano & Huddleston, Migrant Integration Policy Index.
- **Output** — `data/processed/mipex.json`
- **Fetch script** — `scripts/src_mipex.py`
- **Historical range** — 2007-2024 (two files combined: 2007-2019 core indicators + 2020-2024 EU scores)

**URLs**

- <https://mipex.eu/sites/default/files/downloads/pdf/EU%20Policy%20Indicators%20Scores%20(2020-2024).xlsx>

**What we do to it**

1. Downloaded the 2020-2024 EU policy-indicator workbook (one sheet per country).
1. For each of our countries present as a sheet, parsed the 'Overall Scores' block (year -> score) and the 'Policy strand' block (year -> per-strand scores).
1. Rounded to 2 decimals; sorted by year. Countries without a sheet are recorded as missing.

> Measures policy, not experience — stated explicitly in the UI.

<details><summary>Verification notes from the source survey</summary>

mipex.eu/download redirects to /history (an old page); the current data lives behind /download-pdf (an Angular page whose server-rendered HTML still exposes the real static file links). Two working xlsx files confirmed via HEAD: (1) this download_url [949KB, 200] and (2) https://mipex.eu/sites/default/files/downloads/pdf/Policy%20Indicators%20Scores%20(2007-2019)%20%E2%80%93%20core%20set%20of%20indicators.xlsx [3.16MB, 200]. Full narrative report PDF also confirmed: https://mipex.eu/sites/default/files/downloads/files/mipex_2025_full.pdf [12.6MB, 200]. URLs contain spaces and an en-dash character - must be percent-encoded exactly as shown or the request 404s.

</details>

### Natural Earth 110m physical land — map outline

- **Status** — live
- **Coverage** — world coastline within the map's crop
- **Fetched** — 2026-08-10T07:48:14+00:00
- **Licence** — Public domain. Natural Earth asks for attribution but imposes no restriction: "Made with Natural Earth."
- **Output** — `site/src/data/land.ts`
- **Fetch script** — see `scripts/`

**URLs**

- <https://www.naturalearthdata.com/downloads/110m-physical-vectors/110m-land/>

**What we do to it**

1. Natural Earth 110m physical land, projected to the Compare map's Mercator box (lon -128..157, lat -45..62, 980x440 units) and decimated to ~14 KB of SVG path data — small enough to ship inline with no request and no map library.
1. Committed as a derived asset rather than re-derived at build time: it is fixed geometry that never changes between runs, and shipping it inline is what keeps the map free of a runtime dependency.

> Decorative context for the dots. It carries no data: every value on the site is read from the list, never from the map.

### Numbeo — yearly country indices and per-city cost-of-living history

- **Status** — live
- **Coverage** — 12 country-years, 0/73 city histories
- **Rows processed** — 180
- **Fetched** — 2026-08-04T19:54:24+00:00
- **Licence** — Numbeo data is crowd-sourced and its terms restrict bulk redistribution. We commit the derived per-year/per-city aggregates and the fetch script, and cite Numbeo on every figure.
- **Output** — `data/processed/numbeo_history.json`
- **Fetch script** — `scripts/src_numbeo_history.py`

**URLs**

- <https://www.numbeo.com/cost-of-living/rankings_by_country.jsp?title=2015>
- <https://www.numbeo.com/cost-of-living/rankings_by_country.jsp?title=2016>
- <https://www.numbeo.com/cost-of-living/rankings_by_country.jsp?title=2017>
- <https://www.numbeo.com/cost-of-living/rankings_by_country.jsp?title=2018>
- <https://www.numbeo.com/cost-of-living/rankings_by_country.jsp?title=2019>
- <https://www.numbeo.com/cost-of-living/rankings_by_country.jsp?title=2020>

**What we do to it**

1. Requested country ranking pages for 2015-2026 via the ?title=YYYY parameter.
1. Parsed the rankings table, resolving country labels to our ISO2 set.
1. Probed ONE city-history page rather than crawling all 73: the served HTML contains only navigation chrome because Numbeo renders the price series client-side (verified for itemIds 1/26/27/105). The finding is recorded; no data was invented from it.
1. Rate-limited to one request per 1.5s.

> Crowd-sourced; thin for small cities and labelled as such everywhere it appears.

### OECD Economic Outlook 119 — projections

- **Status** — live
- **Coverage** — 13/15 countries (AE, QA are not OECD members), projections to 2027
- **Rows processed** — 1,820
- **Fetched** — 2026-08-04T19:29:21+00:00
- **Licence** — OECD terms and conditions — free re-use with attribution for non-commercial use. Cite: OECD Economic Outlook 119.
- **Output** — `data/processed/oecd_economic_outlook.json`
- **Fetch script** — `scripts/src_oecd_economic_outlook.py`

**URLs**

- <https://sdmx.oecd.org/public/rest/data/OECD.ECO.MAD,DSD_EO@DF_EO,1.5/AUS+USA+CAN+GBR+IRL+DEU+NLD+ITA+ESP+SWE+DNK+NOR+FIN..A?format=csv&startPeriod=2000>

**What we do to it**

1. Requested annual EO series for 13 OECD countries from OECD.ECO.MAD,DSD_EO@DF_EO,1.5.
1. Kept 5 measures: real and nominal GDP growth, unemployment, population, net lending.
1. Derived is_projection per point by comparing the EO year against the last World Bank actual year for the same country — the EO cube has no projection flag.
1. Sorted ascending by year. No blending with any other forecast or with our extrapolation.

> Institutional forecast — rendered solid and attributed, kept separate from naive extrapolation.

### OECD Data Explorer (SDMX) — house prices, wages, hours, tax wedge

- **Status** — live
- **Coverage** — 13/15 countries (AE, QA are not OECD members)
- **Rows processed** — 22,703
- **Fetched** — 2026-08-04T19:23:54+00:00
- **Licence** — OECD terms and conditions — free re-use with attribution for non-commercial use. Cite: OECD Data Explorer, dataflow IDs listed per block.
- **Output** — `data/processed/oecd_indicators.json`
- **Fetch script** — `scripts/src_oecd_indicators.py`

**URLs**

- <https://sdmx.oecd.org/public/rest/data/OECD.ECO.MPD,DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES,1.0/AUS+USA+CAN+GBR+IRL+DEU+NLD+ITA+ESP+SWE+DNK+NOR+FIN.Q..?format=csv&startPeriod=1970>
- <https://sdmx.oecd.org/public/rest/data/OECD.ELS.SAE,DSD_EARNINGS@AV_AN_WAGE,1.0/all?format=csv&startPeriod=1990>
- <https://sdmx.oecd.org/public/rest/data/OECD.ELS.SAE,DSD_HW@DF_AVG_ANN_HRS_WKD,1.0/all?format=csv&startPeriod=1990>
- <https://sdmx.oecd.org/public/rest/data/OECD.CTP.TPS,DSD_TAX_WAGES_COMP@DF_TW_COMP,2.1/all?format=csv&startPeriod=2000>

**What we do to it**

1. Resolved all four dataflow IDs from the live OECD SDMX registry (several plausible IDs do not exist).
1. Requested SDMX-CSV per dataflow; used the 'all' key where the flow requires more key positions than we filter on.
1. Mapped REF_AREA ISO3 to our ISO2 set; every other country dropped.
1. avg_wages: kept USD_PPP and national-currency series, both sexes combined (SEX=_Z).
1. hours_worked: kept total worker status (_T).
1. tax_wedge: filtered to single person without children at 100% of the average wage; kept average tax wedge, average income tax rate, gross earnings and net income.
1. Grouped into MEASURE_UNITMEASURE series and sorted by period. No rebasing or smoothing.

> Index bases differ by country and block — compare shape, not level.

### Reporters Without Borders — World Press Freedom Index

- **Status** — live
- **Coverage** — 15/15 countries, 2022-2026
- **Rows processed** — 75
- **Fetched** — 2026-08-04T19:20:41+00:00
- **Licence** — RSF publishes the index openly; cite Reporters Without Borders (RSF), World Press Freedom Index.
- **Output** — `data/processed/rsf_press_freedom.json`
- **Fetch script** — `scripts/src_rsf_press_freedom.py`
- **Historical range** — 2026 confirmed; pattern likely works for recent prior years too (not individually tested)

**URLs**

- <https://rsf.org/sites/default/files/import_classement/2026.csv>
- <https://rsf.org/sites/default/files/import_classement/2025.csv>
- <https://rsf.org/sites/default/files/import_classement/2024.csv>
- <https://rsf.org/sites/default/files/import_classement/2023.csv>
- <https://rsf.org/sites/default/files/import_classement/2022.csv>

**What we do to it**

1. Fetched the per-year CSV for 2022, 2023, 2024, 2025, 2026 (semicolon-delimited).
1. Converted comma decimal separators to points.
1. Resolved ISO3 codes to our 15 ISO2 countries; all other rows dropped.
1. Captured overall score, rank and the five sub-indicators, plus the worldwide ranked count per year so a rank can be shown with its denominator.
1. Restricted to 2022+ because RSF's methodology changed that year.

> Years that failed to download are omitted, never interpolated.

<details><summary>Verification notes from the source survey</summary>

Best surprise of the session - a direct CSV confirmed working (200, text/csv, 26,930 bytes) with the full score breakdown per country. Found via a link on https://rsf.org/en/index. Uses ';' as the field delimiter and ',' as the decimal separator (European format), plus what looks like Latin-1/Windows-1252 encoding in accented country names rather than UTF-8 - handle encoding carefully when parsing.

</details>

### UAE — no occupation-level wage series since 2009 (ILOSTAT last known figures)

- **Status** — live
- **Coverage** — 4 ISCO-08 major groups, single year (2009), UAE only
- **Rows processed** — 4
- **Fetched** — 2026-08-12T00:46:25+00:00
- **Licence** — ILOSTAT open data terms (ILO). Cite: International Labour Organization (ILO), ILOSTAT, flow DF_EAR_EMTA_SEX_OCU_NB. Underlying national source: UAE Federal Competitiveness and Statistics Centre (FCSC), 2009 Labour Force Survey.
- **Output** — `data/processed/salary_ae.json`
- **Fetch script** — `scripts/src_salary_ae.py`

**URLs**

- <https://sdmx.ilo.org/rest/data/ILO,DF_EAR_EMTA_SEX_OCU_NB,1.0/ARE.......?startPeriod=1990>

**What we do to it**

1. No transform — this is a dated snapshot of ILOSTAT's own published 2009 values for the UAE, verified live against the full 39-row flow before being pinned here (every row in the flow is 2009; nothing more recent exists to prefer over these).

> No occupation-level wage statistic exists for the UAE newer than 2009 in ILOSTAT or in the national statistics body's (FCSC) own releases — verified, not assumed. This file exists so that absence is a sourced, dated data record instead of a silent gap.

### ATO Taxation Statistics 2023-24, Table 15A — income by 6-digit ANZSCO occupation

- **Status** — live
- **Coverage** — 7/7 6-digit ANZSCO codes, Australia, 2023-24 income year
- **Rows processed** — 49
- **Fetched** — 2026-08-12T00:46:01+00:00
- **Licence** — CC BY 2.5 AU. Cite: Australian Taxation Office (ATO), Taxation statistics 2023-24, Table 15A, via data.gov.au.
- **Output** — `data/processed/salary_au.json`
- **Fetch script** — `scripts/src_salary_au.py`

**URLs**

- <https://data.gov.au/data/dataset/faea4485-f407-457d-97f8-3f0822ccd654/resource/3286e287-ee87-4be4-87b2-56c5c6602009/download/ts24individual15occupationsex.xlsx>
- <https://data.gov.au/data/dataset/taxation-statistics-2023-24>

**What we do to it**

1. Downloaded Table 15A (Average and median taxable income, salary or wages, and total income by occupation and sex) from the 2023-24 Taxation Statistics workbook.
1. Parsed all 7 6-digit ANZSCO codes under unit group 2613 (Software and applications programmers), Sex='Total' rows only.
1. Kept N, and mean/median for all three of taxable income, salary-or-wage income and total income, verbatim, under separate never-blended keys. No percentiles exist in this table.

> Mean/median only — no percentile data exists for AU at this occupation depth from any live source (checked: ABS EEH 6306.0 has means at 4-digit and percentiles only at 1-digit, and no EEH dataflow exists on data.api.abs.gov.au to bridge them).

### Job Bank Wages (Canada) — NOC 2021, software occupations, by economic region

- **Status** — live
- **Coverage** — 4/4 target NOC codes x up to 86 geographies each
- **Rows processed** — 344
- **Fetched** — 2026-08-11T19:32:46+00:00
- **Licence** — Open Government Licence - Canada 2.0. Cite: Employment and Social Development Canada (ESDC) / Job Bank, Wages.
- **Output** — `data/processed/salary_ca.json`
- **Fetch script** — `scripts/src_salary_ca.py`

**URLs**

- <https://open.canada.ca/data/dataset/adad580f-76b0-4502-bd05-20c125de9116/resource/9da94d63-b178-4a64-aeb3-b6a3bd721ad2/download/2a71-das-wage2025opendata-esdc-all-19nov2025-vf.csv>
- <https://open.canada.ca/data/en/dataset/adad580f-76b0-4502-bd05-20c125de9116>

**What we do to it**

1. Downloaded the 2025 wages CSV (44,376 rows, all NOC 2021 occupations, all geographies) and filtered to 4 target NOC codes.
1. Kept every geography row for each target NOC verbatim, including rows where the wage fields are null because Job Bank suppressed them for small-area reliability — the geography is kept, not dropped, with the null and Job Bank's own comment intact.
1. Confirmed via the file's own Annual_Wage_Flag that all four target occupations are published hourly, not annual; no unit conversion performed.

### Danmarks Statistik (DST) LONS20 — ICT occupation wage dispersion (DISCO-08)

- **Status** — live
- **Coverage** — 5 DISCO-08 occupations x 7 years, Denmark only (no sub-national breakdown in this table)
- **Rows processed** — 175
- **Fetched** — 2026-08-12T00:46:02+00:00
- **Licence** — CC BY 4.0 (Danmarks Statistik open data licence). Cite: Statistics Denmark (DST), table LONS20.
- **Output** — `data/processed/salary_dk.json`
- **Fetch script** — `scripts/src_salary_dk.py`

**URLs**

- <https://api.statbank.dk/v1/data (table=LONS20)>

**What we do to it**

1. Queried DISCO-08 codes 2511, 2512, 2513, 2514, 2519 (group 251) x all sectors x all forms of pay x non-managerial employees x both sexes x 2018-2024 from table LONS20 via POST, format JSONSTAT.
1. Kept mean-equivalent, lower quartile, median, upper quartile (each _dkk_hour) and employee count verbatim.
1. Occupation titles are the API's own labels, not hand-typed.

> Uses the non-managerial-employees, all-forms-of-pay cut (LONGRP=MED, AFLOEN=TIFA) — see module docstring for why, and for the residual gap from an external cited reference figure.

### INE Encuesta Cuatrienal de Estructura Salarial (EES) — IT wages by CNO-11

- **Status** — live
- **Coverage** — 2 occupation labels (IT professionals + broader ICT specialists) with percentile dispersion, plus 1 broader-category age cross and 1 broader-category tenure cross, Spain only
- **Rows processed** — 25
- **Fetched** — 2026-08-11T22:39:10+00:00
- **Licence** — Attribution required under Ley 37/2007 (Spain's statistics law) — INE does not publish these tables under a named Creative Commons licence; recorded exactly as that, not labelled CC BY. Cite: Instituto Nacional de Estadistica (INE), Encuesta Cuatrienal de Estructura Salarial (EES).
- **Output** — `data/processed/salary_es.json`
- **Fetch script** — `scripts/src_salary_es.py`

**URLs**

- <https://servicios.ine.es/wstempus/js/EN/DATOS_TABLA/70672>
- <https://servicios.ine.es/wstempus/js/EN/DATOS_TABLA/70706>
- <https://servicios.ine.es/wstempus/js/EN/DATOS_TABLA/70707>

**What we do to it**

1. Fetched tables 70672 (dispersion by CNO-11 occupation), 70706 (age) and 70707 (tenure) in full from INE's Tempus3 DATOS_TABLA endpoint, then filtered by matching each series' own English name text (INE's Tempus3 API is flat: series are self-describing by name, not selected via PxWeb-style dimension codes).
1. Kept the latest available data point per matched series verbatim, with its own year — 70672's occupation series are 2018; 70706/70707's are checked and recorded per-series.
1. 70706/70707 only reach CNO-11 major group 2 ('Scientific and intellectual technicians and professionals'), not subgroup 27 specifically — stored separately as broader_category_context, not merged into occupations.

> Vintage is 2018 for the dispersion table, not 2022 as assumed by the work order that commissioned this harvester — verified live, not a fetch error.

### Tilastokeskus (Statistics Finland) — ICT occupation wages, full-time earners (AL2010)

- **Status** — live
- **Coverage** — 5 AL2010 occupations, single year (2024), Finland only, full-time earners only
- **Rows processed** — 25
- **Fetched** — 2026-08-12T00:46:23+00:00
- **Licence** — CC BY 4.0 (Statistics Finland open data licence). Cite: Statistics Finland (Tilastokeskus), table StatFin/pra/15au.
- **Output** — `data/processed/salary_fi.json`
- **Fetch script** — `scripts/src_salary_fi.py`

**URLs**

- <https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin/pra/15au.px>

**What we do to it**

1. Queried AL2010 codes 2511, 2512, 2513, 2514, 2519 (group 251) x all sectors x both sexes x 2024 (the table's sole exposed year) from StatFin/pra/15au via POST, format json-stat2.
1. Kept N, mean, P10, median, P90 (each for TOTAL earnings, not the narrower 'regular hours' variant the table also publishes) verbatim.
1. Occupation titles are the API's own labels, not hand-typed.

> Full-time-only scope is the table's own restriction, not a filter this pipeline chose — see meta.unit.

### CSO Ireland — SES06 earnings, 'Professional' 1-digit SOC major group

- **Status** — live
- **Coverage** — 1 SOC major group x 2 years, Ireland only
- **Rows processed** — 8
- **Fetched** — 2026-08-11T23:06:35+00:00
- **Licence** — CC BY 4.0 (CSO Ireland open data licence, PxStat). Cite: Central Statistics Office (CSO) Ireland, table SES06.
- **Output** — `data/processed/salary_ie.json`
- **Fetch script** — `scripts/src_salary_ie.py`

**URLs**

- <https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/SES06/JSON-stat/2.0/en>

**What we do to it**

1. Fetched table SES06 in full (JSON-stat 2.0) and kept only the 'Professional' (SOC major group 2) rows — the closest, but not ICT-specific, occupation cut this table publishes.
1. Kept mean/median hourly earnings and mean/median paid weekly hours for every year the table carries (2018, 2022) verbatim.

> 1-digit SOC only — confirmed against the table's own live dimension, not assumed. No ICT-specific series exists in Irish official statistics at any finer depth via this table.

### Italy — no occupation-level wage earnings flow exists (ISTAT)

- **Status** — live
- **Coverage** — no occupation-level coverage exists for Italy in this pipeline
- **Rows processed** — 0
- **Fetched** — 2026-08-12T00:46:24+00:00
- **Licence** — N/A — no data fetched. If a future session locates a genuine CP2011 earnings flow, record its actual licence then.
- **Output** — `data/processed/salary_it.json`
- **Fetch script** — `scripts/src_salary_it.py`

**URLs**

- <https://esploradati.istat.it/SDMXWS/rest/dataflow/IT1/ALL/latest>

**What we do to it**

1. No transform — this file records the absence of a source, per the work order's own reported scan of ISTAT's full SDMX dataflow catalogue (4,896 flows), not independently re-verified or re-scanned here.

> ISTAT publishes no occupation-level (CP2011) earnings flow. Its CONTRACTUAL_OCCUPATION dimension is contract grade (operaio/impiegato/quadro/dirigente), not occupation. The only CP2011-crossed earnings flow is a school-leaver cohort survey, not a general wage structure and not comparable to this spine's other sources. NACE J sector earnings are the named alternative, not substituted here because a sector figure is not an occupation figure.

### CBS (Statistics Netherlands) — software/application developer wages (BRC 2014)

- **Status** — live
- **Coverage** — 1 BRC occupation code x 12 years, Netherlands only
- **Rows processed** — 48
- **Fetched** — 2026-08-11T22:44:24+00:00
- **Licence** — CC BY 4.0 (CBS StatLine open data licence). Cite: Statistics Netherlands (CBS), table 85517NED.
- **Output** — `data/processed/salary_nl.json`
- **Fetch script** — `scripts/src_salary_nl.py`

**URLs**

- <https://opendata.cbs.nl/ODataApi/OData/85517NED/TypedDataSet?$filter=Beroep eq 'A000275'>
- <https://opendata.cbs.nl/ODataApi/OData/85517NED/DataProperties>
- <https://opendata.cbs.nl/ODataApi/OData/85517NED/Beroep>

**What we do to it**

1. Queried BRC 2014 code A000275 (0811, software and application developers) from table 85517NED's TypedDataSet, filtered server-side via OData $filter.
1. Kept employee count (thousands), P25, median and P75 gross hourly wage for every annual period (JJ00) verbatim; non-annual (quarterly) periods, if any, are excluded.

> BRC 2014 has no ISCO-08 correspondence — see meta.crosswalk_hazard.

### SSB (Statistics Norway) — ICT occupation wage dispersion (STYRK-08)

- **Status** — live
- **Coverage** — 5 STYRK-08 occupations x 5 years + age cross, Norway only
- **Rows processed** — 149
- **Fetched** — 2026-08-12T00:46:05+00:00
- **Licence** — CC BY 4.0 (Statistics Norway open data licence, data.norge.no / SSB API terms). Cite: Statistics Norway (SSB), tables 11418 and 11658.
- **Output** — `data/processed/salary_no.json`
- **Fetch script** — `scripts/src_salary_no.py`

**URLs**

- <https://data.ssb.no/api/v0/en/table/11418>
- <https://data.ssb.no/api/v0/en/table/11658>

**What we do to it**

1. Queried STYRK-08 codes 2511, 2512, 2513, 2514, 2519 (group 251) x all sectors x both sexes x all employees x 2021-2025 from table 11418.
1. Queried the same codes x 3 age bands x the latest available quarter (2026K1) from table 11658.
1. Kept mean, median, quartiles, N (11418) and age-banded median/mean (11658) verbatim.
1. Occupation titles are the API's own labels, not hand-typed.

### Qatar Planning and Statistics Authority — wages by ISCO major group, via data.gov.qa

- **Status** — live
- **Coverage** — 1 ISCO major group x 2 sexes x 4 years, Qatar only
- **Rows processed** — 8
- **Fetched** — 2026-08-11T23:06:37+00:00
- **Licence** — CC BY 4.0 (data.gov.qa open data licence). Cite: Qatar Planning and Statistics Authority (PSA), via data.gov.qa.
- **Output** — `data/processed/salary_qa.json`
- **Fetch script** — `scripts/src_salary_qa.py`

**URLs**

- <https://www.data.gov.qa/api/explore/v2.1/catalog/datasets/workers-in-paid-employment-15-years-and-above-and-monthly-average-wage-q1/records?limit=100>
- <https://sdmx.ilo.org/rest/data/ILO,DF_EAR_EMTA_SEX_OCU_NB,1.0/QAT.......?startPeriod=2018>

**What we do to it**

1. Fetched all records from the data.gov.qa OpenDataSoft dataset and kept only the 'Professionals' (ISCO major group 2) rows, both sexes, 2020-2023.
1. Kept paid-employment headcount and monthly average wage (QAR) verbatim, per sex, per year — no total/blended figure computed.
1. Corroborated against ILOSTAT flow DF_EAR_EMTA_SEX_OCU_NB (verified live, QAT filter returns real rows) — cited in provenance, not re-parsed into this file's data.

> Major-group depth only — the finest occupation breakdown data.gov.qa publishes for this indicator. Not IT-specific.

### SCB wage structure statistics — ICT occupations (SSYK 2012)

- **Status** — live
- **Coverage** — 7 SSYK occupations x 3 years, Sweden only (no sub-national breakdown in these tables)
- **Rows processed** — 463
- **Fetched** — 2026-08-11T19:32:28+00:00
- **Licence** — CC0 1.0 Universal (SCB adopted CC0 for all open data 2021-07-01; no attribution required). Cite: Statistics Sweden (SCB), wage and salary structures, private and public sector.
- **Output** — `data/processed/salary_se.json`
- **Fetch script** — `scripts/src_salary_se.py`

**URLs**

- <https://api.scb.se/OV0104/v1/doris/en/ssd/AM/AM0110/AM0110A/LoneSpridSektYrk4AN>
- <https://api.scb.se/OV0104/v1/doris/en/ssd/AM/AM0110/AM0110A/LonYrkeAlder4AN>

**What we do to it**

1. Queried SSYK 2012 codes 2511, 2512, 2513, 2514, 2515, 2516, 2519 (group 251, ICT professionals) x all sectors x both sexes x 2023-2025 from two PxWeb tables via POST, response format json-stat2.
1. Dispersion table: kept mean, median, P10/P25/P75/P90 and each measure's 95% CI verbatim.
1. Age table: kept monthly salary and employee count (N) for 7 age bands plus the total, verbatim, including SCB's own null suppression on small cells.
1. Occupation titles are the API's own labels, not hand-typed.

> Reference implementation of the salary spine: CC0, 4-digit, with published confidence intervals.

### ONS ASHE Table 14.7 — Annual pay (Gross), IT occupations, SOC 2020 4-digit

- **Status** — live
- **Coverage** — 6/6 target SOC 2020 codes, UK-wide, 2025 provisional
- **Rows processed** — 6
- **Fetched** — 2026-08-11T19:32:31+00:00
- **Licence** — Open Government Licence v3.0. Cite: Office for National Statistics (ONS), Annual Survey of Hours and Earnings (ASHE), Table 14.
- **Output** — `data/processed/salary_uk.json`
- **Fetch script** — `scripts/src_salary_uk.py`

**URLs**

- <https://www.ons.gov.uk/file?uri=/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/occupation4digitsoc2010ashetable14/2025provisional/ashetable142025provisional.zip>
- <https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/occupation4digitsoc2010ashetable14>

**What we do to it**

1. Downloaded the 2025-provisional ASHE Table 14 zip and extracted the paired 14.7 (Annual pay - Gross) workbooks: 'a' (values) and 'b' (coefficients of variation).
1. Read the 'All' sheet (both sexes, full-time + part-time combined) of each.
1. Kept rows for SOC 2020 codes 1137, 2133-2137 verbatim: description, job count, mean, median, the full published percentile set, year-on-year % change, and CV.
1. ONS's own suppression markers ('x' = CV>20% unreliable, '..' = disclosive) become null — never a guessed number.

> 2025 data is PROVISIONAL; the revised vintage follows Oct/Nov 2026 and should replace this.

### Stack Overflow Annual Developer Survey — salaries by country

- **Status** — live
- **Coverage** — 15/15 countries across 1 wave(s)
- **Rows processed** — 65,437
- **Fetched** — 2026-08-04T19:44:23+00:00
- **Licence** — Stack Overflow releases survey results under the Open Database License (ODbL). Cite: Stack Overflow Annual Developer Survey.
- **Output** — `data/processed/stackoverflow_survey.json`
- **Fetch script** — see `scripts/`
- **Historical range** — 2011-2025

**URLs**

- <https://github.com/StackExchange/Survey/raw/refs/heads/main/packages/archive/2024/results.csv>

**What we do to it**

1. Streamed the annual results CSV for waves: 2024 (~150 MB each).
1. Resolved the free-text Country column to our 15 ISO2 codes; all other responses dropped.
1. Dropped compensation outside $5,000-$1,000,000.
1. Bucketed by experience (<3 / 3-6 / 6+ professional years) and separately by DevType role.
1. Computed median plus p25/p75 per bucket, always retaining n and a thin_sample flag.
1. Raw CSVs are cached locally but excluded from the repo for size (see .gitignore).

> Self-selected sample — comparative signal, not an authoritative wage level.

<details><summary>Verification notes from the source survey</summary>

survey.stackoverflow.co now links directly to a GitHub-hosted archive (StackExchange/Survey repo) rather than the old per-year zip-on-S3 pattern. Verified the 2024 link resolves (302 redirect to media.githubusercontent.com, then 200). Schema/columns differ by year (salary-by-country fields especially), so the pipeline should handle per-year column mapping rather than assume a fixed schema.

</details>

### Teranet–National Bank House Price Index (Canada)

- **Status** — live
- **Coverage** — 6/6 Canadian cities, monthly 1990-06-01→2026-06-01
- **Rows processed** — 2,303
- **Fetched** — 2026-08-04T19:16:10+00:00
- **Licence** — Teranet & National Bank of Canada. Free public access for non-commercial use with attribution; index values are proprietary. We commit the derived per-city series.
- **Output** — `data/processed/teranet_national_bank_hpi.json`
- **Fetch script** — see `scripts/`
- **Historical range** — 1990-06-01 to 2026-06-01 (433 monthly points); individual cities start later than the array start - e.g. Vancouver has data for the full range from index 0, while Toronto/Calgary/the 11-city Composite only start around index 96-104 (roughly 1998-1999) - exact per-city start is the first non-null array entry

**URLs**

- <https://housepriceindex.ca/_data/indx_data.json>

**What we do to it**

1. Fetched the JSON payload backing housepriceindex.ca (35 profiles, 7 data blocks).
1. Rebuilt the monthly date axis from data.meta.start_date and the series length.
1. Selected the 6 series matching our Canadian cities; dropped leading nulls (a city's index simply starts later) rather than back-filling.
1. Kept the Composite 11 series separately as a labelled national benchmark.
1. No rebasing, no smoothing.

> Real city-level history for Canada.

<details><summary>Verification notes from the source survey</summary>

Best surprise of the session. housepriceindex.ca required curl -k (its TLS chain didn't validate against curl's default CA bundle) - worth checking before production use. The homepage has NO visible CSV/download button; the real data source was found only by grepping the homepage's raw HTML for '.json' references, which surfaced /_data/indx_data.json - a 558KB undocumented file behind the interactive chart widget, with a 'profiles' object (metadata + latest value per city, 35 entries) and a 'data' object containing full per-city monthly arrays (index, seasonally-adjusted index, sales-price composite, plus *_ch change variants) and an exact {start_date, end_date} meta block. A fully free, structured, 36-year city-level dataset with no login/paywall, sitting undocumented behind a marketing site.

</details>

### UK House Price Index — full file (HM Land Registry)

- **Status** — live
- **Coverage** — 3/3 UK cities, monthly (values sparse before the mid-1990s)
- **Rows processed** — 1,344
- **Fetched** — 2026-08-04T19:19:04+00:00
- **Licence** — Contains HM Land Registry data © Crown copyright and database right. Open Government Licence v3.0.
- **Output** — `data/processed/uk_hpi.json`
- **Fetch script** — `scripts/src_uk_hpi.py`

**URLs**

- <https://publicdata.landregistry.gov.uk/market-trend-data/house-price-index-data/UK-HPI-full-file-2026-05.csv>

**What we do to it**

1. Discovered the latest monthly full-file release by HEAD-probing back from the current month.
1. Streamed the ~35 MB CSV and kept only rows whose RegionName matches our 3 UK cities.
1. Parsed dd/mm/yyyy dates to YYYY-MM; dropped rows with neither an average price nor an index.
1. Kept average price, index, detached and flat prices; sorted ascending by month.
1. Left values in GBP — no FX conversion of a multi-decade series.

> Real city-level history including an actual price level, not just an index.

### UN DESA — International Migrant Stock 2024 (by destination and origin)

- **Status** — live
- **Coverage** — 15/15 destinations, reference years 1990-2024
- **Rows processed** — 2,094
- **Fetched** — 2026-08-04T19:27:27+00:00
- **Licence** — UN public data, free to use with attribution. Cite: United Nations Department of Economic and Social Affairs, Population Division (2024). International Migrant Stock 2024.
- **Output** — `data/processed/un_migrant_stock.json`
- **Fetch script** — `scripts/src_un_migrant_stock.py`
- **Historical range** — 1990-2024 (reference years within file typically 1990,1995,2000,2005,2010,2015,2020,2024)

**URLs**

- <https://www.un.org/development/desa/pd/sites/www.un.org.development.desa.pd/files/undesa_pd_2024_ims_stock_by_sex_destination_and_origin.xlsx>

**What we do to it**

1. Downloaded the 6 MB origin-by-destination workbook with a browser User-Agent (un.org 403s otherwise).
1. Read 'Table 1', locating the header at row 11 and detecting year columns by 4-digit headers.
1. Kept rows whose destination M49 code is one of our 15 countries.
1. Split into: total foreign-born (origin = World/900), per-origin breakdown for the latest reference year (country origins only, codes < 900), and the Iranian-born series (M49 364).
1. Sorted origin breakdowns by descending stock. No estimation of missing corridors.

> Absolute counts; shares are computed in-site against World Bank population and shown as a formula.

<details><summary>Verification notes from the source survey</summary>

Listing page https://www.un.org/development/desa/pd/content/international-migrant-stock returns HTTP 403 without a browser-like User-Agent header - MUST send a UA string (e.g. 'Mozilla/5.0') or all requests are blocked. Verified via HEAD: content-length 6,005,287 bytes, content-type application/vnd.openxmlformats...sheet, last-modified 2025-01-27. Sibling files also present for 2017/2019/2020 vintages and age/sex-only breakdowns at the same base path.

</details>

### UN World Population Prospects 2024 — bulk CSV

- **Status** — live
- **Coverage** — 15/15 countries, 1990-2100 (projections from 2024)
- **Rows processed** — 1,665
- **Fetched** — 2026-08-04T19:38:46+00:00
- **Licence** — CC BY 3.0 IGO. Cite: United Nations, Department of Economic and Social Affairs, Population Division (2024). World Population Prospects 2024.
- **Output** — `data/processed/un_wpp.json`
- **Fetch script** — `scripts/src_un_wpp.py`

**URLs**

- <https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/CSV_FILES/WPP2024_TotalPopulationBySex.csv.gz>

**What we do to it**

1. Downloaded and gunzipped the 17 MB total-population bulk CSV (~720k rows).
1. Kept only the 'Estimates' and medium 'Medium' variants; all other projection variants dropped.
1. Filtered to our 15 countries by ISO2/ISO3 code and to years 1990-2100.
1. Converted WPP's thousands to persons.
1. Marked years after 2023 as projections; de-duplicated by year.

> Medium variant only — high/low variants deliberately not shown, to avoid implying a range we did not model.

### Wikipedia — List of countries by English-speaking population

- **Status** — live
- **Coverage** — 13/15 countries, single snapshot
- **Rows processed** — 13
- **Fetched** — 2026-08-04T19:34:07+00:00
- **Licence** — Wikipedia text is CC BY-SA 4.0. Underlying figures belong to the cited national sources.
- **Output** — `data/processed/wikipedia_english_speakers.json`
- **Fetch script** — see `scripts/`
- **Historical range** — single snapshot, sourced from ~2012 Eurobarometer plus varying national census years

**URLs**

- <https://en.wikipedia.org/wiki/List_of_countries_by_English-speaking_population>

**What we do to it**

1. Fetched the article HTML and parsed every wikitable whose header mentions English.
1. Resolved the first cell of each row to one of our 15 countries; all other rows dropped.
1. Extracted the first percentage and the first large integer found in the row.
1. Countries absent from the table are recorded as missing, never estimated.

> Mixed vintages by country — a snapshot, not a series.

<details><summary>Verification notes from the source survey</summary>

Confirmed page loads (200), contains 8 tables, and cites 'Eurobarometer' 3 times, matching the expected source. No CSV export exists - pipeline should parse the HTML tables directly or use Wikipedia's action API for cleaner structured extraction.

</details>

### WIPO Global Innovation Index 2024

- **Status** — live
- **Coverage** — 13/15 countries
- **Rows processed** — 13
- **Fetched** — 2026-08-04T19:46:34+00:00
- **Licence** — WIPO publishes the GII under CC BY 4.0 (some content excepted); cite WIPO, Global Innovation Index 2024.
- **Output** — `data/processed/wipo_gii.json`
- **Fetch script** — see `scripts/`
- **Historical range** — 2024 edition (17th) confirmed; 2025 edition (18th) URL guessed at the same record and also returned 200 but content not independently opened

**URLs**

- <https://tind.wipo.int/record/50062/files/wipo-pub-2000-2024-en-global-innovation-index-2024-17th-edition.pdf>

**What we do to it**

1. Downloaded the published PDF with a browser User-Agent (both hosts 403 otherwise).
1. Extracted text from the first 60 pages with pdfplumber.
1. For each country, took the first line containing its name and a number in (5.0, 80.0).
1. Recorded the originating line with every value for auditability.
1. Countries not confidently matched are omitted rather than guessed.

> PDF scraping is fragile by nature; every value carries its source line.

<details><summary>Verification notes from the source survey</summary>

wipo.int/global_innovation_index/en/ redirects to a modern JS-driven page with almost no static content, and the interactive wipo.int/gii-ranking/en/ page is likewise a near-empty JS shell (3KB) - neither is scrapable directly. The actual report PDFs live in WIPO's TIND institutional repository. Confirmed via HEAD: the URL 302-redirects to a watermarked-download endpoint (TIND's normal file-serving flow), which is a strong signal the file is real and servable. Report PDF's annex contains the full country score/rank table; no separate machine-readable XLSX was found.

</details>

### World Bank Open Data — Indicators API

- **Status** — live
- **Coverage** — 15/15 countries, 1990-2026 (per-indicator coverage varies by country)
- **Rows processed** — 3,203
- **Fetched** — 2026-08-04T19:10:45+00:00
- **Licence** — CC BY 4.0 — World Bank Open Data. Cite: World Bank, World Development Indicators.
- **Output** — `data/processed/world_bank.json`
- **Fetch script** — `scripts/src_world_bank.py`

**URLs**

- <https://api.worldbank.org/v2/country/AUS;USA;CAN;GBR;IRL;DEU;NLD;ITA;ESP;SWE;DNK;NOR;FIN;ARE;QAT/indicator/NY.GDP.PCAP.CD?format=json&per_page=20000&date=1990:2026>
- <https://api.worldbank.org/v2/country/AUS;USA;CAN;GBR;IRL;DEU;NLD;ITA;ESP;SWE;DNK;NOR;FIN;ARE;QAT/indicator/NY.GDP.PCAP.PP.CD?format=json&per_page=20000&date=1990:2026>
- <https://api.worldbank.org/v2/country/AUS;USA;CAN;GBR;IRL;DEU;NLD;ITA;ESP;SWE;DNK;NOR;FIN;ARE;QAT/indicator/FP.CPI.TOTL.ZG?format=json&per_page=20000&date=1990:2026>
- <https://api.worldbank.org/v2/country/AUS;USA;CAN;GBR;IRL;DEU;NLD;ITA;ESP;SWE;DNK;NOR;FIN;ARE;QAT/indicator/SL.UEM.TOTL.ZS?format=json&per_page=20000&date=1990:2026>
- <https://api.worldbank.org/v2/country/AUS;USA;CAN;GBR;IRL;DEU;NLD;ITA;ESP;SWE;DNK;NOR;FIN;ARE;QAT/indicator/SM.POP.NETM?format=json&per_page=20000&date=1990:2026>
- <https://api.worldbank.org/v2/country/AUS;USA;CAN;GBR;IRL;DEU;NLD;ITA;ESP;SWE;DNK;NOR;FIN;ARE;QAT/indicator/SP.POP.TOTL?format=json&per_page=20000&date=1990:2026>

**What we do to it**

1. Requested 6 indicators for the 15 covered countries in one call each (semicolon-joined ISO3).
1. Dropped rows with null values (World Bank returns nulls for unreported years).
1. Regrouped from flat rows to {ISO2: {indicator_key: [{year, value}]}} sorted ascending by year.
1. No smoothing, no interpolation, no imputation.

> Values are as published; gaps are left as gaps.

### World Happiness Report 2026 — Figure 2.1 data panel

- **Status** — live
- **Coverage** — 15/15 countries, 2011-2025
- **Rows processed** — 203
- **Fetched** — 2026-08-04T19:20:16+00:00
- **Licence** — World Happiness Report data is free to use with attribution. Cite: Helliwell et al., World Happiness Report 2026.
- **Output** — `data/processed/world_happiness_report.json`
- **Fetch script** — see `scripts/`
- **Historical range** — 2011-2025 (within the WHR26 file, 2013 appears absent); earlier per-report vintage files exist but do not form one unbroken 2005+ panel

**URLs**

- <https://files.worldhappiness.report/WHR26_Data_Figure_2.1.xlsx>

**What we do to it**

1. Read the single 'Data for Figure 2.1' sheet from the published xlsx.
1. Matched columns by header prefix (life evaluation + the six explanatory components).
1. Resolved country names to ISO2 and kept our 15; unmatched names dropped, never guessed.
1. Computed the per-year ranked-country count so ranks can be shown with a denominator.
1. No interpolation across the missing 2013 wave.

> Scores are 3-year rolling averages, so year-on-year moves are damped by construction.

<details><summary>Verification notes from the source survey</summary>

data.worldhappiness.report/table is a client-side-rendered Next.js app with no static download link exposed to curl. Real files live on a separate domain, files.worldhappiness.report, linked from https://www.worldhappiness.report/data-sharing/ (note: bare worldhappiness.report redirects to the www subdomain; a guessed /data/ path 404s). Verified by unzipping the xlsx: columns are Year, Rank, Country name, Life evaluation (3yr avg), whiskers, 6 factor columns; 2117 data rows, ~140 countries/year. Task wanted 2005+ but true 2005-2010 data is NOT in this file - would need older per-report appendix files (WHR12_Data.xlsx, WHR15_Ch03_Data.xlsx, etc., also confirmed present) as supplements.

</details>

### Open-Meteo ERA5 archive — 1991-2020 monthly climate normals

- **Status** — partial
- **Coverage** — 21/73 cities x 12 months, 1991-2020 (WMO standard reference period)
- **Rows processed** — 252
- **Fetched** — 2026-08-05T00:29:41+00:00
- **Licence** — Open-Meteo data is CC BY 4.0; underlying ERA5 is Copernicus Climate Change Service information. Cite: Open-Meteo / Copernicus ERA5.
- **Output** — `data/processed/climate_normals.json`
- **Fetch script** — `scripts/src_climate_normals.py`

**URLs**

- <https://geocoding-api.open-meteo.com/v1/search?name=<city>>
- <https://archive-api.open-meteo.com/v1/archive?latitude=..&longitude=..&start_date=1991-01-01&end_date=2020-12-31>

**What we do to it**

1. Geocoded each city, keeping only hits whose country code matches the city's own (there are five Valencias) and preferring the largest by population.
1. Fetched daily max/min temperature and precipitation for 1991-01-01..2020-12-31 (10,958 days per city).
1. Aggregated to 12 calendar-month normals: mean daily max, mean daily min, their midpoint, mean count of days with >= 1 mm precipitation, and mean monthly precipitation total.
1. Wrote the series to climate.monthly on each city record. Existing annual climate fields were NOT modified — they come from station data and are kept as an independent signal.

> Reanalysis, not station observations — tagged 'index' rather than 'official'.

## Sources we could not get

These are documented at the same level of detail as the working ones. The site renders nothing for them rather than filling the gap.

### IMF World Economic Outlook — country projections — blocked

- **Why** — imf.org is unreachable from this environment (HTTP 403 at the Akamai edge). The parser is complete and runs wherever IMF is reachable; a manual drop-in path is documented.
- **Attempted** — 2026-08-04T20:49:37+00:00
- Tried: <https://www.imf.org/-/media/Files/Publications/WEO/WEO-Database/2026/April/WEOApr2026all.ashx>
- Tried: <https://www.imf.org/-/media/Files/Publications/WEO/WEO-Database/2026/october/WEOOct2026all.ashx>
- Tried: <https://www.imf.org/external/pubs/ft/weo/2026/01/weodata/WEOApr2026all.xls>

### World Bank Global Economic Prospects — growth forecasts — unavailable

- **Why** — No parseable GEP data file was discoverable at build time. The forecast layer does not depend on it — OECD EO and UN WPP supply attributed projections.
- **Attempted** — 2026-08-04T20:49:52+00:00
- Tried: <https://www.worldbank.org/en/publication/global-economic-prospects>

## Manual drop-in sources

Some well-known datasets are paid, gated, or unreachable from automated builds. They are supported as documented hand-placed files rather than pretended-away.

| Source | How to obtain it | Where to put it |
| --- | --- | --- |
| IMF World Economic Outlook | imf.org → Publications → WEO → *World Economic Outlook Databases* → download the entire database (free, tab-delimited). | `data/manual/imf_weo.json` — see the shape documented at the top of `scripts/src_imf_weo.py`. |
| EIU liveability & cost of living | Paid report. Quote the headline figure only. | Forecast card in `data/manual/forecast_cards.json` with source and date. |
| Knight Frank / CBRE / JLL housing outlooks | Free registration, per-report PDFs. | Forecast card, attributed and dated. |
| Gartner / IDC tech market forecasts | Paid. Press releases carry citable headline numbers. | Forecast card, attributed and dated. |
| StatCan occupation counts | Table 14-10-0335-01, inactive since 2022. | `data/manual/` drop-in; documented as historical only. |
| Jobs and Skills Australia / ABS | ABS labour-force releases. | `data/manual/` drop-in. |

Forecast cards are rendered as attributed quote-cards — a headline figure, the institution, and the date — never merged into a chart line.

## Confidence tiers

- **official** — Government/statistical body (gov sites, BLS, OECD, WMO)
- **index** — Established published index (WHR, GPI, EF EPI, HDI)
- **crowd** — Crowd-sourced or survey (Numbeo, levels.fyi, InterNations, Glassdoor)

## Staleness rules

A figure older than its rule shows a warning on the site rather than being hidden.

- `visa` — warn after 6 months
- `prices_salaries` — warn after 12 months
- `indices` — warn after 18 months
- `climate` — warn after 120 months

