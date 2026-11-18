# Most Reliable Players Under Pressure

SupeRR Selector S2 · Round 1 — a win-probability pressure model and Bayesian reliability ratings for T20 batters and bowlers (IPL + T20I, 2022–2026).

## Method in brief
- **Pressure per ball**: chase = √(Leverage Index × Demand); setting = Demand vs par. Top 25% of balls (knockouts ×1.25) = pressure balls.
- **Credits per ball**: run value, wicket value (in runs), win probability added — each measured against a context-expected baseline.
- **Ratings**: empirical-Bayes shrinkage (overall skill + shrunk pressure lift), five weighted components, Rating = 50 + 10z, 90% intervals from match-level bootstrap.

## Files
| File | Purpose |
|---|---|
| s1_prep_wp.py | Cleaning, win-probability models, leverage, demand, expected-runs models |
| s2_ratings.py | Ball credits, Bayesian estimates, composite rating, bootstrap |
| s3_charts.py | Figures and summary tables |
| s4_report.py | Methodology report PDF |
| s5_dashdata.py | Data files for the interactive dashboard |
| bat_leaderboard.csv / bowl_leaderboard.csv | Full leaderboards for all eligible players |

Run order: s1 → s2 → s3 → s4 → s5. Seeds fixed (match split 7, bootstrap 2027).
