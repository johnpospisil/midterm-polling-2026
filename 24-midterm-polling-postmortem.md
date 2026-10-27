# Project 24: 2026 Midterm Polling Post-Mortem

**Backlog ID:** PO-1 · **Difficulty:** Medium · **Data access:** Open (check aggregator terms) · **Estimated time:** 6–7 weeks · **Time-sensitive: start right after the Nov 3, 2026 election**

**Working title:** *How Wrong Were the Polls? Bias, Variance and Herding in the 2026 Midterms*

**One-sentence pitch:** Collect every public 2026 Senate, governor and House poll, compare them with certified results, and decompose polling error into bias shared across polls, pollster-specific bias and excess variance, testing whether newer methods (online panels, text-to-web, weighting by recalled past vote) did better.

---

## 0. Day-one access check
- [ ] Find poll sources for 2026 and check their terms: Wikipedia poll tables (CC BY-SA), public aggregators' downloadable CSVs (check each), pollster releases (primary sources). **FiveThirtyEight's archive stopped when the site shut down in 2025; check which historical CSVs are still on GitHub for 2016–2024 comparisons.**
- [ ] Find a results source: state election offices (certified), plus the MIT Election Data + Science Lab (MEDSL) once it publishes 2026 data.
- [ ] Build a pollster attributes table (mode, population, weighting) for 20 pollsters from their methodology statements.

## 1. The question

**Primary:** What was the average signed error of 2026 polls (poll margin minus result margin) in Senate and governor races, and how much of it is shared across all polls (systematic bias) vs pollster-specific?

**Secondary:**
- **Methods:** did polls weighted on recalled 2024 vote, or using particular modes (live phone, IVR, online panel, text-to-web), have smaller errors?
- **Herding:** in the final weeks, were polls less dispersed than sampling error alone would produce?
- **Where:** were errors larger in some kinds of states or districts (e.g. by education level, urbanisation or Hispanic share)?
- **Generic ballot:** how accurate was the national generic congressional ballot vs the actual national House vote?
- **History:** how does 2026 compare with 2014–2024 errors?

**A finding that would be wrong if:** average signed error is near zero and dispersion matches sampling error (polls were fine), in which case the story becomes "the polls were right, here's why".

## 2. Why now
- The midterms are on November 3, 2026, so results arrive in the following weeks. Being first with a careful post-mortem (mid-December to January, after certification) gets attention.
- After misses in 2016 and 2020 and a closer performance in 2024, pollsters changed methods (especially weighting on recalled vote). 2026 is the first midterm test of those changes.
- Prior work: Shirani-Mehr, Rothschild, Goel & Gelman, *Disentangling Bias and Variance in Election Polls* (JASA, 2018); AAPOR task-force reports on 2016 and 2020 polling.

## 3. Data sources

| Source | What it gives you | Grain | Where |
|---|---|---|---|
| **Public polls 2026** | Pollster, sponsor, dates, sample size, population (LV/RV/A), mode, toplines | poll × race | Wikipedia poll tables (CC BY-SA), aggregators (check terms), pollster releases |
| **Historical polls 2014–2024** | Same fields for past cycles | poll × race | FiveThirtyEight archive on GitHub (check availability) |
| **Certified results** | Votes by candidate, by state and district | race | State election offices; MEDSL (open) |
| **Pollster methodology** | Mode, weighting variables (recalled vote, education), panel source | pollster | Methodology statements; AAPOR Transparency Initiative members |
| **State and district demographics** | Education, race/ethnicity, urbanisation | state / district | Census ACS |
| **Forecasts and markets** | Final forecasts and market prices (for comparison) | race | Public forecasters; ties to Project 34 |

## 4. Building the dataset

1. **Poll table:** one row per poll × race, two-party margin, field dates, n, population, mode, pollster; deduplicate polls reported in multiple places; prefer the LV version when several are published.
2. **Pollster table:** methods and AAPOR membership.
3. **Results:** certified two-party margins, entered with source and date. Track uncertified vs certified versions.
4. **Error:** signed error = poll margin − result margin (from the Democratic or Republican perspective; pick one and be consistent).
5. **Checks:** totals vs official results; double-entry for 10% of polls; partisan-sponsored polls flagged.

## 5. Method

### Bias–variance decomposition
- Bayesian hierarchical model (Stan or PyMC): poll margin ~ true margin + race-level bias + pollster house effect + time trend + sampling error; estimate race-level bias, its correlation across states, and excess variance.

### Method comparisons
- Error by mode and weighting approach, controlling for race and timing (pollsters choose different races, so control carefully).

### Herding
- Compare the observed variance of final-two-week polls with the variance expected from sample sizes alone; test by pollster.

### History
- Same model on 2014–2024 for comparison.

### What you won't claim
That a pollster is "biased" in a partisan sense. A house effect is a statistical tendency that can come from methods.

## 6. Charts

| # | Chart | Purpose |
|---|---|---|
| **Hero** | **Final polling average vs result for every Senate and governor race** (dumbbell chart, sorted by error) | The headline |
| 2 | Average signed error by cycle, 2014–2026 | Is it getting better? |
| 3 | Error by pollster method (dot plot with intervals) | Did the new methods work? |
| 4 | Herding: observed vs expected dispersion in the final weeks | Shareable stats insight |
| 5 | Error vs state demographics (scatter) | Where polls miss |
| 6 | Polls vs forecasts vs prediction markets | Bridge to Project 34 |

**Interactive:** pick a race and see every poll over time vs the result.

## 7. Repo skeleton

```
midterm-polling-2026/
  README.md, DATA.md, Makefile, pyproject.toml, uv.lock
  src/mp/
    ingest/wikipedia_polls.py, aggregators.py, historical_538.py, results.py, acs.py
    build/polls.py, pollsters.py, margins.py
    models/hier_bias.stan, fit.py, methods.py, herding.py, history.py
    viz/theme.py, figures.py
  data/reference/pollster_methods.csv (cited), results_certified.csv (cited)
  tests/          # dedupe rules, margin sign convention, results vs official totals
  report/index.qmd
  app/
```

## 8. Milestones

| Week | Deliverable |
|---|---|
| Before Nov 3 | Poll scraping pipeline; pollster table; historical data model fitted |
| 1 (Nov 4–10) | Preliminary results; quick descriptive post ("first look"), clearly labelled preliminary |
| 2–3 | Certified results as they arrive; full model |
| 4 | Method and herding analyses |
| 5 | Article + race explorer |
| 6–7 | Review by a survey methodologist; publish final version |

## 9. Distribution
- Polling and elections community (AAPOR members, election-analysis Substacks, r/fivethirtyeight-type subreddits, r/PoliticalDiscussion), data journalists.
- Keep the tone strictly non-partisan; that's what makes it credible.

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Results certification takes weeks (some states are slow) | Preliminary then final versions, clearly labelled |
| Poll data terms | Use primary sources and CC-licensed tables; cite everything |
| Few polls in House races | Focus on statewide races; House as secondary |
| Perceived partisanship | Same rules for both parties; publish code and data |

## 11. Stretch goals
- Ballot measures polling accuracy.
- A "poll quality" score from the model, updated each cycle.
- Combine with Project 34 into one "who called it best" article.
