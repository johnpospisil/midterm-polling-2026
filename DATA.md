# Data sources, terms and status

Every status note is dated. Re-check before each publish (P11, P20).

**Checked 2026-11-09** (P01 access check). Raw probe responses are in `data/raw/_probe/` (gitignored).

## Summary

| # | Source | What it gives us | Access | Terms / licence | Bots & robots.txt | Final pre-election numbers? | Use in this project |
|---|---|---|---|---|---|---|---|
| a | **Wikipedia 2026 race pages** (35 Senate, 38 governor, 52 House state pages, overview pages) | Every public poll (pollster, sponsor, dates, n, LV/RV/A, MoE, toplines), aggregator final averages per race, forecaster ratings columns, unofficial results | MediaWiki API (`action=query&prop=revisions`, `action=parse&oldid=`), no key | **CC BY-SA 4.0**. Anything we publish that's derived from it (the poll table) must be CC BY-SA 4.0 with attribution | `/w/` is disallowed for crawlers, but Wikimedia's bot policy directs automated clients to the API. **The User-Agent must include a full `https://` contact URL and the library name**, or requests get a 403 (seen today) | **Yes, permanently**: revision history keeps each page as of election eve. Last pre-election revisions are mostly Nov 3, 05:00–11:00 UTC | **Primary 2026 poll source.** Aggregator averages and ratings are taken from Wikipedia's tables, which cite each aggregator |
| b1 | **Silver Bulletin** (natesilver.net) | Polling averages + final forecast (dated Nov 3, 2026) | Web page; toplines **paywalled** | © Nate Silver; no reuse licence stated | Robots.txt blocks named AI crawlers; general `*` allowed | Yes (live, paywalled); 25 Wayback captures Oct 25–Nov 4 | Comparison only: per-race final averages via Wikipedia's tables; forecast probabilities only if visible without a paywall |
| b2 | **270toWin** | Polling averages | Web page | Terms page not found today (404) → **unclear** | Robots.txt blocks named AI crawlers; `*` allowed | Live page; no Wayback captures of the polls page Oct 25–Nov 4 | Comparison only, via Wikipedia's tables |
| b3 | **Decision Desk HQ** | Polling averages + forecast (House/Senate/governor) | Web page; returns **429** to automated requests | Terms page not reachable (404) → **unclear** | robots.txt itself returns 429 | Live forecast page; **no Wayback captures** Oct 25–Nov 4 | Comparison only: averages via Wikipedia's tables; forecast numbers by manual transcription from the live page if it still shows the final version |
| b4 | **FiftyPlusOne** | Poll database (with methods fields), averages, Senate/House forecast | CSV API, **API key required**; forecasts and averages are Premium | **Restrictive**: personal, non-commercial licence; "redistribution, or publication of API Data" prohibited; attribution "Powered by FiftyPlusOne" required; 50 requests/hour | Robots.txt blocks named AI crawlers | Forecast page: 20 Wayback captures, last Nov 3, 22:40 UTC (before polls closed) | **Comparison only, no redistribution.** Don't use the API for the poll table. Final averages via Wikipedia's tables; forecast via the Wayback capture |
| b5 | **RealClearPolling** | Polling averages, race ratings | Web page; returns **403** to automated requests | Terms page blocked (403) → **unclear** | robots.txt itself returns 403 | 9 Wayback captures, last Nov 2, 02:16 UTC | Comparison only, via Wikipedia's tables |
| b6 | **Race to the WH** | Polling averages + forecast | Web page | No terms stated on page → **unclear** | Robots.txt blocks named AI crawlers | 1 Wayback capture (Oct 31) | Comparison only, via Wikipedia's tables (cited on 9–11 race pages) |
| c1 | **The Economist** model | Senate/House win probabilities | Web page; **403** to automated requests | © The Economist; restrictive by default | Robots.txt blocks named AI crawlers | Live page; Wayback captures all failed | Ratings column via Wikipedia only; probabilities only if available manually |
| c2 | **Split Ticket** (published at The Argument) | Senate/House probabilities + modelled margins; "Get the Data" download | Web page + download | © 2026; reuse not stated → **unclear** | Robots.txt allows; no AI blocks | 2 Wayback captures, last Nov 3, 22:45 UTC | Candidate for chart 6 if the download is public |
| c3 | Race-rating outlets (Cook, Inside Elections, Sabato, Fox, NBC, MS NOW, RCP) | Categorical ratings only (Safe/Likely/Lean/Toss-up) | Via Wikipedia's ratings table (dated per column, Oct 29–Nov 3) | Ratings are facts cited on Wikipedia (CC BY-SA) | — | Yes, in Wikipedia's pre-election revision | Optional: ratings vs results in chart 6 |
| d1 | **FiveThirtyEight `fivethirtyeight/data`** on GitHub, `pollster-ratings/raw_polls.csv` | 20,466 poll-questions, 1998–2022 cycles, with poll **and** actual margins, mode (`methodology`), partisan flag, AAPOR/Roper flag. Polls up to 61 days out (median 19) | Public GitHub, no key | **CC BY 4.0** (repo licence) | — | n/a (historical) | **2014 and 2016 history** (final weeks only) and a cross-check for 2018–2022. **Has no 2024 cycle** |
| d2 | **FiveThirtyEight poll CSVs via Wayback** (`projects.fivethirtyeight.com/polls-page/data/*_historical.csv`) | Full poll time series for 2018, 2020, 2022, 2024 (Senate file: 9,292 rows; also governor, House, generic ballot, president) | Wayback Machine, last good capture 2025-03-06; the live URLs now redirect to ABC News | 538 published its data under CC BY 4.0. Confirm the notice on the archived polls page before publishing | — | n/a (historical) | **2018–2024 history** with full time series, including **2024** |
| e1 | **State election offices** | Unofficial and certified results | Per-state web pages and downloads; formats vary | Public records | Some block or time out automated requests (Michigan SOS: 403 / timeout today); PA and GA returned 200 | n/a | **Primary results source**; manual download where automation is blocked |
| e2 | **Wikipedia results tables** | Unofficial results already posted (e.g. Michigan Senate current revision) | MediaWiki API | CC BY-SA 4.0 | as (a) | n/a | Cross-check only |
| e3 | **MEDSL** (Harvard Dataverse) | Statewide returns, Senate 1976–2024 (updated 2026-05-11), 2022 precinct data | Dataverse API, no key | Open (check each dataset's licence, usually CC0) | — | **No 2026 data yet** | Historical results; 2026 cross-check in P21 |
| f | **Census ACS 5-year API** | Education, Hispanic share, density for states and congressional districts | `api.census.gov`; **now requires an API key** ("Missing Key" response today) | Public domain (US government) | Allowed | n/a | P15 demographics. **Needs a free API key** |
| g | **Internet Archive Wayback Machine** | Archived snapshots (CDX API + `id_` raw captures) | No key; be gentle (≥1 s between calls) | IA terms allow research use; **rights in archived content stay with the original site**, so a Wayback copy carries the same terms as the original | — | See rows above | Fallback for final forecasts; source for 538's 2018–2024 CSVs |

## Findings that change the plan

1. **Polls are safe.** Wikipedia revision history keeps every page as of election eve, so the 2026 poll table doesn't depend on any aggregator. About 2,020 general-election poll rows across 62 Senate and governor races, including hypothetical matchups that P03 will drop. 30 races have 20+ rows.
2. **Aggregator averages come from Wikipedia's "Source of poll aggregation" tables.** These list each aggregator's final average per race with dates and a citation: Silver Bulletin (43 pages), 270toWin (39), DDHQ (38), FiftyPlusOne (38), RealClearPolitics (37), Race to the WH (~11). This avoids scraping sites whose terms are unclear or restrictive.
3. **Forecast probabilities are the weak spot.** The probabilistic models are DDHQ, the Economist, FiftyPlusOne, Silver Bulletin and Split Ticket. All are paywalled, block automated requests, or have unclear or restrictive terms. Plan: take only a handful of final numbers per race (win probability, projected margin), by hand or from the Wayback capture closest to election eve, and cite each. Never bulk-redistribute them.
4. **History needs two 538 sources.** `raw_polls.csv` (CC BY 4.0) covers 2014–2022 but only the final weeks before each election and **lacks 2024**. The Wayback copies of 538's `*_polls_historical.csv` cover 2018–2024 with full time series. For 2014–2016, the model's time trend can only use late polls.
5. **Licence for what we publish:** the 2026 poll table is derived from Wikipedia, so it must be released under **CC BY-SA 4.0** with attribution. Code stays under the repo's code licence.
6. **Parser note for P03:** Minnesota's pages show 0 poll rows in the quick survey because Democrats appear as "(DFL)", not "(D)". Party tags need a mapping.
7. **Wikimedia User-Agent:** `mp-polling-postmortem/0.1 (https://github.com/johnpospisil/midterm-polling-2026) httpx/0.28` works. Without the `https://` URL and library token, httpx requests get a 403.

## P02 capture (2026-11-09)

| What | Where | Count / as-of |
|---|---|---|
| Wikipedia pages, election-eve revision (last before 2026-11-03 11:00 UTC) + current revision | `data/raw/wikipedia/<page>/<revid>.{html,wikitext}`, `manifest.csv` (revid, timestamps, sha256) | 126 pages × 2 = 252 revisions, 198 MB: 35 Senate, 36 governor, 52 House state pages, 3 overview pages. Election-eve revisions range from 2026-10-24 (quiet pages) to 2026-11-03 10:52 UTC |
| Aggregator final averages | `data/processed/final_averages.parquet` (from Wikipedia "Source of poll aggregation" tables) | 20 Senate + 21 governor races + generic ballot. Silver Bulletin 42 race rows, 270toWin 36, DDHQ 34, RCP 34, FiftyPlusOne 33, NBC 1 (generic), Texas Tribune 1. Race to the WH appears only in primary or hypothetical tables, so it has no final averages |
| Forecaster ratings | `data/processed/final_forecasts.parquet` (`kind = rating`) | From the overview pages' ratings tables: Cook, DDHQ, Fox, IE, NBC, RCP, Sabato, Silver for all 71 races; Economist, FPO, MS NOW, Split Ticket for the 35 Senate races. Rating dates Oct 29–Nov 3 |
| Split Ticket model | `data/raw/forecasts/splitticket/*.csv` + `meta.json`; `final_forecasts.parquet` (`kind = model`) | Win probability + projected margin, 35 Senate + 435 House races (no governors). Datawrapper versions last modified **2026-11-03 04:06–04:08 UTC** (election eve); `snapshot.py` takes the last version before the cutoff. Chamber control: D 76.8% Senate, 92.4% House |
| Wayback captures | `data/raw/forecasts/wayback/` | Silver Bulletin landing, Senate and generic pages (paywalled: free text only); FiftyPlusOne (empty JavaScript shell, **no data**); Split Ticket article |

**Rules used to choose the final-matchup table:** nominees and parties come from the election-eve infobox. An aggregation table is kept only if every candidate column matches a nominee, by first name + surname, or by surname alone when it's unique. This handles untagged headers (NH Senate), the top-two primary table (CA governor), replaced candidates (ME Senate: Troy Jackson replacing Graham Platner; SC Senate: Darline Graham replacing Lindsey Graham), and shared surnames (AK Senate: Dan S. Sullivan (R) vs Daniel J. Sullivan Jr. (I)). Where there's no Democrat, the independent is the D side (NE Senate: Dan Osborn).

**Not captured:** DDHQ and Economist win probabilities (both block automated access); Silver Bulletin and FiftyPlusOne race-level probabilities (paywalled, or the capture holds no data). Their categorical ratings are in the table above.

**Polls added after the election:** 9 races have 1–3 more poll rows in the current revision than on election eve (CO gov/Sen, FL gov/Sen, IL gov, AR Sen, ID Sen, MI Sen, NE Sen). See the P03 question.

## P03 race registry and raw poll table (2026-11-09)

- **`data/reference/races.csv`** (committed; **CC BY-SA 4.0**, as nominees and ratings come from Wikipedia): 507 rows = 35 Senate + 36 governor + 435 House + generic ballot. Statewide nominees come from the election-eve infobox. House nominees come from Split Ticket's final district table (names only, as facts; **no Split Ticket probabilities or margins are committed**). Flags: `rcv` (AK; ME federal), `top_two` (CA, WA), `top_four` (AK), `nominee_placeholder` (5 Louisiana House seats show "Eventual Nominee" in Split Ticket's final table), `replacement_note` (ME Sen, SC Sen, NM gov).
- **Generic-ballot polls** are in `Template:2026 United States elections/polling` (election-eve revid 1383518721, 2026-11-03 03:11 UTC), not on the House overview page. Since Nov 5 the template is shown on a new page, "2026 United States elections polling".
- **`data/processed/polls_raw.parquet`** (gitignored): 2,654 rows from current revisions plus 3 rows removed after the election (flagged). Senate 815 rows (30 races), governor 722 (34 races), House 381 (113 districts), generic ballot 736. Final three weeks: 261 Senate, 237 governor, 93 House, 50 generic. 32 statewide races have 5+ polls in the final three weeks.
- **Table selection:** a table is kept only if both principals are among its candidate columns, which drops primaries and hypothetical matchups. Skipped tables are in `polls_parse_log.csv`: 311 not-final-matchup, 288 primary or convention, 48 annotation rows, 18 statewide congressional polls on House pages. A check for tables that contain both principals' surnames yet were skipped found **0**.
- **Row issues** (`data/processed/p03_parse_issues.csv`): 63 with no sample size, 10 where a principal wasn't offered, 3 month-only dates, 1 reversed date range in the source ("July 8–6", NV gov; flagged, not fixed).
- **Post-election edits:** 16 rows added after the election (field end ≤ Nov 2), 2 edited, 3 removed.

## P04 poll table (2026-11-10)

**`data/processed/polls.parquet`** (gitignored), one row per poll × race:

| Step | Rows |
|---|---|
| Rows in polls_raw | 2,657 |
| − removed from Wikipedia after the election | 3 |
| − fieldwork ended after election eve | 0 |
| − a principal candidate not offered | 10 |
| − exact duplicate rows | 3 |
| − other versions of the same poll | 514 |
| **= polls** | **2,127** (Senate 646, governor 593, House 339, generic 549) |

- **Version rule** (same race, pollster, field dates, even across tables): RCV round 1 > plain vote > later rounds; LV > V > RV > A; full ballot over head-to-head; "with leaners" (smallest unallocated share); first listed.
- **Margins** are two-party D − R (`margin`), with `dem_2p` and raw `margin_raw`. Dates: `field_mid` (rounded down), `days_before` (to 2026-11-03), `week_before`.
- **Sponsors:** Wikipedia's (D)/(R) tag after a pollster's name marks the **firm**. Sponsors are in a separate footnote group, "Partisan clients", which also lists news outlets and nonprofits. `sponsor_class` = `candidate_internal` (175 polls), `party_committee` (16), `partisan_client` (258), `sponsored_nonpartisan` (110: media, academic, AARP…), `affiliated_pollster` (565: firm tag only), `nonpartisan` (1,068). `is_partisan` is true for the first three. Share of polls that are partisan: Senate 19%, governor 18%, House 45%, generic ballot 0%.
- **User review files** (`review/`, kept across rebuilds): `sponsors_for_review.csv` (250 sponsors; `partisan_Y_N` overrides the automatic class) and `double_entry_sample.csv` (212 polls = 10%, seeded; priority 1 = Senate/governor polls in the final three weeks, 36 rows).

## Sources that block reuse, and fallbacks

| Source | Blocker | Fallback |
|---|---|---|
| FiftyPlusOne API | Bans publishing or redistributing API data; needs a key | Its final averages as cited in Wikipedia's tables; forecast numbers from the Nov 3 Wayback capture, as a comparison only |
| Silver Bulletin | Paywall | Final averages via Wikipedia's tables; forecast only if the free view or a Wayback capture shows it |
| DDHQ, RCP, Economist | Block automated access; terms unreadable | Wikipedia's tables; manual transcription of a few final numbers if the pages still show them |
| 270toWin, Race to the WH | Terms unclear | Wikipedia's tables |

## Open items

- [x] Census API key: stored as `CENSUS_API_KEY` in `.env` (gitignored); ACS 2024 5-year call verified 2026-11-09.
- [ ] Confirm the CC BY 4.0 notice on the archived 538 polls page (2025-03-06 capture) before publishing 2018–2024 derived data.
- [x] Split Ticket "Get the Data": free Datawrapper download offered by the publisher; no licence stated. Use cited per-race numbers for comparison only (2026-11-09).
- [x] DDHQ and Economist probabilities: skipped by user decision (2026-11-09); their ratings are used instead.
