"""Step 5: data files for the interactive dashboard."""
import sys, json, numpy as np, pandas as pd
OUT, DD, DP = sys.argv[1], sys.argv[2], sys.argv[3]
b = pd.read_pickle(f"{OUT}/balls.pkl"); S = json.load(open(f"{OUT}/summary.json"))
TEAM = {1: "CSK", 2: "MI", 3: "RR", 4: "PBKS", 5: "RCB", 7: "DC", 8: "KKR", 242: "SRH", 3508: "GT", 3509: "LSG"}
mp = pd.read_csv(f"{DP}/competition_team_player_mapping.csv")
rr = set(mp[(mp.comp_name == "IPL 2026") & (mp.team_name == "Rajasthan Royals")].player_id)
code = {k: open(f"{k}").read() for k in ["s1_prep_wp.py", "s2_ratings.py"]}
def dump(name, rows, desc):
    rows = json.loads(pd.DataFrame(rows).to_json(orient="records"))
    meta = [{"label": "Method", "value": desc}, {"label": "Input", "value": "RR SupeRR Selector data pack (ball_by_ball.csv, matches.csv, competitions.csv, competition_team_player_mapping.csv)"},
            {"label": "s2_ratings.py", "value": code["s2_ratings.py"], "type": "code", "lang": "python"}]
    json.dump({"rows": rows, "meta": meta}, open(f"{DD}/{name}.json", "w"))
for role in ["bat", "bowl"]:
    R = pd.read_pickle(f"{OUT}/{role}_ratings.pkl"); E = R[R.eligible].copy()
    d = pd.DataFrame({"rank": E["rank"].astype(int), "name": E["name"],
                      "team": [TEAM.get(t, "–") if pd.notna(t) else "–" for t in E.last_ipl_team_id],
                      "rr_2026": E.index.isin(rr), "rating": E.rating.round(1), "rating_lo": E.rating_lo.round(1), "rating_hi": E.rating_hi.round(1),
                      "top10_pct": (E.p_top10 * 100).round(0).astype(int), "press_balls": E.press_balls.astype(int), "press_inns": E.p_inns.astype(int),
                      "run_value": E.run_value.round(1), "wicket_value": E.wicket_value.round(1), "consistency": E.consistency.round(1),
                      "lift": E.lift.round(1), "impact": E.impact.round(1)})
    if role == "bat":
        d["runs_p"] = E.runs_p.astype(int); d["balls_p"] = E.balls_p.astype(int); d["outs_p"] = E.outs_p.astype(int)
        d["sr_p"] = (E.runs_p / E.balls_p * 100).round(1); d["xsr_p"] = (E.xr_p / E.balls_p * 100).round(1)
        d["sr_n"] = (E.runs_np / E.balls_np * 100).round(1); d["xsr_n"] = (E.xr_np / E.balls_np * 100).round(1)
        d["above_exp_p"] = (d.sr_p - d.xsr_p).round(1); d["above_exp_n"] = (d.sr_n - d.xsr_n).round(1)
    else:
        d["runs_p"] = E.runs_p.astype(int); d["balls_p"] = E.balls_p.astype(int); d["wkts_p"] = E.outs_p.astype(int)
        d["econ_p"] = (E.runs_p / E.balls_p * 6).round(2); d["xecon_p"] = (E.xr_p / E.balls_p * 6).round(2)
        d["econ_n"] = (E.runs_np / E.balls_np * 6).round(2); d["xecon_n"] = (E.xr_np / E.balls_np * 6).round(2)
        d["above_exp_p"] = (d.xecon_p - d.econ_p).round(2); d["above_exp_n"] = (d.xecon_n - d.econ_n).round(2)
    dump(f"{role}_leaderboard", d.sort_values("rank"),
         "Eligible players (>=120 pressure balls, >=10 pressure innings/spells, played in 2026). Rating = 50 + 10z of a weighted composite of Bayesian-shrunk run value, wicket value, consistency, pressure lift and win impact on pressure balls; 90% interval and top-10 % from 400 match bootstrap resamples.")
V = S["validation"]
rows = [{"metric": k, "label": l, "normal": round(V["normal"][k], 2), "pressure": round(V["pressure"][k], 2)} for k, l in
        [("SR", "Strike rate"), ("dot", "Dot-ball %"), ("bnd", "Boundary %"), ("out", "Dismissal % per ball"), ("econ", "Economy"), ("wpa_swing", "Win-prob swing per ball (pts)")]]
rows.append({"metric": "share", "label": "Share of balls flagged as pressure (%)", "normal": None, "pressure": round(V["share_pressure"], 1)})
dump("pressure_validation", rows, "League-wide outcomes on pressure balls (Pressure Index percentile >= 0.75, knockouts x1.25) vs all other balls, 843 completed matches 2022-26.")
h = b.assign(over=b.over_no.clip(upper=20), wkts=b.wkts_before.clip(upper=7)).groupby(["innings", "over", "wkts"]).agg(share=("press", "mean"), balls=("press", "size")).reset_index()
h["share"] = (h.share * 100).round(1); h = h[h.balls >= 20]
dump("pressure_heatmap", h, "Share of deliveries flagged as pressure by innings, over and wickets down (cells with >=20 balls).")
sens = [{"variant": x["variant"], "bat_overlap": x["overlap"], "bat_rho": round(x["rho"], 3), "bowl_overlap": y["overlap"], "bowl_rho": round(y["rho"], 3)}
        for x, y in zip(S["sensitivity"]["bat"], S["sensitivity"]["bowl"])]
dump("sensitivity", sens, "Overlap of the top 10 and Spearman correlation of ratings when one modelling choice is changed.")
print({f: len(json.load(open(f"{DD}/{f}.json"))["rows"]) for f in ["bat_leaderboard", "bowl_leaderboard", "pressure_validation", "pressure_heatmap", "sensitivity"]})
