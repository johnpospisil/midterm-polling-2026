# CLAUDE.md — Project 24: How Wrong Were the Polls? (2026 Midterms)

Spec: [24-midterm-polling-postmortem.md](24-midterm-polling-postmortem.md). Repo: github.com/johnpospisil/midterm-polling-2026 (public).

## Role and voice

Act as a senior data scientist whose priority is making results understandable to the general public, not only to other data scientists or pollsters. Every analysis has to be correct first and then explainable to a curious non-expert.

**Plain-language rules (apply to the report, chart titles, captions and README):**
- Lead with the finding, in one sentence a non-expert could repeat at dinner. Put the method after it.
- Make errors concrete: "Polls had Democrats 2 points too high in the typical Senate race" rather than "mean signed error of +2.0".
- Define a technical term in the sentence where it first appears (house effect = "a pollster's consistent lean relative to other polls of the same race, usually caused by its methods").
- Chart titles state the takeaway; subtitles say what is plotted. Every chart gets alt text.
- Use colorblind-safe palettes (load the `dataviz` skill before any chart), make charts readable on a phone, and label directly instead of relying on legends where possible. Don't use red/blue party colors as the only cue.
- Describe uncertainty in words as well as intervals ("we're fairly confident", "this could be noise").
- **Strictly non-partisan.** Same rules for both parties. Never call a pollster "biased" in a partisan sense (spec §5, "What you won't claim").

## Decisions (made 2026-11-09)

| Decision | Choice |
|---|---|
| Sign convention | Margin = Dem share − Rep share of the **two-party** vote. Signed error = poll margin − result margin, so **positive = polls overstated Democrats**. Used everywhere, tested. |
| Race ids | `SEN-PA-2026`, `GOV-GA-2026`, `HOU-AZ06-2026`, `GEN-US-2026` (generic ballot) |
| Scope | Senate + governor are primary; House districts and generic ballot are secondary |
| Model | Bayesian hierarchical model in Stan via `cmdstanpy` (`models/hier_bias.stan`) |
| Release | **Two releases**: (1) "First look" on called/unofficial results, labelled PRELIMINARY, **~Mon Nov 24**; (2) final post-mortem on certified results, **~Thu Dec 18** |
| Venue | Quarto site on GitHub Pages; race explorer embedded with Observable JS |
| Project 34 | **Independent.** No shared deadlines or joint release. Chart 6 compares polls against **forecasters** only (no prediction markets). |
| Reviewer | Find a survey methodologist (Prompt P09); send the full draft ~Dec 8 |
| Data terms | Primary sources and CC-licensed tables only; respect robots.txt; cite everything in DATA.md with dates |
| Forecasters (chart 6) | Split Ticket, FiftyPlusOne (Nov 3 Wayback capture), Silver Bulletin if its free view shows the numbers. DDHQ and the Economist only if their live pages still show final numbers that can be transcribed by hand |
| Unclear-terms sources | Take only a few cited final numbers per race (win probability, projected margin) by hand or from Wayback; use for comparison; **never bulk-redistribute**. Aggregator averages come from Wikipedia's tables |
| Late-added polls | Use the current Wikipedia revision; keep polls with field end ≤ 2026-11-02; flag those missing from the election-eve revision `added_post_election`; robustness check without them |
| Non-standard contests (2026-11-10) | No Democrat → the independent is the D side (ID, NE, SD Sen; AK House), flagged for a check without them. RCV races (AK; ME Sen/House) → first-round shares, same rule for every pollster. 3-way races → margin is D side minus R side only; the third candidate's share is kept in `candidates`. Same-party top-two contests are dropped automatically (no R side) |
| DDHQ / Economist probabilities | Skipped (blocked); chart 6 uses their ratings only |
| Census | ACS 5-year 2024; key in `.env` as `CENSUS_API_KEY` (verified 2026-11-09) |

## Timeline

Today is Mon 2026-11-09, six days after the election (Tue Nov 3). The pre-election snapshotter planned in Project 34 (B1) **never ran**, so the "before Nov 3" work starts now. Waits on things outside our control are marked ⏳.

| Dates | Phase | Prompts | Why this timing |
|---|---|---|---|
| **Nov 9–11** ⚠️ | Access check + **freeze the pre-election record** | P01, P02 | Aggregator and forecaster pages get archived, overwritten or deleted in the weeks after an election. Wikipedia history is permanent, but other sites aren't. |
| Nov 10–14 | Poll table, pollster table | P03, P04, P05 | Needs only the frozen pre-election data, so no waiting |
| Nov 13–14, then weekly | ⏳ Provisional results (called / unofficial) | P06 | Most statewide counts are close to complete ~10 days out; slow states (CA, AK, some House seats) keep counting. Rerun every Monday until certification. |
| Nov 14–20 | Historical baseline 2014–2024 + model built and fitted on history | P07, P08 | No waiting; done now so the 2026 fit is quick once results settle |
| **By Thu Nov 20** | Reviewer outreach | P09 | Reviewers need 2+ weeks' notice to review a draft in early December |
| Nov 18–24 | First-look analysis + **publish first look ~Nov 24** | P10, P11 | Called results are stable enough for a descriptive, clearly labelled preliminary post |
| Nov 24–Dec 8 | Full model, methods, herding, demographics, forecasters, explorer, full draft | P12–P18 | Run on near-final unofficial counts; only small changes are expected at certification |
| ⏳ Dec 1 | Possible runoffs (verify in P06 whether any 2026 race goes to a runoff) | — | — |
| ⏳ ~Dec 1–12 | States certify (most by early Dec; California certifies ~38 days after the election, ≈ Dec 11; verify stragglers in P06's certification calendar) | — | Final numbers can't be locked before the last relevant state certifies |
| Dec 11–14 | Swap in certified results, rerun everything | P19 | Right after the last state certifies |
| Dec 15–18 | QA, reviewer feedback, **publish final ~Dec 18** | P20 | — |
| 2027 (when released) | ⏳ MEDSL 2026 data; stretch goals | P21 | MEDSL usually publishes months after the election |

**Slack:** if certification slips (e.g. California later than Dec 11), publish the final with that state's unofficial-but-complete count clearly marked, or push to the week of Jan 5. Don't publish between Dec 22 and Jan 2, when readership is low.

## Working conventions

- Python via `uv` (3.13); package `src/mp/`; layout follows spec §7. `make` targets: `ingest`, `build`, `models`, `figures`, `report`, `test`, `lint`.
- Raw downloads are cached to `data/raw/<source>/` (gitignored) with a `manifest.csv` (url, revision/snapshot id, fetched_at UTC, sha256). Processed tables go to `data/processed/*.parquet`. Hand-curated, cited tables go to `data/reference/*.csv` (committed).
- Ingest code is polite (rate-limited, retries with backoff, identifies itself with a generic project User-Agent, not the user's email), resumable and idempotent.
- Results rows always carry `status` (`called` / `unofficial` / `certified`), `source_url` and `as_of` date. Never overwrite a provisional row; append a new version.
- Tests (pytest): margin sign convention, two-party conversion, dedupe rules (LV preferred; same poll from multiple sources counted once), results totals vs official totals, and parameter recovery for the Stan model on simulated data.
- Record each source's terms of use in `DATA.md`, **dated**. Re-check before each publish.
- Skills: `superpowers:test-driven-development` for build/model code, `dataviz` before any chart, `data:validate-data` before each publish, `artifact-design` for any HTML deliverable.

## Checkpoint rule (applies to every prompt)

At the end of each prompt, **stop and present the checkpoint**: show the listed deliverables (chart images, tables, links, counts), say what was surprising, and ask the listed questions. Don't start the next prompt until the user replies. Then tick the prompt below (`- [x] ✅ DONE! … _Done YYYY-MM-DD: one-line result_`) and add a line to **Status**.

---

## Prompts

Copy each prompt into Claude Code in order. "When" is the earliest sensible start and the target finish.

### Phase 0: Access check and freeze the pre-election record (Nov 9–11) ⚠️

- [x] ✅ DONE! **P01: Access check and DATA.md.** _Done 2026-11-09: Wikipedia revision history covers every 2026 poll (~2,000 Senate/governor rows); aggregator averages come via Wikipedia's tables; 538 history = raw_polls.csv (2014–22) + Wayback CSVs (2018–24); forecasters are the weak spot; Census now needs a key._
  **When:** Mon Nov 9 – Tue Nov 10. Do it first.
  > Run spec §0. For each candidate source, record in DATA.md (dated today): what it has, grain, how to access it, terms/licence (quote and link the reuse clause), robots.txt status, and whether it still has its **final pre-election** numbers. Sources: (a) Wikipedia 2026 Senate, governor, House and generic-ballot poll pages (CC BY-SA, via the MediaWiki API); (b) public polling aggregators and averages active in 2026 (research which exist, e.g. RealClearPolling, 270toWin, Silver Bulletin, VoteHub, Decision Desk HQ, NYT/others), checking each one's terms for downloadable CSVs; (c) public forecasters' final 2026 race forecasts; (d) FiveThirtyEight historical data still on GitHub for 2014–2024 (polls and pollster ratings/raw-polls); (e) results: state election office unofficial and certified pages, Wikipedia results tables as a cross-check, and MEDSL (note it won't have 2026 yet); (f) Census ACS 5-year API for states and congressional districts; (g) the Internet Archive Wayback Machine as a fallback for (b) and (c). Save one probe response per source under `data/raw/_probe/`.

  **Deliverables:**
  - `DATA.md` with a dated source table (source × access / terms / coverage / still has final numbers?)
  - `data/raw/_probe/` with one raw sample per source
  - A short list of sources whose terms block reuse, and the fallback for each

  **Checkpoint questions:** Which aggregators and forecasters should be included? Should sources with unclear terms be skipped, or used only for comparison and not redistributed?

- [x] ✅ DONE! **P02: Freeze the pre-election record.** _Done 2026-11-09: 126 Wikipedia pages × (election-eve + current) frozen; aggregator averages for 41 races + generic ballot; ratings from 12 raters; Split Ticket final model (Senate + House) from Nov 3 Datawrapper versions. DDHQ/Economist probabilities not obtainable._
  **When:** Tue Nov 10 – Wed Nov 11. ⚠️ Don't delay. Sites change their pages after the election.
  > Write `ingest/wikipedia_polls.py` fetch mode: for every 2026 Senate, governor, generic-ballot and polled-House page found in P01, use the MediaWiki API to get the **last revision before 2026-11-03 06:00 ET** and the **current revision** (pollsters sometimes add late polls afterwards). Save raw HTML/wikitext with revision ids to `data/raw/wikipedia/` plus a manifest. Write `ingest/aggregators.py` and `ingest/snapshot.py` to capture each approved aggregator's final polling average and each approved forecaster's final probabilities and projected margins per race, from the live site if it still shows them, otherwise from the closest Wayback snapshot before Nov 3. Record the snapshot timestamp on every row. Write `data/processed/final_averages.parquet` and `final_forecasts.parquet`.

  **Deliverables:**
  - `data/raw/wikipedia/` (pre-election and current revisions) + `manifest.csv`
  - `data/processed/final_averages.parquet`, `data/processed/final_forecasts.parquet`
  - A coverage table: race × (Wikipedia polls? aggregator average? forecasts from whom?), with each snapshot's date

  **Checkpoint questions:** Are there races or sources with no pre-election snapshot? Should we accept a Wayback snapshot from several days before the election in those cases?

### Phase 1: Poll and pollster tables (Nov 10–14)

- [x] ✅ DONE! **P03: Race registry + Wikipedia poll parser.** _Done 2026-11-09: races.csv (507 races); polls_raw.parquet with 2,654 rows (Sen 815, Gov 722, House 381, generic 736); 0 silent table misses; 77 row issues listed._
  **When:** Wed Nov 11 – Thu Nov 12.
  > Build `data/reference/races.csv` (race_id, office, state, district, candidates with party, rating/competitiveness if available, special-election flag, runoff/RCV/top-two flags). Then write the parser half of `ingest/wikipedia_polls.py`: turn each poll table into raw rows (pollster, sponsor, field start/end, sample size, population LV/RV/A, mode if listed, every candidate's share, undecided, footnotes, source revision id). Handle merged cells, footnote markers, ranges like "±3.1", multiple versions of the same poll (LV/RV, with/without leaners, head-to-heads vs full ballots). Write the parser tests first using saved fixtures.

  **Deliverables:**
  - `data/reference/races.csv`
  - `data/processed/polls_raw.parquet` (one row per table row as published)
  - Parser tests passing on fixtures; a list of rows that failed to parse, with reasons

  **Checkpoint questions:** How should races without a standard D-vs-R contest be handled (D-vs-D top-two, independent instead of a Democrat, RCV races)? Recommended: exclude same-party races, treat a major independent as the "D side" with a flag, and use first-round shares for RCV.

- [ ] **P04: Poll table (margins, dedupe, flags).**
  **When:** Thu Nov 12 – Fri Nov 13.
  > Implement `build/margins.py` and `build/polls.py` per spec §4: one row per poll × race, two-party margin (D − R) using the CLAUDE.md sign convention, field-date midpoint, days before the election, n, population; prefer LV > RV > A when a poll publishes several; dedupe polls reported in multiple places; flag partisan/candidate-sponsored polls and internal polls. Tests first (sign convention, two-party conversion, dedupe rules, LV preference). Export a random 10% sample to `review/double_entry_sample.csv` with source links for me to check by hand against the original pollster release.

  **Deliverables:**
  - `data/processed/polls.parquet`
  - A dedupe waterfall ("N raw rows → dropped X duplicates → Y RV/A versions → final N polls")
  - Poll counts by office, by week before the election, and for the top 20 pollsters
  - `review/double_entry_sample.csv` for my hand check

  **Checkpoint questions:** What should the cutoff be for "final polls": last 2 weeks, last 3 weeks, or last poll per pollster? Should partisan-sponsored polls be in the main analysis or only in a robustness check?

- [ ] **P05: Pollster attributes table.**
  **When:** Fri Nov 13 – Sat Nov 14 (can run alongside P06).
  > Build `build/pollsters.py` and the cited `data/reference/pollster_methods.csv` for at least the 20 pollsters with the most 2026 statewide polls (spec §0): canonical name and aliases, mode(s) (live phone, IVR, online opt-in panel, probability panel, text-to-web, mixed), population, weighting variables (education, **recalled 2024 vote**, party ID), panel source, AAPOR Transparency Initiative membership, and a source URL + access date for every field. Use "unknown", never a guess. Normalise pollster names in the poll table to the canonical names.

  **Deliverables:**
  - `data/reference/pollster_methods.csv` (cited, with access dates)
  - The share of 2026 polls covered by coded pollsters
  - A list of fields left "unknown"

  **Checkpoint questions:** Should we email pollsters with unclear methods (outward-facing, so only with your OK)? Should mixed-mode pollsters be grouped by their main mode?

### Phase 2: Results (from Nov 13, refreshed weekly)

- [ ] **P06: Results ingest (provisional) + certification calendar.**
  **When:** First run Fri Nov 13 – Sat Nov 14. ⏳ Rerun every Monday (Nov 16, 23, 30, Dec 7) until P19.
  > Implement `ingest/results.py`: for every race in `races.csv`, take candidate votes from the state election office's unofficial results (Wikipedia results tables only as a cross-check), with `status`, `source_url`, `as_of`, and estimated % of the expected vote counted. Compute the two-party result margin. Compute the national House vote (for the generic ballot), with uncontested seats handled explicitly and documented. Build `data/reference/certification_calendar.csv` (state, statutory/expected certification date, source) and check whether any 2026 race goes to a runoff. Test that state totals match the official page totals.

  **Deliverables:**
  - `data/reference/results_certified.csv` (versioned rows; status = called/unofficial for now)
  - `data/reference/certification_calendar.csv`, plus the date the **last relevant state** is expected to certify (this sets P19's date)
  - A coverage table: races with polls + result, % counted, and races still too close or incomplete

  **Checkpoint questions:** Should races under ~98% counted be held out of the first look? How should uncontested House seats be treated in the national House vote?

### Phase 3: Historical baseline and model (Nov 14–20)

- [ ] **P07: Historical polls and results, 2014–2024.**
  **When:** Sat Nov 14 – Tue Nov 17.
  > Implement `ingest/historical_538.py` using whatever FiveThirtyEight data is still on GitHub (P01). Map it to the same schema as the 2026 poll table (race ids, D − R margins, LV preference, pollster canonical names), including results for 2014, 2016, 2018, 2020, 2022 and 2024 Senate/governor races (and presidential races, for context only). Note gaps in coverage per cycle and the dedupe/selection differences from our 2026 rules.

  **Deliverables:**
  - `data/processed/polls_hist.parquet`, `data/processed/results_hist.parquet`
  - Counts of polls and races per cycle × office
  - A short note in DATA.md on how 538's selection rules differ from ours

  **Checkpoint questions:** Should presidential races count in the "history" chart, or only midterm-style statewide races?

- [ ] **P08: Hierarchical bias model, built and fitted on history.**
  **When:** Mon Nov 16 – Fri Nov 20.
  > Add `cmdstanpy` (and `arviz`) and write `models/hier_bias.stan` + `models/fit.py` following spec §5 and Shirani-Mehr et al. (2018): poll margin ~ result margin + race-level bias (correlated across races within a cycle, with an election-wide component) + pollster house effect + time trend toward election day + sampling error (from n) + excess variance. Tests first: simulate fake polls with known parameters and show the model recovers them. Then fit each historical cycle (`models/history.py`) and produce chart 2 v1 (average signed error and total error by cycle).

  **Deliverables:**
  - Stan model + fitting code; parameter-recovery plot from simulated data
  - Per-cycle estimates: election-wide bias, race-bias SD, excess variance, with intervals
  - Chart 2 v1: average signed error by cycle, 2014–2024
  - Fit diagnostics (R-hat, divergences, ESS)

  **Checkpoint questions:** Do the historical estimates match published work (e.g. ~polls overstating Democrats in 2016/2020)? If not, what explains the gap?

- [ ] **P09: Reviewer outreach.**
  **When:** By Thu Nov 20 (can be done any time Nov 14–20).
  > Find 3–5 candidate survey methodologists who could review the final draft (AAPOR task-force authors, academic survey researchers, public poll analysts with methods expertise; no one employed by a pollster covered in the analysis). For each, give a public profile link and why they fit. Draft a short, plain email: what the project is, that it's non-partisan and open (code + data), what I'm asking (read a ~15-minute draft in the week of Dec 8, comments by Dec 14), and an offer to acknowledge them. Save drafts to `docs/reviewer_outreach.md`. Don't send anything.

  **Deliverables:**
  - `docs/reviewer_outreach.md` with candidates + one email draft per candidate

  **Checkpoint questions:** Which candidates should get the email, and from which address? (I'll send them myself.)

### Phase 4: First look (Nov 18–24)

- [ ] **P10: First-look analysis on provisional results.**
  **When:** Wed Nov 18 – Sat Nov 21 (after the Nov 16 results refresh).
  > Using provisional results (status called/unofficial, ≥98% counted): define the "final polling average" per race (a documented, simple rule, e.g. the latest poll per pollster in the last 21 days, weighted by √n) and compare it with the aggregators' published final averages from P02. Compute signed and absolute error by office, the share of races where polls overstated each party, and generic ballot vs the provisional national House vote. Produce the **hero chart v1** (dumbbell: final average vs result for every Senate and governor race, sorted by error) and a simple histogram of poll-level errors vs what sampling error alone would give. Label everything PRELIMINARY with the results `as_of` date.

  **Deliverables:**
  - Hero chart v1 (PNG + interactive) with alt text
  - A first-look stats table (mean signed error, mean absolute error, by office; generic ballot error)
  - Our average vs the aggregators' averages (sanity check)
  - Three candidate headline sentences

  **Checkpoint questions:** Which headline? Is the finding "polls were off in one direction" or "polls were about right"? (The spec says either is a story.)

- [ ] **P11: Publish the first look (~Mon Nov 24).**
  **When:** Sat Nov 21 – Mon Nov 24.
  > Set up `report/` as a Quarto website with GitHub Pages deploy via Actions. Write `report/first-look.qmd`: a short (≤800 words), finding-first post with the hero chart, the stats table, a "what we'll do next" section, and a prominent PRELIMINARY banner with the results date. Run the `data:validate-data` checklist, check reading grade (target ≤ 10), re-check source terms, then publish. Draft distribution posts (spec §9: a Bluesky/X thread, a Reddit post for r/fivethirtyeight-style and r/PoliticalDiscussion communities, a pitch to 2–3 election-analysis Substacks).

  **Deliverables:**
  - Live first-look URL
  - QA checklist results; reading-grade score
  - Distribution drafts in `docs/distribution_first_look.md`. **Nothing is posted without my sign-off.**

  **Checkpoint questions:** OK to publish? Which distribution drafts should go out, and when?

### Phase 5: Full analysis on near-final results (Nov 24 – Dec 8)

- [ ] **P12: Full 2026 model.**
  **When:** Tue Nov 24 – Tue Dec 1 (after the Nov 23 results refresh; light work over Thanksgiving, Nov 26).
  > Fit the hierarchical model to 2026 Senate + governor polls (House and generic ballot as a separate secondary fit). Report the election-wide bias, race-level bias and its correlation across states, house effects with intervals, and excess variance vs sampling error. Posterior predictive checks. Compare 2026 with each historical cycle (chart 2 final). Sensitivity: final-poll window (2/3/4 weeks), with and without partisan polls.

  **Deliverables:**
  - Variance decomposition table: "of the typical poll's error, X% is shared across all polls, Y% race-specific, Z% pollster, W% sampling"
  - House-effect dot plot (with the non-partisan wording rule)
  - Chart 2 final (2014–2026)
  - A sensitivity grid (does the headline survive each check?)

  **Checkpoint questions:** Is the shared-bias finding robust enough to headline? Is any house effect large enough to name, given the wording rules?

- [ ] **P13: Did newer methods do better?**
  **When:** Mon Nov 30 – Thu Dec 3.
  > Implement `models/methods.py`: compare errors by mode and by weighting on recalled 2024 vote, controlling for race and timing (within-race comparisons or race fixed effects in the hierarchical model, since pollsters choose different races). Report effect sizes with intervals and the number of pollsters behind each group; be explicit about how few pollsters drive each comparison. Chart 3.

  **Deliverables:**
  - Chart 3: error by method (dot plot with intervals)
  - A table of methods × number of pollsters × number of polls × estimated effect
  - One plain-English paragraph answering "did the new methods work?", with honest uncertainty

  **Checkpoint questions:** Is there enough data to say anything about text-to-web or probability panels, or should those be grouped?

- [ ] **P14: Herding.**
  **When:** Tue Dec 1 – Thu Dec 3.
  > Implement `models/herding.py`: for each race with enough final-two-week polls, compare the observed spread of poll margins with the spread expected from sample sizes alone (plus the model's excess variance from history). Use a simulation test and a by-pollster version (are a pollster's late polls closer to the running average than its early ones?). Correct for multiple comparisons. Chart 4.

  **Deliverables:**
  - Chart 4: observed vs expected dispersion by race
  - A pollster-level herding table (aggregate wording; no accusations)
  - The plain-English answer: "were late polls suspiciously close together?"

  **Checkpoint questions:** Is the herding wording fair to pollsters? Should the pollster-level table be published or kept in the appendix?

- [ ] **P15: Where did polls miss? (demographics).**
  **When:** Thu Dec 3 – Sat Dec 5.
  > Implement `ingest/acs.py` (ACS 5-year: % bachelor's+, % Hispanic, urbanisation/density, % white non-college for states and districts). Relate race-level bias from P12 to these variables (scatter + a simple regression on the race-level bias estimates, carrying their uncertainty). With ~35–45 statewide races, report this as descriptive. Chart 5.

  **Deliverables:**
  - `data/processed/acs_states.parquet`, `acs_districts.parquet`
  - Chart 5: error vs the strongest demographic variable(s)
  - A caveat paragraph on the small sample

  **Checkpoint questions:** Which one or two demographic variables should go in the article?

- [ ] **P16: Polls vs forecasters (chart 6).**
  **When:** Fri Dec 4 – Sat Dec 5.
  > Using P02's final forecasts, compare each forecaster's final projected margin and win probability with the polling average and the result: margin error, Brier score and log loss, with bootstrap intervals. Note how few races were close (limits what can be concluded). Chart 6. No prediction-market data (Project 34 is independent).

  **Deliverables:**
  - Chart 6: polls vs forecasters, margin error and Brier score
  - A table per forecaster with intervals

  **Checkpoint questions:** Include this in the main article or as a sidebar?

- [ ] **P17: Race explorer.**
  **When:** Sat Dec 5 – Tue Dec 8.
  > Build the interactive race explorer (spec §6) with Observable JS inside the Quarto site: pick a race and see every poll over time (sized by n, coloured by method, partisan polls marked), the polling average, the aggregators' final averages, and the result line, with a results-status label. Precompute compact JSON in `app/`. Make it mobile-first and accessible (keyboard navigation, contrast, text alternative).

  **Deliverables:**
  - Explorer embedded in a local preview
  - Screenshots at desktop and phone widths
  - The JSON build step wired into `make figures`

  **Checkpoint questions:** Which race should open by default, and which 4–5 should be featured?

- [ ] **P18: Full draft → reviewer.**
  **When:** Mon Dec 7 – Tue Dec 8. Send to the reviewer by Dec 8.
  > Write `report/index.qmd`: "How Wrong Were the Polls? Bias, Variance and Herding in the 2026 Midterms". Follow the plain-language rules: finding-first intro, hero chart early, then shared vs pollster error, history, methods, herding, where, generic ballot, forecasters, an embedded explorer, "what we don't claim", and a methods appendix for experts. Mark numbers that will change at certification. Deploy as an unlisted draft and produce a PDF for the reviewer.

  **Deliverables:**
  - Draft URL + PDF
  - Reading-grade score (target ≤ 10)
  - A list of the numbers that depend on not-yet-certified states

  **Checkpoint questions:** Send to the reviewer now? Which sections should be cut or moved to the appendix?

### Phase 6: Certification and final release (Dec 11–18)

- [ ] **P19: Swap in certified results.**
  **When:** ⏳ The day after the last relevant state certifies (expected ~Fri Dec 11 – Mon Dec 14; see P06's calendar).
  > Rerun `ingest/results.py` for certified results, add new versions with status `certified`, and diff them against the provisional rows (which races moved, by how much). Rerun everything from a clean clone with `make all`. Update every number and chart in the draft; flag any headline that changed.

  **Deliverables:**
  - A provisional → certified diff table
  - All charts and tables regenerated from certified data
  - A list of changed numbers in the draft

  **Checkpoint questions:** Did anything change enough to alter a headline? Are any states still uncertified? If so, publish with them marked, or wait?

- [ ] **P20: QA, reviewer feedback, publish final (~Thu Dec 18).**
  **When:** Tue Dec 15 – Fri Dec 18.
  > Incorporate reviewer comments (list each with how it was addressed). Run the `data:validate-data` checklist, reproduce from a clean clone, re-check every source's terms in DATA.md, and update the README (status, findings, reproduce). Publish to GitHub Pages, update the first-look post with a link to the final version, and tag a release (`v1.0`) with the processed data. Draft distribution posts (spec §9).

  **Deliverables:**
  - Live final URL and the `v1.0` release
  - `docs/review_response.md`
  - QA results
  - Distribution drafts in `docs/distribution_final.md`. **Nothing is posted without my sign-off.**

  **Checkpoint questions:** OK to publish? Which posts go out and when (avoid Dec 22 – Jan 2)?

### Phase 7: After publication (2027)

- [ ] **P21: MEDSL cross-check + stretch goals.**
  **When:** ⏳ When MEDSL publishes 2026 data (check monthly from January 2027); stretch goals any time after P20.
  > Cross-check our certified results against MEDSL and publish a dated correction note if anything differs. Then pick one stretch goal with me (spec §11): ballot-measure polling accuracy, a reusable "poll quality" score from the model, or a 2028 primaries rerun plan.

  **Deliverables:**
  - A MEDSL vs our results diff (and a correction note if needed)
  - The chosen stretch goal's plan or output

---

## Status

- 2026-11-09: Plan written. Pre-election snapshots were never captured (P34's B1 didn't run), so P02 rebuilds them from Wikipedia revision history and the Wayback Machine. Decisions: first look ~Nov 24 + final ~Dec 18; independent of Project 34; find a reviewer by Nov 20. Next: P01.
- 2026-11-09: P01 done (see DATA.md). Wikimedia needs a User-Agent with an `https://` contact URL plus the library name. The 2026 poll table must be released under CC BY-SA 4.0. User approved the forecaster list and the unclear-terms rule (see Decisions); Census key verified. Next: P02.
- 2026-11-09: P02 done (see DATA.md "P02 capture"). Nominees come from the election-eve infobox; that's how final-matchup tables are picked. P03 must handle replaced candidates (ME, SC Senate), independents as the D side (NE Senate), shared surnames (AK Senate) and 3-way races. User decided: keep late-added polls (flagged, field end ≤ Nov 2) and skip DDHQ/Economist probabilities. Next: P03.
- 2026-11-09: P03 done (see DATA.md "P03"). Generic-ballot polls come from a Wikipedia template, not the House page. races.csv carries no Split Ticket numbers (terms rule). 2026-11-10: user approved the non-standard-contest rules (see Decisions). Next: P04.
