"""Step 1: clean ball-by-ball data, build match state, train win-probability (WP) models,
compute per-ball Leverage Index (pressure) and Win Probability Added (WPA)."""
import sys, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss

D = sys.argv[1]
OUT = sys.argv[2]
b = pd.read_csv(f"{D}/ball_by_ball.csv", low_memory=False)
m = pd.read_csv(f"{D}/matches.csv")
c = pd.read_csv(f"{D}/competitions.csv")
pe = pd.read_csv(f"{D}/playing_eleven.csv")

# ---------------- match table ----------------
m = m.merge(c, on="comp_id", how="left")
m["match_date"] = pd.to_datetime(m["match_date"])
m["year"] = m.match_date.dt.year
m["is_ipl"] = m.comp_name.str.startswith("IPL")
noresult = m.result.str.contains("No Result|Abandon", case=False, na=True)
m = m[~noresult].copy()
tied_no_winner = m.win_team_id.isna()
m["win_team_id"] = m.win_team_id.fillna(-1)
m["knockout"] = (m.knock_out == 1) | m.stage.isin(["Final", "Qualifier", "Eliminator", "Semi Final"])

# opposition-strength tier for T20I (full members vs associates / A sides)
FULL = {"India", "Australia", "England", "South Africa", "New Zealand", "Pakistan", "Sri Lanka",
        "West Indies", "Bangladesh", "Afghanistan", "Ireland", "Zimbabwe"}
IPL_TEAMS = {"Chennai Super Kings", "Mumbai Indians", "Rajasthan Royals", "Punjab Kings",
             "Royal Challengers Bengaluru", "Delhi Capitals", "Kolkata Knight Riders",
             "Sunrisers Hyderabad", "Gujarat Titans", "Lucknow Super Giants"}
def tier(name):
    if name in IPL_TEAMS: return 1.0
    if name in FULL: return 1.0 if name not in ("Zimbabwe", "Ireland") else 0.85
    if name.endswith(" A"): return 0.7
    return 0.6  # associates
m["home_tier"] = m.home_team.map(tier)
m["away_tier"] = m.away_team.map(tier)

# ---------------- ball table ----------------
b = b[b.innings.isin([1, 2]) & b.match_id.isin(m.match_id)].copy()
b = b.sort_values(["match_id", "innings", "overid", "over_ball_num", "innings_ball_num"]).reset_index(drop=True)
b["extras_type"] = b.extras_type.fillna("")
b["is_wide"] = b.extras_type.eq("wide")
b["is_nb"] = b.extras_type.isin(["Overstep", "other"])
b["legal"] = ~(b.is_wide | b.is_nb)
b["total_runs"] = b.runs + b.extras1_runs + b.extras_2_runs
# runs charged to bowler: bat runs + wides + no-ball penalty (byes/leg-byes excluded)
b["bowler_runs"] = b.runs + np.where(b.is_wide, b.extras1_runs, 0) + np.where(b.is_nb, b.extras1_runs, 0)
BOWLER_W = {"Caught", "Bowled", "LBW", "Stump", "Hit Wicket"}
b["bowler_wkt"] = b.is_wicket & b.dismissal_type.isin(BOWLER_W)
b["team_wkt"] = b.is_wicket & ~b.dismissal_type.isin(["Retire Out"])
b["striker_out"] = b.team_wkt & (b.dismissed_player_id == b.striker_id)
b["faced"] = ~b.is_wide  # balls faced by striker

g = b.groupby(["match_id", "innings"])
b["runs_before"] = g.total_runs.cumsum() - b.total_runs
b["wkts_before"] = g.team_wkt.cumsum() - b.team_wkt
b["legal_before"] = g.legal.cumsum() - b.legal

mi = m.set_index("match_id")
inn1_tot = b[b.innings == 1].groupby("match_id").total_runs.sum()
b["max_balls"] = 120
r1 = b.match_id.map(mi.first_inn_revised_overs); r2 = b.match_id.map(mi.second_inn_revised_overs)
b.loc[(b.innings == 1) & r1.notna(), "max_balls"] = r1[(b.innings == 1) & r1.notna()]
b.loc[(b.innings == 2) & r2.notna(), "max_balls"] = r2[(b.innings == 2) & r2.notna()]
tgt = b.match_id.map(inn1_tot) + 1
rt = b.match_id.map(mi.revised_target)
b["target"] = np.where((b.innings == 2) & rt.notna(), rt, tgt)
b["balls_left"] = (b.max_balls - b.legal_before).clip(lower=1)
b["wkts_left"] = 10 - b.wkts_before
b["over_no"] = (b.legal_before // 6) + 1
b["phase"] = np.select([b.legal_before < 36, b.legal_before < 90], ["Powerplay", "Middle"], "Death")

# par score: mean completed 1st-innings total per competition-type & year (scoring environment)
b["year"] = b.match_id.map(mi.year); b["is_ipl"] = b.match_id.map(mi.is_ipl)
full1 = b[(b.innings == 1)].groupby("match_id").agg(tot=("total_runs", "sum"))
full1 = full1.join(mi[["year", "is_ipl", "first_inn_revised_overs"]])
full1 = full1[full1.first_inn_revised_overs.isna()]
par = full1.groupby(["is_ipl", "year"]).tot.mean().rename("par").reset_index()
b = b.merge(par, on=["is_ipl", "year"], how="left")
print("Par scores:\n", par)

b["bat_won"] = (b.batting_team_id == b.match_id.map(mi.win_team_id)).astype(float)
b.loc[b.match_id.map(mi.win_team_id).eq(-1).values, "bat_won"] = 0.5
# super-over decided ties: win_team recorded -> fine

def feats1(df, runs, wl, bl):
    crr = runs / np.maximum(df.max_balls - bl, 1) * 6
    proj = runs + crr / 6 * bl
    return np.column_stack([runs, wl, bl, df.max_balls, crr, df.par, proj - df.par * df.max_balls / 120,
                            df.is_ipl.astype(int)])
def feats2(df, runs, wl, bl):
    need = df.target - runs
    rrr = need / bl * 6
    return np.column_stack([need, wl, bl, rrr, df.par * df.max_balls / 120, df.target, df.is_ipl.astype(int)])

# ---------------- train WP models (match-level split for validation) ----------------
rng = np.random.RandomState(7)
mids = b.match_id.unique(); test_m = set(rng.choice(mids, int(len(mids) * 0.2), replace=False))
models = {}
for inn, ff in [(1, feats1), (2, feats2)]:
    d = b[(b.innings == inn) & (b.bat_won != 0.5)]
    X = ff(d, d.runs_before.values, d.wkts_left.values, d.balls_left.values); y = d.bat_won.values
    tr = ~d.match_id.isin(test_m).values
    mono = [1, 1, 0, 0, 1, 0, 1, 0] if inn == 1 else [-1, 1, 1, -1, 0, 0, 0]
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                         min_samples_leaf=200, monotonic_cst=mono, random_state=1)
    clf.fit(X[tr], y[tr])
    p = clf.predict_proba(X[~tr])[:, 1]
    print(f"WP model inn{inn}: test AUC={roc_auc_score(y[~tr], p):.3f} Brier={brier_score_loss(y[~tr], p):.3f} "
          f"LogLoss={log_loss(y[~tr], p):.3f} n_test_balls={(~tr).sum()}")
    # refit on all
    clf.fit(X, y); models[inn] = clf

# ---- smooth first-innings WP: projected final score -> chase win probability ----
from scipy.stats import norm
from scipy.optimize import minimize
i1 = b[b.innings == 1].copy()
fin = i1.groupby("match_id").total_runs.sum()
i1["rem"] = i1.match_id.map(fin) - i1.runs_before
def pfe(df, runs, wl, bl):
    crr = runs / np.maximum(df.max_balls.values - bl, 1) * 6
    return np.column_stack([wl, bl, df.par.values * df.max_balls.values / 120, crr, df.is_ipl.astype(int)])
proj_m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, min_samples_leaf=200,
                                       monotonic_cst=[1, 1, 1, 0, 0], random_state=1)
proj_m.fit(pfe(i1, i1.runs_before.values, i1.wkts_left.values, i1.balls_left.values), i1.rem)
i1["prem"] = proj_m.predict(pfe(i1, i1.runs_before.values, i1.wkts_left.values, i1.balls_left.values))
i1["res"] = i1.rem - i1.prem
sd_tab = i1.groupby(pd.cut(i1.balls_left, np.arange(0, 125, 6))).res.std()
bl_mid = np.array([iv.mid for iv in sd_tab.index]); sd_vals = sd_tab.values
coef_sd = np.polyfit(np.sqrt(bl_mid), sd_vals, 1)
print("projection residual sd ~", coef_sd)
def sd_of(bl): return np.maximum(np.polyval(coef_sd, np.sqrt(np.maximum(bl, 0))), 0) * (bl > 0)
# chase-win vs target margin (probit), first innings complete matches, decided results
mm = m.set_index("match_id")
first_bat = b[b.innings == 1].groupby("match_id").agg(tot=("total_runs", "sum"), bt=("batting_team_id", "first"),
                                                       par=("par", "first"), mb=("max_balls", "first"))
first_bat["win"] = (first_bat.bt == mm.win_team_id.reindex(first_bat.index)).astype(float)
first_bat = first_bat[mm.win_team_id.reindex(first_bat.index) != -1]
first_bat["d"] = first_bat.tot - first_bat.par * first_bat.mb / 120
def nll(p):
    pr = norm.cdf((first_bat.d - p[0]) / abs(p[1])).clip(1e-6, 1 - 1e-6)
    return -(first_bat.win * np.log(pr) + (1 - first_bat.win) * np.log(1 - pr)).sum()
P0 = minimize(nll, [0, 30], method="Nelder-Mead").x
print("Bat-first win = Phi((total - par - %.1f)/%.1f)" % (P0[0], abs(P0[1])))
def wp1(df, runs, wl, bl):
    proj = runs + np.where(bl > 0, proj_m.predict(pfe(df, runs, wl, np.maximum(bl, 0))), 0) * (wl > 0)
    d = proj - df.par.values * df.max_balls.values / 120
    return norm.cdf((d - P0[0]) / np.sqrt(P0[1] ** 2 + sd_of(np.where(wl > 0, bl, 0)) ** 2))


def wp(df, runs, wkts_lost, legal_after):
    """WP of batting team for a hypothetical post-ball state (vectorised, with terminal states)."""
    runs = np.asarray(runs, float); wl = 10 - np.asarray(wkts_lost); bl = df.max_balls.values - legal_after
    out = np.zeros(len(df)); inn = df.innings.values
    # innings 2
    i2 = inn == 2
    won = i2 & (runs >= df.target.values)
    lost = i2 & ~won & ((wl <= 0) | (bl <= 0))
    tie = lost & (runs == df.target.values - 1)
    live2 = i2 & ~won & ~lost
    out[won] = 1; out[lost] = 0; out[tie] = 0.5
    if live2.any():
        s = df[live2]
        out[live2] = models[2].predict_proba(feats2(s, runs[live2], wl[live2], np.maximum(bl[live2], 1)))[:, 1]
    # innings 1
    i1 = inn == 1
    end1 = i1 & ((wl <= 0) | (bl <= 0))
    live1 = i1 & ~end1
    if i1.any():
        out[i1] = wp1(df[i1], runs[i1], wl[i1], bl[i1])
    return out

# WP before each ball
b["wp_before"] = wp(b, b.runs_before, b.wkts_before, b.legal_before)
# WP after (actual)
b["wp_after"] = wp(b, b.runs_before + b.total_runs, b.wkts_before + b.team_wkt, b.legal_before + b.legal)
b["dwp"] = b.wp_after - b.wp_before   # batting-team perspective

# ---------------- Leverage: expected |ΔWP| over plausible outcomes of the ball ----------------
outc = [("dot", 0, 0, 1), ("one", 1, 0, 1), ("two", 2, 0, 1), ("four", 4, 0, 1), ("six", 6, 0, 1),
        ("wkt", 0, 1, 1), ("wide", 1, 0, 0)]
leg = b[["phase"]].copy()
cat = np.select([b.team_wkt, ~b.legal & b.is_wide, b.runs >= 6, b.runs >= 4, b.runs >= 2, b.runs == 1],
                ["wkt", "wide", "six", "four", "two", "one"], "dot")
probs = pd.crosstab(b.phase, cat, normalize="index")
print("Outcome probabilities by phase:\n", probs.round(3))
lev = np.zeros(len(b))
for name, r, w, l in outc:
    pa = wp(b, b.runs_before + r, b.wkts_before + w, b.legal_before + l)
    lev += b.phase.map(probs[name]).values * np.abs(pa - b.wp_before.values)
b["leverage"] = lev
b["LI"] = b.leverage / b.leverage.mean()
b["knockout"] = b.match_id.map(mi.knockout).values
# ---- Situational Demand (DLS-style demand / resources) ----
par_rr = b.par.values / 20.0
Xres = np.column_stack([b.wkts_left, b.balls_left, b.par * b.max_balls / 120, par_rr, b.is_ipl.astype(int)])
b["xrem"] = np.maximum(proj_m.predict(Xres), 1)
Xres2 = Xres.copy(); Xres2[:, 0] = np.maximum(Xres2[:, 0] - 1, 0)
b["wkt_cost"] = np.clip(b.xrem - np.where(b.wkts_left > 1, proj_m.predict(Xres2), 0), 0, None)
sd2 = (b.target - b.runs_before) / b.xrem
sd1 = (b.par * b.max_balls / 120) / (b.runs_before + b.xrem)
b["SD"] = np.clip(np.where(b.innings == 2, sd2, sd1), 0.25, 3.0)
b["SD"] = b.SD / b.SD.mean()
LIc = b.LI.clip(upper=b.LI.quantile(0.995))
b["LIc"] = LIc
# Chase: stakes (leverage) x demand ; Setting: demand (projected total vs par) only
b["PI_raw"] = np.where(b.innings == 2, np.sqrt(LIc * b.SD), b.SD)
b["PI_pct"] = b.groupby("innings").PI_raw.rank(pct=True)
b["PI"] = b.PI_pct * np.where(b.knockout, 1.25, 1.0)
b["press"] = b.PI >= 0.75

# ---------------- expected-runs / expected-dismissal models (context baseline) ----------------
def ctx(df):
    rrr = np.where(df.innings == 2, (df.target - df.runs_before) / df.balls_left * 6, 0)
    crr = df.runs_before / np.maximum(df.legal_before, 1) * 6
    return np.column_stack([df.innings, df.legal_before, df.wkts_before, df.max_balls, np.clip(rrr, 0, 36), crr,
                            df.par, df.is_ipl.astype(int), (df.pace_or_spin == "Pace").astype(int)])
f = b[b.faced]
Xc = ctx(f)
xr = HistGradientBoostingRegressor(max_iter=250, learning_rate=0.05, min_samples_leaf=300, random_state=1).fit(Xc, f.runs)
xo = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.05, min_samples_leaf=300, random_state=1).fit(Xc, f.striker_out)
b["xruns_bat"] = np.nan; b["xout"] = np.nan
b.loc[b.faced, "xruns_bat"] = xr.predict(Xc); b.loc[b.faced, "xout"] = xo.predict_proba(Xc)[:, 1]
# bowler expectation on all deliveries
Xa = ctx(b)
xbr = HistGradientBoostingRegressor(max_iter=250, learning_rate=0.05, min_samples_leaf=300, random_state=1).fit(Xa, b.bowler_runs)
xbw = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.05, min_samples_leaf=300, random_state=1).fit(Xa, b.bowler_wkt)
b["xruns_bowl"] = xbr.predict(Xa); b["xwkt_bowl"] = xbw.predict_proba(Xa)[:, 1]

# context weights: recency + opposition strength
REC = {2022: 0.45, 2023: 0.6, 2024: 0.75, 2025: 0.9, 2026: 1.0}
b["w_rec"] = b.year.map(REC)
ht = b.match_id.map(mi.home_team_id); at_ = b.match_id.map(mi.away_team_id)
htier = b.match_id.map(mi.home_tier); atier = b.match_id.map(mi.away_tier)
b["bowl_opp_tier"] = np.where(b.bowling_team_id == ht, htier, atier)   # opponent faced by batter
b["bat_opp_tier"] = np.where(b.batting_team_id == ht, htier, atier)    # opponent faced by bowler
b["comp"] = np.where(b.is_ipl, "IPL", "T20I/Other")
b["match_date"] = b.match_id.map(mi.match_date)
b["stage"] = b.match_id.map(mi.stage)
b.to_pickle(f"{OUT}/balls.pkl")
m.to_pickle(f"{OUT}/matches.pkl")
print(b[["LI", "PI", "dwp", "wp_before"]].describe())
