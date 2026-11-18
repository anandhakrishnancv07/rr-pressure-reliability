"""Step 2: player pressure ratings (batters & bowlers).
Hierarchical empirical-Bayes estimates of pressure performance + clutch lift + consistency + impact,
with global match-level bootstrap for uncertainty."""
import sys, json, numpy as np, pandas as pd
OUT = sys.argv[1]
REPS = int(sys.argv[2]) if len(sys.argv) > 2 else 300
import os
b = pd.read_pickle(f"{OUT}/balls.pkl")
TAG = os.environ.get("TAG", "")
if os.environ.get("PRESS_Q"): b["press"] = b.PI >= float(os.environ["PRESS_Q"])
if os.environ.get("NOREC"): b["w_rec"] = 1.0
if os.environ.get("NOOPP"): b["bowl_opp_tier"] = 1.0; b["bat_opp_tier"] = 1.0
ACTIVE_FROM = pd.Timestamp("2026-01-01")
MIN_PRESS, MIN_INN = 120, 10
WEIGHTS = {"run_value": 0.30, "wicket_value": 0.20, "consistency": 0.20, "lift": 0.15, "impact": 0.15}
if os.environ.get("WSET") == "equal": WEIGHTS = {k: 0.2 for k in WEIGHTS}
if os.environ.get("WSET") == "clutch": WEIGHTS = {"run_value": 0.2, "wicket_value": 0.15, "consistency": 0.2, "lift": 0.25, "impact": 0.2}

# ---------------- per-ball credits ----------------
bat = b[b.faced].copy()
bat["pid"] = bat.striker_id; bat["name"] = bat.striker_name
bat["w"] = bat.w_rec * bat.bowl_opp_tier
is_bye = bat.extras_type.isin(["byes", "legbyes"])
bat["v_wpa"] = np.where(is_bye & ~bat.striker_out, 0, bat.dwp) * 100        # WP percentage points
bat["v_run"] = bat.runs - bat.xruns_bat                                       # runs above expected
bat["v_wkt"] = (bat.xout - bat.striker_out.astype(float)) * bat.wkt_cost      # runs saved by not getting out
bat["v_nrv"] = bat.v_run + bat.v_wkt

bw = b.copy()
bw["pid"] = bw.bowler_id; bw["name"] = bw.bowler_name
bw["w"] = bw.w_rec * bw.bat_opp_tier
runout = bw.team_wkt & ~bw.bowler_wkt
bw["v_wpa"] = np.where(runout, 0, -bw.dwp) * 100
bw["v_run"] = bw.xruns_bowl - bw.bowler_runs                                  # runs saved vs expected
bw["v_wkt"] = (bw.bowler_wkt.astype(float) - bw.xwkt_bowl) * bw.wkt_cost      # wicket value above expected
bw["v_nrv"] = bw.v_run + bw.v_wkt
VALS = ["v_wpa", "v_run", "v_wkt", "v_nrv"]

def player_match_table(df):
    d = df.assign(**{f"s_{v}": df.w * df[v] for v in VALS})
    t = d.groupby(["pid", "match_id", "press"]).agg(n=("w", "size"), wn=("w", "sum"),
            **{f"s_{v}": (f"s_{v}", "sum") for v in VALS}, raw_nrv=("v_nrv", "sum")).reset_index()
    return t

def hyper(df):
    """League means and between-player true-score variances (method of moments)."""
    H = {}
    for v in VALS:
        for lab, mask in [("p", df.press), ("n", ~df.press), ("a", df.index == df.index)]:
            d = df[mask]
            g = d.groupby("pid")[v].agg(["mean", "size"]); g = g[g["size"] >= 100]
            s2 = d[v].var(); tau2 = g["mean"].var() - (s2 / g["size"]).mean()
            H[(v, lab)] = dict(mean=float(np.average(d[v], weights=d.w)), s2=float(s2), tau2=float(tau2),
                               k=float(s2 / tau2) if tau2 > 0 else float("inf"))
        # clutch deviation (pressure minus non-pressure) true variance
        P = df[df.press].groupby("pid")[v].agg(["mean", "size"]); N = df[~df.press].groupby("pid")[v].agg(["mean", "size"])
        j = P.join(N, lsuffix="_p", rsuffix="_n").dropna(); j = j[(j.size_p >= 100) & (j.size_n >= 100)]
        samp = (H[(v, "p")]["s2"] / j.size_p + H[(v, "n")]["s2"] / j.size_n).mean()
        H[(v, "dev")] = dict(tau2=float((j.mean_p - j.mean_n).var() - samp), players=int(len(j)))
    # minimum-signal floor: when a true-score variance is not identifiable, assume k = 3000 balls
    for v in VALS:
        for lab in ["a", "p", "n"]:
            h = H[(v, lab)]; best = max(H[(v, x)]["tau2"] * h["s2"] / H[(v, x)]["s2"] for x in ["a", "p", "n"])
            h["tau2_raw"] = h["tau2"]; h["tau2"] = max(h["tau2"], best, h["s2"] / 3000); h["k"] = h["s2"] / h["tau2"]
    # WPA: pressure-only true variance is not identifiable (<=0); borrow all-ball signal-to-noise ratio
    a = H[("v_wpa", "a")]
    H[("v_wpa", "p")]["tau2_used"] = max(H[("v_wpa", "p")]["tau2"], a["tau2"] / a["s2"] * H[("v_wpa", "p")]["s2"])
    return H

def eb(raw, n, mean, s2, tau2):
    if tau2 <= 0: return pd.Series(mean, index=raw.index), pd.Series(0.0, index=raw.index)
    rel = tau2 / (tau2 + s2 / np.maximum(n, 1e-9))
    return mean + rel * (raw - mean), rel

def compute(t, H, mult=None, pool=None, m_prior=10.0):
    """Ratings from a player-match table; mult = bootstrap match multiplicities."""
    if mult is not None:
        c = t.match_id.map(mult).fillna(0).values
        t = t.assign(n=t.n * c, wn=t.wn * c, raw_nrv=t.raw_nrv, c=c, **{f"s_{v}": t[f"s_{v}"] * c for v in VALS})
    else:
        t = t.assign(c=1.0)
    P = t[t.press].groupby("pid")[["n", "wn"] + [f"s_{v}" for v in VALS]].sum()
    N = t[~t.press].groupby("pid")[["n", "wn"] + [f"s_{v}" for v in VALS]].sum()
    A = t.groupby("pid")[["n", "wn"] + [f"s_{v}" for v in VALS]].sum()
    R = pd.DataFrame(index=A.index)
    R["press_balls"] = P.n.reindex(R.index).fillna(0); R["norm_balls"] = N.n.reindex(R.index).fillna(0)
    est = {}
    for v in ["v_run", "v_wkt", "v_nrv"]:
        # baseline skill from ALL balls, then pressure = baseline + shrunk clutch deviation
        rawA = A[f"s_{v}"] / A.wn
        mu, _ = eb(rawA, A.wn, H[(v, "a")]["mean"], H[(v, "a")]["s2"], H[(v, "a")]["tau2"])
        rawP = (P[f"s_{v}"] / P.wn).reindex(R.index); rawN = (N[f"s_{v}"] / N.wn).reindex(R.index)
        nP = P.wn.reindex(R.index).fillna(0); nN = N.wn.reindex(R.index).fillna(0)
        dev = (rawP - rawN).fillna(0)
        samp = H[(v, "p")]["s2"] / np.maximum(nP, 1e-9) + H[(v, "n")]["s2"] / np.maximum(nN, 1e-9)
        tau = H[(v, "dev")]["tau2"]
        dshr = dev * (tau / (tau + samp)) if tau > 0 else dev * 0
        league_off = H[(v, "p")]["mean"] - H[(v, "a")]["mean"]
        est[v] = 100 * (mu + league_off + dshr)          # per 100 pressure balls
        R[f"lift_{v}"] = 100 * dshr
        R[f"raw_p_{v}"] = 100 * rawP; R[f"raw_n_{v}"] = 100 * rawN
    rawW = (P.s_v_wpa / P.wn).reindex(R.index)
    hw = H[("v_wpa", "p")]
    R["impact"], _ = eb(rawW.fillna(hw["mean"]), P.wn.reindex(R.index).fillna(0), hw["mean"], hw["s2"], hw["tau2_used"])
    R["impact"] = 100 * (R["impact"] - hw["mean"])   # WP points above league-average pressure performance
    R["raw_p_v_wpa"] = 100 * rawW
    R["run_value"] = est["v_run"]; R["wicket_value"] = est["v_wkt"]; R["pressure_nrv"] = est["v_nrv"]
    R["lift"] = R.lift_v_nrv if H[("v_nrv", "dev")]["tau2"] > 0 else R.lift_v_run
    # consistency over pressure innings / spells (>=5 pressure balls)
    inn = t[t.press & (t.n / t.c.replace(0, 1) >= 5) & (t.c > 0)]
    succ = inn.assign(s=(inn.raw_nrv >= 0) * inn.c).groupby("pid").agg(s=("s", "sum"), m=("c", "sum"))
    R["p_inns"] = succ.m.reindex(R.index).fillna(0); R["succ"] = succ.s.reindex(R.index).fillna(0)
    if pool is None: pool = R.succ.sum() / R.p_inns.sum()
    R["consistency"] = 100 * (R.succ + m_prior * pool) / (R.p_inns + m_prior)
    return R, pool

def finalize(R, meta_df, role):
    last = meta_df.groupby("pid").match_date.max()
    R["name"] = meta_df.groupby("pid").name.agg(lambda s: s.mode().iat[0])
    R["last_match"] = last
    ipl = meta_df[meta_df.is_ipl].sort_values("match_date")
    tcol = "batting_team_id" if role == "bat" else "bowling_team_id"
    R["last_ipl_team_id"] = ipl.groupby("pid")[tcol].last()
    R["last_ipl_year"] = ipl.groupby("pid").year.last()
    R["eligible"] = (R.press_balls >= MIN_PRESS) & (R.p_inns >= MIN_INN) & (R.last_match >= ACTIVE_FROM)
    return R

def score(R, ref):
    comp = 0
    for c, w in WEIGHTS.items():
        comp = comp + w * (R[c] - ref[c][0]) / ref[c][1]
    return 50 + 10 * (comp - ref["_c"][0]) / ref["_c"][1]

results = {}
for role, df in [("bat", bat), ("bowl", bw)]:
    H = hyper(df)
    t = player_match_table(df)
    R, pool = compute(t, H)
    R = finalize(R, df, role)
    # Beta-binomial prior strength for consistency from method of moments on eligible players
    E0 = R[R.eligible]; pr0 = E0.succ / E0.p_inns
    tau2c = max(pr0.var() - (pr0 * (1 - pr0) / E0.p_inns).mean(), 1e-4)
    m_prior = float(pool * (1 - pool) / tau2c - 1)
    R, pool = compute(t, H, m_prior=m_prior)
    R = finalize(R, df, role)
    E = R[R.eligible]
    # scale each component by its TRUE-talent SD (not the SD of estimates), so noisy metrics carry less weight
    lift_v = "v_nrv" if H[("v_nrv", "dev")]["tau2"] > 0 else "v_run"
    tau_cons = np.sqrt(tau2c) * 100
    tau = {"run_value": 100 * np.sqrt(H[("v_run", "p")]["tau2"]), "wicket_value": 100 * np.sqrt(H[("v_wkt", "p")]["tau2"]),
           "lift": 100 * np.sqrt(max(H[(lift_v, "dev")]["tau2"], 1e-6)), "impact": 100 * np.sqrt(H[("v_wpa", "p")]["tau2_used"]),
           "consistency": tau_cons}
    ref = {c: (E[c].mean(), tau[c]) for c in WEIGHTS}
    comp = sum(w * (E[c] - ref[c][0]) / ref[c][1] for c, w in WEIGHTS.items())
    ref["_c"] = (comp.mean(), comp.std())
    R["rating"] = score(R, ref)
    for c in WEIGHTS:
        R[f"z_{c}"] = (R[c] - ref[c][0]) / ref[c][1]
    # ---- bootstrap over matches (global resample) ----
    rng = np.random.default_rng(2027)
    mids = t.match_id.unique()
    elig = R[R.eligible].index
    ratings = np.zeros((REPS, len(elig)))
    for i in range(REPS):
        cnt = pd.Series(rng.choice(mids, len(mids), replace=True)).value_counts()
        Rb, _ = compute(t, H, mult=cnt, pool=pool, m_prior=m_prior)
        ratings[i] = score(Rb.reindex(elig), ref).fillna(R.loc[elig, "rating"].min()).values
    ranks = (-ratings).argsort(axis=1).argsort(axis=1) + 1
    R.loc[elig, "rating_lo"] = np.percentile(ratings, 5, axis=0)
    R.loc[elig, "rating_hi"] = np.percentile(ratings, 95, axis=0)
    R.loc[elig, "p_top10"] = (ranks <= 10).mean(axis=0)
    R.loc[elig, "p_top20"] = (ranks <= 20).mean(axis=0)
    R.loc[elig, "median_rank"] = np.median(ranks, axis=0)
    # ---- descriptive raw stats ----
    if role == "bat":
        raw = df.groupby(["pid", "press"]).agg(runs=("runs", "sum"), balls=("runs", "size"), outs=("striker_out", "sum"),
                                               xr=("xruns_bat", "sum"), dots=("runs", lambda s: (s == 0).sum()),
                                               b4=("is_four", "sum"), b6=("is_six", "sum")).unstack()
    else:
        raw = df.groupby(["pid", "press"]).agg(runs=("bowler_runs", "sum"), balls=("legal", "sum"), outs=("bowler_wkt", "sum"),
                                               xr=("xruns_bowl", "sum"), dots=("total_runs", lambda s: (s == 0).sum()),
                                               b4=("is_four", "sum"), b6=("is_six", "sum")).unstack()
    for s, lab in [(True, "p"), (False, "np")]:
        for k in ["runs", "balls", "outs", "xr", "dots", "b4", "b6"]:
            R[f"{k}_{lab}"] = raw[k][s].reindex(R.index)
    # per-competition pressure split
    sp = df[df.press].groupby(["pid", "comp"]).agg(n=("v_nrv", "size"), nrv=("v_nrv", "mean"), wpa=("v_wpa", "mean")).unstack()
    for comp_ in ["IPL", "T20I/Other"]:
        R[f"n_{comp_}"] = sp["n"][comp_].reindex(R.index) if comp_ in sp["n"] else np.nan
        R[f"nrv100_{comp_}"] = 100 * sp["nrv"][comp_].reindex(R.index) if comp_ in sp["nrv"] else np.nan
    # temporal stability check of pressure NRV (raw) and of the composite
    def window_rating(mask):
        Rw, _ = compute(player_match_table(df[mask]), H, pool=pool, m_prior=m_prior)
        return Rw
    Re = window_rating(df.year <= 2024); Rl = window_rating(df.year >= 2025)
    jj = Re[["pressure_nrv", "press_balls", "consistency"]].join(Rl[["pressure_nrv", "press_balls", "consistency"]],
                                                                 lsuffix="_e", rsuffix="_l").dropna()
    jj = jj[(jj.press_balls_e >= 80) & (jj.press_balls_l >= 80)]
    rawj = (df[df.press & (df.year <= 2024)].groupby("pid").v_nrv.agg(["mean", "size"])
            .join(df[df.press & (df.year >= 2025)].groupby("pid").v_nrv.agg(["mean", "size"]), lsuffix="_e", rsuffix="_l").dropna())
    rawj = rawj[(rawj.size_e >= 80) & (rawj.size_l >= 80)]
    R = R.sort_values("rating", ascending=False)
    R["rank"] = np.nan; R.loc[R.eligible, "rank"] = np.arange(1, R.eligible.sum() + 1)
    R.to_pickle(f"{OUT}/{role}_ratings{TAG}.pkl")
    results[role] = dict(
        hyper={f"{k[0]}|{k[1]}": v for k, v in H.items()},
        temporal_r_eb=float(np.corrcoef(jj.pressure_nrv_e, jj.pressure_nrv_l)[0, 1]), temporal_n=int(len(jj)),
        temporal_r_raw=float(np.corrcoef(rawj.mean_e, rawj.mean_l)[0, 1]), temporal_n_raw=int(len(rawj)),
        eligible=int(R.eligible.sum()), total=int(len(R)), pool_success=float(pool), weights=WEIGHTS,
        true_sd=tau, lift_metric=lift_v, consistency_prior_innings=m_prior)
    print(role, json.dumps({k: v for k, v in results[role].items() if k != "hyper"}, default=float))
    cols = ["name", "rating", "rating_lo", "rating_hi", "p_top10", "median_rank", "press_balls", "p_inns",
            "run_value", "wicket_value", "consistency", "lift", "impact", "runs_p", "balls_p", "outs_p"]
    print(R[R.eligible][cols].head(30).round(2).to_string())
json.dump(results, open(f"{OUT}/model_meta{TAG}.json", "w"), indent=1, default=float)
