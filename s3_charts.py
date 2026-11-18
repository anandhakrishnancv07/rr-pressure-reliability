"""Step 3: charts + summary tables for the report and dashboard."""
import sys, json, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
OUT = sys.argv[1]; FIG = sys.argv[2]
b = pd.read_pickle(f"{OUT}/balls.pkl")
meta = json.load(open(f"{OUT}/model_meta.json"))
BAT = pd.read_pickle(f"{OUT}/bat_ratings.pkl"); BOWL = pd.read_pickle(f"{OUT}/bowl_ratings.pkl")
mp = pd.read_csv(f"{sys.argv[3]}/competition_team_player_mapping.csv")
TEAM = {1: "CSK", 2: "MI", 3: "RR", 4: "PBKS", 5: "RCB", 7: "DC", 8: "KKR", 242: "SRH", 3508: "GT", 3509: "LSG"}

C1, C2, C3, C4, C5 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
INK, INK2, MUTE, GRID, SURF = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTE, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
                     "figure.facecolor": "white", "axes.facecolor": "white", "axes.titleweight": "bold",
                     "axes.titlesize": 10.5, "axes.titlecolor": INK, "axes.titlelocation": "left"})
def save(fig, name):
    fig.savefig(f"{FIG}/{name}.png", dpi=200, bbox_inches="tight"); plt.close(fig)

S = {}  # summary for report/dashboard

# ---------- 1. Pressure validation: league numbers pressure vs normal ----------
f = b[b.faced]
def lg(d, bw_):
    return dict(SR=d.runs.sum() / len(d) * 100, dot=(d.runs == 0).mean() * 100,
                bnd=(d.is_four | d.is_six).mean() * 100, out=d.striker_out.mean() * 100,
                econ=bw_.bowler_runs.sum() / bw_.legal.sum() * 6, wpa_swing=d.dwp.abs().mean() * 100)
val = {k: lg(f[f.press == p], b[b.press == p]) for k, p in [("pressure", True), ("normal", False)]}
val["share_pressure"] = float(b.press.mean() * 100)
S["validation"] = val
fig, axs = plt.subplots(1, 4, figsize=(9.2, 2.5))
for ax, (k, lab, fmt) in zip(axs, [("SR", "Strike rate", "{:.1f}"), ("dot", "Dot-ball %", "{:.1f}%"),
                                  ("out", "Dismissal % per ball", "{:.2f}%"), ("wpa_swing", "Avg win-prob swing / ball", "{:.2f} pts")]):
    v = [val["normal"][k], val["pressure"][k]]
    bars = ax.bar(["Normal", "Pressure"], v, color=[MUTE, C1], width=0.6)
    for r_, x in zip(bars, v):
        ax.text(r_.get_x() + r_.get_width() / 2, x, fmt.format(x), ha="center", va="bottom", fontsize=8.5, color=INK)
    ax.set_title(lab, fontsize=9.5); ax.set_ylim(0, max(v) * 1.22); ax.grid(axis="x", visible=False)
fig.suptitle("Pressure balls are harder: lower scoring, more dots and dismissals, 2.2x bigger match swings",
             x=0.01, ha="left", fontsize=10.5, fontweight="bold", y=1.05)
save(fig, "01_pressure_validation")

# ---------- 2. Where pressure occurs: share of pressure balls by over x wickets ----------
fig, axs = plt.subplots(1, 2, figsize=(9.2, 3.2), sharey=True)
cmap = LinearSegmentedColormap.from_list("seq", ["#f4f8fd", "#9ec5f4", "#3987e5", "#184f95", "#0d366b"])
for ax, inn, ttl in [(axs[0], 1, "1st innings (setting): falling behind par"), (axs[1], 2, "2nd innings (chase): leverage x required demand")]:
    d = b[b.innings == inn]
    pv = d.assign(ov=d.over_no.clip(upper=20), wk=d.wkts_before.clip(upper=7)).pivot_table(index="wk", columns="ov", values="press", aggfunc="mean")
    im = ax.imshow(pv.values * 100, aspect="auto", cmap=cmap, vmin=0, vmax=100, origin="lower")
    ax.set_xticks(range(0, 20, 2)); ax.set_xticklabels(range(1, 21, 2)); ax.set_yticks(range(len(pv.index)))
    ax.set_yticklabels([str(i) if i < 7 else "7+" for i in pv.index]); ax.grid(False)
    ax.set_xlabel("Over"); ax.set_title(ttl, fontsize=9.5)
axs[0].set_ylabel("Wickets down")
cb = fig.colorbar(im, ax=axs, shrink=0.85, pad=0.02); cb.set_label("% of balls flagged as pressure")
save(fig, "02_pressure_heatmap")

# chase pressure vs win probability
d2 = b[b.innings == 2]
band = pd.cut(d2.wp_before, [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0])
pw = d2.groupby(band, observed=True).press.mean() * 100
fig, ax = plt.subplots(figsize=(4.4, 2.7))
ax.bar(range(len(pw)), pw.values, color=C1, width=0.7)
ax.set_xticks(range(len(pw))); ax.set_xticklabels([f"{int(i.left*100)}-{int(i.right*100)}" for i in pw.index], rotation=45, fontsize=7.5)
ax.set_xlabel("Chasing side's win probability (%)"); ax.set_ylabel("% balls = pressure"); ax.grid(axis="x", visible=False)
ax.set_title("Chase pressure peaks when the game is in the balance", fontsize=9.5)
save(fig, "03_pressure_vs_wp")
S["pressure_by_wp"] = {str(k): float(v) for k, v in pw.items()}

# ---------- 3. Example match WP curve ----------
# the IPL chase with the biggest pressure contribution from a top-10 batter
top_bat = BAT[BAT.eligible].head(10)
cand = b[(b.innings == 2) & b.is_ipl & b.striker_id.isin(top_bat.index) & b.press]
mid = cand.groupby("match_id").dwp.sum().idxmax()
mm = b[b.match_id == mid].copy()
mm["x"] = np.where(mm.innings == 1, mm.legal_before, 120 + mm.legal_before) / 6
hero = cand[cand.match_id == mid].striker_name.mode().iat[0]
mi_ = pd.read_pickle(f"{OUT}/matches.pkl").set_index("match_id").loc[mid]
fig, ax = plt.subplots(figsize=(9.2, 2.9))
c2 = mm[mm.innings == 2]
ax.fill_between(c2.x, 0, 100, where=c2.press.values, color=C1, alpha=0.10, step="mid", lw=0, label="Pressure balls (chase)")
c1 = mm[mm.innings == 1]
ax.fill_between(c1.x, 0, 100, where=c1.press.values, color=C2, alpha=0.10, step="mid", lw=0, label="Pressure balls (setting)")
chase_team = c2.batting_team_id.iat[0]
wp_chase = np.where(mm.innings == 2, mm.wp_before, 1 - mm.wp_before) * 100
ax.plot(mm.x, wp_chase, color=INK, lw=1.8, label="Chasing side win probability")
hb = c2[c2.striker_name == hero]
ax.scatter(hb.x[hb.runs >= 4], hb.wp_before[hb.runs >= 4] * 100, s=22, color=C1, zorder=3, label=f"{hero} boundaries")
ax.axvline(20, color=MUTE, lw=0.8, ls="--"); ax.set_ylim(0, 100); ax.set_xlim(0, mm.x.max() + 0.3)
ax.set_xlabel("Overs (0-20 first innings, 20-40 chase)"); ax.set_ylabel("Win prob. %")
ax.set_title(f"How the model reads a match: {mi_.home_team} vs {mi_.away_team}, {mi_.match_date.date()} ({mi_.result})", fontsize=9.5)
ax.legend(loc="upper left", fontsize=7.5, frameon=False, ncol=2)
save(fig, "04_match_example")
S["example_match"] = dict(match_id=int(mid), hero=hero, result=mi_.result, date=str(mi_.match_date.date()),
                          teams=f"{mi_.home_team} vs {mi_.away_team}")

# ---------- 4. Ratings with CIs ----------
def rating_chart(R, title, name, color):
    E = R[R.eligible].head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    y = np.arange(len(E))
    top = E["rank"] <= 10
    ax.hlines(y, E.rating_lo, E.rating_hi, color=np.where(top, color, MUTE), lw=2.2, alpha=0.45)
    ax.scatter(E.rating, y, s=48, color=np.where(top, color, MUTE), zorder=3, edgecolor="white", linewidth=1.5)
    for yi, (r_, rk) in enumerate(zip(E.rating, E["rank"])):
        ax.text(E.rating_hi.iloc[yi] + 0.8, yi, f"{r_:.1f}", va="center", fontsize=8, color=INK)
    ax.set_yticks(y); ax.set_yticklabels([f"{int(rk)}. {n}" for n, rk in zip(E.name, E["rank"])], fontsize=8.5)
    ax.axvline(50, color=MUTE, lw=0.8, ls=":"); ax.text(50.3, len(E) - 0.4, "avg eligible = 50", fontsize=7, color=MUTE)
    ax.set_xlabel("Pressure Reliability Rating (dot) with 90% bootstrap interval (line)")
    ax.set_title(title, fontsize=10); ax.grid(axis="y", visible=False)
    save(fig, name)
rating_chart(BAT, "Top 15 batters under pressure (top 10 coloured)", "05_bat_ratings", C1)
rating_chart(BOWL, "Top 15 bowlers under pressure (top 10 coloured)", "06_bowl_ratings", C2)

# ---------- 5. Component contributions ----------
W = meta["bat"]["weights"]; LAB = {"run_value": "Run value", "wicket_value": "Wicket value", "consistency": "Consistency",
                                  "lift": "Pressure lift", "impact": "Win impact (WPA)"}
COLS = [C1, C2, C3, C4, C5]
def contrib_chart(R, role, name, title):
    E = R[R.eligible].head(10).iloc[::-1]
    tsd = meta[role]["true_sd"]
    Ee = R[R.eligible]
    fig, ax = plt.subplots(figsize=(6.4, 3.9))
    y = np.arange(len(E)); left_pos = np.zeros(len(E)); left_neg = np.zeros(len(E))
    for (c, w), col in zip(W.items(), COLS):
        v = w * (E[c] - Ee[c].mean()) / tsd[c]
        lp = np.where(v >= 0, left_pos, left_neg)
        ax.barh(y, v, left=lp, color=col, height=0.62, label=LAB[c], edgecolor="white", linewidth=1)
        left_pos += np.where(v >= 0, v, 0); left_neg += np.where(v < 0, v, 0)
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_yticks(y); ax.set_yticklabels(E.name, fontsize=8.5); ax.grid(axis="y", visible=False)
    ax.set_xlabel("Contribution to composite (weight x true-talent SDs above eligible mean)")
    ax.legend(fontsize=7, frameon=False, ncol=5, loc="upper center", bbox_to_anchor=(0.45, -0.17))
    ax.set_title(title, fontsize=10)
    save(fig, name)
contrib_chart(BAT, "bat", "07_bat_components", "What drives each batter's rating")
contrib_chart(BOWL, "bowl", "08_bowl_components", "What drives each bowler's rating")

# ---------- 6. Pressure vs normal scatter ----------
def pvn(R, role, name):
    E = R[R.eligible].copy()
    if role == "bat":
        E["xp"] = E.runs_np / E.balls_np * 100 - E.xr_np / E.balls_np * 100
        E["yp"] = E.runs_p / E.balls_p * 100 - E.xr_p / E.balls_p * 100
        xl, yl, ttl = "Normal: strike rate above expected", "Pressure: strike rate above expected", "Batters: normal vs pressure scoring (runs per 100 balls above context-expected)"
    else:
        E["xp"] = (E.xr_np - E.runs_np) / E.balls_np * 6
        E["yp"] = (E.xr_p - E.runs_p) / E.balls_p * 6
        xl, yl, ttl = "Normal: runs saved per over vs expected", "Pressure: runs saved per over vs expected", "Bowlers: normal vs pressure economy (runs saved per over vs context-expected)"
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    top = E["rank"] <= 10
    ax.scatter(E.xp[~top], E.yp[~top], s=np.clip(E.press_balls[~top] / 8, 8, 90), color=MUTE, alpha=0.45, edgecolor="white", lw=0.6)
    ax.scatter(E.xp[top], E.yp[top], s=np.clip(E.press_balls[top] / 8, 8, 90), color=C1 if role == "bat" else C2, edgecolor="white", lw=1.2, zorder=3)
    SHORT = {"Abhishek Sharma": "Abhishek", "Suryakumar Yadav": "SKY", "Namboori Tilak Varma": "Tilak", "Phil Salt": "Salt"}
    OFF = {"Phil Salt": (-22, 4), "Suryakumar Yadav": (6, -9), "Virat Kohli": (-8, -11), "Namboori Tilak Varma": (6, 4)}
    if role == "bat":
        for _, r_ in E[top].iterrows():
            ax.annotate(SHORT.get(r_["name"], r_["name"].split()[-1]), (r_.xp, r_.yp), xytext=OFF.get(r_["name"], (4, 3)),
                        textcoords="offset points", fontsize=7.5, color=INK)
    else:
        BOFF = {1: (8, 6), 2: (-14, 10), 3: (-30, -4), 4: (10, 8), 5: (-6, -14), 6: (8, 0), 7: (8, 0), 8: (-12, -12), 9: (6, -12), 10: (12, -4)}
        for _, r_ in E[top].iterrows():
            rk = int(r_["rank"])
            ax.annotate(str(rk), (r_.xp, r_.yp), xytext=BOFF.get(rk, (5, 3)), textcoords="offset points", fontsize=7.5,
                        color=INK, fontweight="bold", arrowprops=dict(arrowstyle="-", color=MUTE, lw=0.5))
        BN = {"Varun Chakravarthy": "Varun", "Mustafizur Rahman": "Mustafizur", "Kuldeep Yadav": "Kuldeep", "Rashid Khan": "Rashid",
              "Bhuvneshwar Kumar": "Bhuvneshwar", "Sufiyan Muqeem": "Muqeem", "Jasprit Bumrah": "Bumrah"}
        items = [f"{int(r_['rank'])} {BN.get(r_['name'], r_['name'].split()[-1])}" for _, r_ in E[top].iterrows()]
        ax.text(0.01, 0.99, "Top 10:  " + "   ".join(items[:5]) + "\n              " + "   ".join(items[5:]), transform=ax.transAxes, fontsize=6.8, va="top", color=INK2)
        ax.set_xlim(-3, 3.2); ax.set_ylim(-3, 3.6)
    lim = [min(E.xp.min(), E.yp.min()) - 2, max(E.xp.max(), E.yp.max()) + 2]
    ax.plot(lim, lim, color=MUTE, lw=0.8, ls="--")
    ax.axhline(0, color=GRID, lw=1); ax.axvline(0, color=GRID, lw=1)
    ax.set_xlabel(xl); ax.set_ylabel(yl); ax.set_title(ttl, fontsize=9.5)
    ax.text(0.99, 0.02, "Above the dashed line = better under pressure than usual.\nDot size = pressure balls.", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=7, color=INK2)
    save(fig, name)
pvn(BAT, "bat", "09_bat_pressure_vs_normal"); pvn(BOWL, "bowl", "10_bowl_pressure_vs_normal")

# ---------- 7. Reliability: stabilisation points ----------
fig, axs = plt.subplots(1, 2, figsize=(9.2, 2.8), sharex=False)
for ax, role, col in [(axs[0], "bat", C1), (axs[1], "bowl", C2)]:
    H = meta[role]["hyper"]
    lv = meta[role]["lift_metric"]
    items = [("Run value", H["v_run|p"]["k"]), ("Net run value", H["v_nrv|p"]["k"]),
             ("Win impact (WPA)", H["v_wpa|p"]["k"]), ("Wicket value", H["v_wkt|p"]["k"]),
             ("Clutch lift", H[f"{lv}|p"]["s2"] / H[f"{lv}|dev"]["tau2"])]
    ax.barh([i[0] for i in items][::-1], [i[1] for i in items][::-1], color=col, height=0.6)
    for yi, v in enumerate([i[1] for i in items][::-1]):
        ax.text(v + 40, yi, f"{v:,.0f}", va="center", fontsize=8)
    ax.set_title(f"{'Batting' if role == 'bat' else 'Bowling'}: balls needed for 50% signal", fontsize=9.5)
    ax.set_xlim(0, 3900); ax.grid(axis="y", visible=False); ax.tick_params(axis="y", labelsize=8)
save(fig, "11_stabilisation")

# bootstrap probability top-10
fig, axs = plt.subplots(1, 2, figsize=(9.2, 3.0))
for ax, R, col, ttl in [(axs[0], BAT, C1, "Batters"), (axs[1], BOWL, C2, "Bowlers")]:
    E = R[R.eligible].head(10)
    ax.bar(range(10), E.p_top10 * 100, color=col, width=0.65)
    for i, v in enumerate(E.p_top10 * 100): ax.text(i, v + 1.5, f"{v:.0f}%", ha="center", fontsize=7.5)
    ax.set_xticks(range(10)); ax.set_xticklabels([n.split()[-1] for n in E.name], rotation=45, ha="right", fontsize=7.5)
    ax.set_ylim(0, 105); ax.set_ylabel("% of 400 resamples in top 10"); ax.set_title(f"{ttl}: rank stability", fontsize=9.5)
    ax.grid(axis="x", visible=False)
save(fig, "12_rank_stability")

# ---------- 8. RR squad gap ----------
rr = mp[(mp.comp_name == "IPL 2026") & (mp.team_name == "Rajasthan Royals")].player_id
fig, axs = plt.subplots(1, 2, figsize=(9.2, 3.3))
rrsum = {}
for ax, R, role, col in [(axs[0], BAT, "Batting", C1), (axs[1], BOWL, "Bowling", C2)]:
    E = R[R.eligible]
    rrE = E[E.index.isin(rr)].sort_values("rating")
    t10 = E.head(10)
    y = np.arange(len(rrE))
    ax.barh(y, rrE.rating - 50, left=50, color="#e87ba4", height=0.55)
    for yi, (_, r_) in enumerate(rrE.iterrows()):
        ax.text(max(r_.rating, 50) + 0.6, yi, f"#{int(r_['rank'])} of {len(E)}", va="center", fontsize=7.5, color=INK2)
    ax.axvspan(t10.rating.min(), t10.rating.max(), color=col, alpha=0.12, lw=0)
    ax.text((t10.rating.min() + t10.rating.max()) / 2, -0.45, "our top-10 range", ha="center", va="center", fontsize=7.5, color=col)
    ax.axvline(50, color=INK2, lw=0.8)
    ax.set_yticks(y); ax.set_yticklabels(rrE.name, fontsize=8); ax.set_xlim(28, 85); ax.grid(axis="y", visible=False)
    ax.set_xlabel("Pressure Reliability Rating (50 = eligible average)")
    ax.set_title(f"{role}: RR 2026 squad (eligible players)", fontsize=9.5)
    rrsum[role] = rrE.sort_values("rating", ascending=False)[["name", "rating", "rank", "press_balls"]].assign(rank=lambda d: d["rank"].astype(int)).to_dict("records")
save(fig, "13_rr_gap")
S["rr_squad"] = rrsum
S["rr_ineligible"] = {
    "bat": BAT[BAT.index.isin(rr) & ~BAT.eligible & (BAT.press_balls >= 50)][["name", "rating", "press_balls"]].to_dict("records"),
    "bowl": BOWL[BOWL.index.isin(rr) & ~BOWL.eligible & (BOWL.press_balls >= 50)][["name", "rating", "press_balls"]].to_dict("records")}

# ---------- 9. sensitivity ----------
sens = {}
for role, R0 in [("bat", BAT), ("bowl", BOWL)]:
    top = set(R0[R0.eligible].head(10).index); rows = []
    for tag, lab in [("_q70", "Pressure = top 30% of balls"), ("_q80", "Pressure = top 20% of balls"), ("_eq", "Equal component weights"),
                     ("_cl", "Clutch-heavy weights"), ("_norec", "No recency weighting"), ("_noopp", "No opposition weighting")]:
        R = pd.read_pickle(f"{OUT}/{role}_ratings{tag}.pkl"); E = R[R.eligible]
        rows.append(dict(variant=lab, overlap=len(top & set(E.head(10).index)),
                         rho=float(R0.loc[R0.eligible, "rating"].corr(R.reindex(R0[R0.eligible].index).rating, method="spearman"))))
    sens[role] = rows
S["sensitivity"] = sens

# ---------- tables ----------
def table(R, role):
    E = R[R.eligible].head(10)
    rows = []
    for pid, r_ in E.iterrows():
        d = dict(rank=int(r_["rank"]), pid=int(pid), name=r_["name"], rating=r_.rating, lo=r_.rating_lo, hi=r_.rating_hi,
                 p_top10=r_.p_top10, press_balls=int(r_.press_balls), p_inns=int(r_.p_inns),
                 run_value=r_.run_value, wicket_value=r_.wicket_value, consistency=r_.consistency, lift=r_.lift, impact=r_.impact,
                 team=TEAM.get(r_.last_ipl_team_id, "-") if pd.notna(r_.last_ipl_team_id) else "Not in IPL data",
                 last_ipl=int(r_.last_ipl_year) if pd.notna(r_.last_ipl_year) else None,
                 n_ipl=int(r_["n_IPL"]) if pd.notna(r_["n_IPL"]) else 0, n_t20i=int(r_["n_T20I/Other"]) if pd.notna(r_["n_T20I/Other"]) else 0,
                 nrv_ipl=r_["nrv100_IPL"], nrv_t20i=r_["nrv100_T20I/Other"])
        if role == "bat":
            d.update(runs_p=int(r_.runs_p), balls_p=int(r_.balls_p), outs_p=int(r_.outs_p), sr_p=r_.runs_p / r_.balls_p * 100,
                     xsr_p=r_.xr_p / r_.balls_p * 100, sr_n=r_.runs_np / r_.balls_np * 100, xsr_n=r_.xr_np / r_.balls_np * 100,
                     avg_p=r_.runs_p / max(r_.outs_p, 1), dot_p=r_.dots_p / r_.balls_p * 100, bnd_p=(r_.b4_p + r_.b6_p) / r_.balls_p * 100)
        else:
            d.update(runs_p=int(r_.runs_p), balls_p=int(r_.balls_p), wkts_p=int(r_.outs_p), econ_p=r_.runs_p / r_.balls_p * 6,
                     xecon_p=r_.xr_p / r_.balls_p * 6, econ_n=r_.runs_np / r_.balls_np * 6, xecon_n=r_.xr_np / r_.balls_np * 6,
                     sr_p=r_.balls_p / max(r_.outs_p, 1), dot_p=r_.dots_p / r_.balls_p * 100)
        rows.append(d)
    return rows
S["top_bat"] = table(BAT, "bat"); S["top_bowl"] = table(BOWL, "bowl")
S["n_matches"] = int(b.match_id.nunique()); S["n_balls"] = int(len(b))
S["n_ipl_matches"] = int(b[b.is_ipl].match_id.nunique())
S["eligible"] = {r: meta[r]["eligible"] for r in meta}
S["temporal"] = {r: dict(eb=meta[r]["temporal_r_eb"], raw=meta[r]["temporal_r_raw"], n=meta[r]["temporal_n"]) for r in meta}
json.dump(S, open(f"{OUT}/summary.json", "w"), indent=1, default=lambda o: None if pd.isna(o) else float(o))

# full eligible leaderboard CSVs
for role, R in [("bat", BAT), ("bowl", BOWL)]:
    cols = ["rank", "name", "rating", "rating_lo", "rating_hi", "p_top10", "median_rank", "press_balls", "p_inns", "run_value",
            "wicket_value", "consistency", "lift", "impact", "runs_p", "balls_p", "outs_p", "runs_np", "balls_np", "outs_np"]
    R[R.eligible][cols].round(3).to_csv(f"{OUT}/{role}_leaderboard.csv", index_label="player_id")
print(json.dumps({k: S[k] for k in ["validation", "example_match", "sensitivity", "temporal", "eligible"]}, indent=1, default=str))
