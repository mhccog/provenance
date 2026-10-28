# Provenance

**Live:** https://mhccog.github.io/provenance/

A daily desk of rare, actionable deals to broker, built only from public records. Four desks:

| Desk | What it finds | Sources (licence) |
|---|---|---|
| **Revival broker** | Sleeping beauties: lapsed heritage trade marks (watches, jewellery, perfume, spirits, leather, tailoring, motoring, porcelain); dissolved houses and marques with no recorded successor; much-loved software whose makers walked away; clinical trials stopped for money, not safety | UK IPO open data snapshot Feb 2018 (OGL v3), Wikidata (CC0), GitHub API, ClinicalTrials.gov (US Gov), optional Companies House API (OGL v3) |
| **Import scout** | Luxury, craft and hospitality brands with many locations abroad and none mapped in the UK | OSM name-suggestion-index (BSD-3), taginfo worldwide + Geofabrik UK (ODbL), Wikidata (CC0) |
| **Treasure hunter** | UK companies entering insolvency in the last 21 days in asset-rich sectors (distilleries, hotels, jewellers, ateliers, coachbuilders, boatyards, galleries, studios, equestrian…), with the office-holder named in the notice and possible buyers nearby | The Gazette (OGL v3), Companies House links (OGL v3), OpenStreetMap via Overpass (ODbL) |
| **Twin finder** | Makers and teams in different countries building the same rare thing, with no sign they know each other | GitHub API, mhccog/not-the-only-one (OpenAlex/arXiv/GitHub/HN), Crossref (open metadata), Photon geocoder (ODbL) |

Each lead has: why it's worth your time, a first move (public professional channels only), an outreach draft to copy (nothing is ever sent), a content angle, a suggested deal, sources with licence and trust level, and a status and notes stored in your browser's `localStorage`.

## Trust and audit

`scripts/audit.py` runs daily in the workflow:
- **Schema**: leads are exported to `docs/data/leads.csv` and validated with [frictionless-py](https://framework.frictionlessdata.io/) against `leads.schema.json`.
- **Links**: a sample of source links per source is checked with [lychee](https://github.com/lycheeverse/lychee) (`lycheeverse/lychee-action`). Failing links are flagged on their cards.
- **Spot-checks**: about 10 records per source are re-read from the original publisher and compared (Gazette page, ClinicalTrials.gov record, GitHub repo, Wikidata entity, taginfo counts, Crossref titles). Mismatches are flagged and demoted.

Ratings and known issues for every source are in `docs/data/sources.json`, shown on the **Sources & trust** page.

## Refresh

`.github/workflows/refresh.yml` runs daily at 05:17 UTC. Each desk keeps its last good copy if a source is down, and the page says so.

The trade mark snapshot is static: the IPO hasn't published bulk data since 2018. To rebuild `data-static/sleeping-marks.json`, download `opendatadomestic.zip` from the IPO page, unzip it and run `python3 scripts/prepare_trademarks.py OpenDataDomestic.txt`.

## Optional free keys (Actions secrets; never committed)

| Service | Sign up | Secret | Adds |
|---|---|---|---|
| Companies House API | https://developer.company-information.service.gov.uk/get-started | `COMPANIES_HOUSE_API_KEY` | Dissolved heritage companies in luxury SIC codes; SIC codes for Gazette companies |
| OpenAlex | https://openalex.org/settings/api | `OPENALEX_API_KEY` | Researchers working on a stopped trial's drug; fresher research twins |
| EUIPO open data | https://euipo.europa.eu/ohimportal/en/open-data | `EUIPO_CLIENT_ID`, `EUIPO_CLIENT_SECRET` | EU status of sleeping-beauty marks |

## Rules

Disclose every referral fee. Some are banned in the UK, such as personal injury referral fees under LASPO 2012 ss.56–60, and regulated financial introductions need authorisation. Outreach to individuals relies on legitimate interest: keep it brief and relevant, and always offer an opt-out. See the **Rules** page.

## Run locally

```
cd scripts && python3 build_closing.py && python3 build_revival.py && python3 build_import.py && python3 build_twins.py && python3 build_desk.py && python3 audit.py && python3 build_desk.py
cd ../docs && python3 -m http.server 8791
```

Basemap: Natural Earth (public domain). Map: MapLibre GL JS (BSD-3). Fonts: Fraunces and Inter (SIL OFL).
