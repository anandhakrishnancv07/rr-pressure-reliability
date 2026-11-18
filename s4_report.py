"""Step 4: build the methodology report PDF."""
import sys, json
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Image, Table, TableStyle,
                                PageBreak, KeepTogether, NextPageTemplate)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage

OUT, FIG, PDF, DASH = sys.argv[1], sys.argv[2], sys.argv[3], (sys.argv[4] if len(sys.argv) > 4 else "")
S = json.load(open(f"{OUT}/summary.json")); M = json.load(open(f"{OUT}/model_meta.json"))
F = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("DV", F + "DejaVuSans.ttf")); pdfmetrics.registerFont(TTFont("DVB", F + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DVI", F + "DejaVuSans-Oblique.ttf")); pdfmetrics.registerFont(TTFont("DVC", F + "DejaVuSansCondensed.ttf"))
pdfmetrics.registerFont(TTFont("DVCB", F + "DejaVuSansCondensed-Bold.ttf"))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("DV", normal="DV", bold="DVB", italic="DVI", boldItalic="DVB")

PINK = colors.HexColor("#E2187F"); NAVY = colors.HexColor("#1D3A8A"); INK = colors.HexColor("#141414")
INK2 = colors.HexColor("#4a4a46"); GRID = colors.HexColor("#dcdad4"); TINT = colors.HexColor("#f6f4ef"); BLUE = colors.HexColor("#2a78d6")
ORANGE = colors.HexColor("#eb6834"); PINKT = colors.HexColor("#fde8f2")

st = {
    "h1": ParagraphStyle("h1", fontName="DVB", fontSize=16, leading=20, textColor=NAVY, spaceBefore=4, spaceAfter=8, keepWithNext=1),
    "h2": ParagraphStyle("h2", fontName="DVB", fontSize=11.5, leading=15, textColor=INK, spaceBefore=10, spaceAfter=4, keepWithNext=1),
    "body": ParagraphStyle("body", fontName="DV", fontSize=9.2, leading=13.4, textColor=INK, spaceAfter=5),
    "small": ParagraphStyle("small", fontName="DV", fontSize=8, leading=11, textColor=INK2, spaceAfter=4),
    "cap": ParagraphStyle("cap", fontName="DVI", fontSize=7.8, leading=10.5, textColor=INK2, spaceAfter=8),
    "bul": ParagraphStyle("bul", fontName="DV", fontSize=9.2, leading=13.2, textColor=INK, leftIndent=11, bulletIndent=2, spaceAfter=2.5),
    "cell": ParagraphStyle("cell", fontName="DVC", fontSize=7.6, leading=9.6, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="DVCB", fontSize=7.6, leading=9.6, textColor=INK),
    "hcell": ParagraphStyle("hcell", fontName="DVCB", fontSize=7.4, leading=9.2, textColor=colors.white),
    "formula": ParagraphStyle("formula", fontName="DV", fontSize=8.6, leading=12.5, textColor=INK, leftIndent=10,
                              backColor=TINT, borderPadding=(5, 6, 5, 6), spaceBefore=4, spaceAfter=9),
    "card_t": ParagraphStyle("ct", fontName="DVB", fontSize=9.6, leading=12, textColor=NAVY, spaceAfter=1),
    "card": ParagraphStyle("card", fontName="DV", fontSize=8.4, leading=11.6, textColor=INK, spaceAfter=0),
}
def P(t, s="body"): return Paragraph(t, st[s])
def B(items): return [Paragraph(i, st["bul"], bulletText="•") for i in items]
W = A4[0] - 36 * mm
def img(name, width=W, cap=None):
    path = f"{FIG}/{name}.png"; w, h = PILImage.open(path).size
    out = [Image(path, width=width, height=width * h / w)]
    if cap: out.append(P(cap, "cap"))
    return KeepTogether(out)
def table(data, widths, header_bg=NAVY, zebra=True, extra=None):
    rows = [[Paragraph(str(c), st["hcell"]) for c in data[0]]] + \
           [[c if hasattr(c, "wrap") else Paragraph(str(c), st["cell"]) for c in r] for r in data[1:]]
    t = Table(rows, colWidths=widths, repeatRows=1)
    sty = [("BACKGROUND", (0, 0), (-1, 0), header_bg), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
           ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRID), ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
           ("LEFTPADDING", (0, 0), (-1, -1), 3.5), ("RIGHTPADDING", (0, 0), (-1, -1), 3.5)]
    if zebra:
        for i in range(1, len(rows)):
            if i % 2 == 0: sty.append(("BACKGROUND", (0, i), (-1, i), TINT))
    if extra: sty += extra
    t.setStyle(TableStyle(sty)); return t
def f1(x): return "–" if x is None else f"{x:.1f}"
def f0(x): return "–" if x is None else f"{x:.0f}"
def sg(x, d=1): return "n/a" if x is None or x != x else (f"+{x:.{d}f}" if x >= 0 else f"−{abs(x):.{d}f}")

def on_page(c, doc):
    c.saveState()
    c.setFillColor(PINK); c.rect(0, A4[1] - 5 * mm, A4[0], 5 * mm, fill=1, stroke=0)
    c.setFillColor(NAVY); c.rect(0, A4[1] - 6.2 * mm, A4[0], 1.2 * mm, fill=1, stroke=0)
    c.setFont("DV", 7.2); c.setFillColor(INK2)
    c.drawString(18 * mm, 10 * mm, "SupeRR Selector S2 · Round 1 · Most Reliable Players Under Pressure")
    c.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}")
    c.restoreState()

doc = BaseDocTemplate(PDF, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=17 * mm,
                      title="Most Reliable Players Under Pressure — Methodology & Rankings", author="SupeRR Selector S2 submission")
doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")], onPage=on_page)])
s = []
V = S["validation"]; TB = S["top_bat"]; TW = S["top_bowl"]
mb, mw = M["bat"], M["bowl"]

# ======================= PAGE 1: EXECUTIVE SUMMARY =======================
s.append(Paragraph("<font color='#E2187F'>SUPERR SELECTOR · SEASON 2 · ROUND 1</font>", ParagraphStyle("k", fontName="DVB", fontSize=8.5, textColor=PINK, spaceAfter=3)))
s.append(Paragraph("Who delivers when it matters?", ParagraphStyle("t", fontName="DVB", fontSize=22, leading=26, textColor=NAVY, spaceAfter=2)))
s.append(Paragraph("A win-probability pressure model and Bayesian reliability ratings for batters and bowlers, IPL + T20I 2022–2026",
                   ParagraphStyle("st", fontName="DV", fontSize=10.5, leading=14, textColor=INK2, spaceAfter=10)))
s.append(P(f"<b>The question.</b> Which players perform best, and most dependably, in the moments that decide T20 matches — and whom should "
           f"Rajasthan Royals back at the IPL 2027 auction? <b>The data.</b> {S['n_balls']:,} deliveries from {S['n_matches']} completed matches "
           f"({S['n_ipl_matches']} IPL, the rest T20Is and two emerging-team tournaments), Jan 2022 – Nov 2026."))
s.append(P("<b>The approach in one line.</b> We score every delivery for pressure using a win-probability model (how much the match can swing on this ball) "
           "combined with scoreboard demand (how far the batting side is behind what its remaining resources normally produce). "
           "The top 25% of balls are 'pressure balls'. On those balls we measure each player against a context-expected baseline, "
           "estimate true pressure ability with Bayesian shrinkage so small samples cannot fluke their way to the top, "
           "and test every ranking with 400 bootstrap resamples."))
# top-10 side-by-side table
rows = [["#", "Batter", "Rating (90% CI)", "Top-10 prob.", "#", "Bowler", "Rating (90% CI)", "Top-10 prob."]]
for a, b_ in zip(TB, TW):
    rows.append([str(a["rank"]), Paragraph(f"<b>{a['name']}</b>", st["cell"]), f"{a['rating']:.1f} ({a['lo']:.0f}–{a['hi']:.0f})", f"{a['p_top10']*100:.0f}%",
                 str(b_["rank"]), Paragraph(f"<b>{b_['name']}</b>", st["cell"]), f"{b_['rating']:.1f} ({b_['lo']:.0f}–{b_['hi']:.0f})", f"{b_['p_top10']*100:.0f}%"])
s.append(Spacer(1, 3))
s.append(table(rows, [7 * mm, 38 * mm, 26 * mm, 16 * mm, 7 * mm, 38 * mm, 26 * mm, 16 * mm],
               extra=[("LINEAFTER", (3, 0), (3, -1), 1.2, colors.white), ("BACKGROUND", (0, 0), (3, 0), BLUE), ("BACKGROUND", (4, 0), (-1, 0), ORANGE)]))
s.append(P("Rating: 50 = average eligible player; each 10 points = one standard deviation of the composite. CI = 5th–95th percentile across 400 match-level bootstrap "
           "resamples. Top-10 prob. = share of resamples in which the player finished in the top 10.", "cap"))
s.append(P("<b>Five things the data told us</b>", "h2"))
s += B([
    f"<b>Pressure is real and measurable.</b> On pressure balls the league strike rate falls from {V['normal']['SR']:.0f} to {V['pressure']['SR']:.0f}, "
    f"dot balls rise from {V['normal']['dot']:.1f}% to {V['pressure']['dot']:.1f}%, and each ball moves the match {V['pressure']['wpa_swing']/V['normal']['wpa_swing']:.1f}× as much.",
    "<b>Skill travels; 'clutch' is a small extra.</b> Players who are good in general are good under pressure. The pressure-specific "
    f"deviation is real but small (batting year-to-year correlation r = {S['temporal']['bat']['raw']:.2f}; bowling r = {S['temporal']['bowl']['raw']:.2f}). "
    "So we estimate pressure ability as <i>overall skill + a shrunk pressure lift</i>, which is far more predictive than raw pressure averages.",
    "<b>Bowling under pressure is more repeatable than batting.</b> A bowler's pressure record carries over from 2022–24 to 2025–26 more than twice as strongly as a batter's.",
    "<b>The top of both lists is robust.</b> Changing the pressure cut-off, the weights, or the recency/opposition weighting keeps 8–10 of the 10 batters (6 under the widest pressure definition) "
    "and 8–10 of the 10 bowlers in the top 10 (Spearman ρ ≥ 0.96 in every variant).",
    "<b>RR's gap is clear.</b> RR's best 2026 pressure batter ranks #20 and best bowler #31 of ~100 eligible players. "
    "Priorities for 2027: a middle-order/finishing batter who scores above expectation in chases, and a wicket-taking spinner or death seamer.",
])
s.append(PageBreak())

# ======================= 1. DATA =======================
s.append(P("1. Data and preparation", "h1"))
s.append(P("We used all six files in the data pack. Ball-by-ball records were joined to matches (venue, stage, knockout flag, result, rain revisions), "
           "competitions (IPL vs T20I, season) and team lists. Cleaning rules:"))
s += B([
    "Excluded 40 abandoned / no-result matches and super-over innings (innings 3–4). Tied matches decided by super over keep their recorded winner.",
    "<b>Legal balls</b> exclude wides and no-balls ('Overstep' / 'other'). Balls faced by a batter exclude wides. "
    "<b>Runs charged to a bowler</b> = bat runs + wides + no-ball penalty (byes and leg-byes excluded).",
    "<b>Bowler wickets</b> = caught, bowled, LBW, stumped, hit wicket. Run-outs, retirements and obstruction count against the batting team but not for the bowler.",
    "<b>Rain-affected matches</b>: overs and targets use the revised values (e.g. 114 balls, revised target), so 'balls remaining' and 'runs required' are always correct.",
    "<b>Scoring environment ('par')</b>: average completed first-innings total for each competition type and year — e.g. IPL 2022 ≈ 171 vs IPL 2026 ≈ 196, T20I ≈ 166–182. "
    "Every expectation is measured relative to the par of its own season, so the Impact Player era's inflated totals don't distort comparisons.",
])

# ======================= 2. PRESSURE =======================
s.append(P("2. Defining pressure", "h1"))
s.append(P("Pressure is the combination of <b>stakes</b> (how much the result can change on this ball) and <b>demand</b> (how hard the "
           "situation is relative to the resources left). We measure both for every delivery, separately for the two innings because they create pressure differently."))
s.append(P("2.1 Stakes: a win-probability model", "h2"))
s.append(P("For the chase we trained a gradient-boosted classifier (monotonic constraints so that more runs needed always lowers win chances, more wickets in hand raises them) "
           "on runs required, balls left, wickets in hand, required run rate, target, par and competition. "
           f"On a held-out 20% of matches it scores <b>AUC 0.84, Brier 0.179</b>. For the first innings, we project the final total from the current state and convert the "
           "projected margin over par into a win probability (probit fit on 800+ results, σ ≈ 48 runs). "
           "<b>Leverage</b> of a ball = the expected absolute change in win probability across its possible outcomes (dot, 1, 2, 4, 6, wicket, wide), weighted by how often each outcome happens in that phase. "
           "The Leverage Index (LI) is that value divided by the average, so LI = 2 means the ball matters twice as much as a typical ball."))
s.append(P("2.2 Demand: required runs vs remaining resources (DLS-style)", "h2"))
s.append(P("A second model estimates how many runs a side normally adds from any state (wickets in hand × balls left × par). Demand compares what is needed with that resource:"))
s.append(P("Chase demand = runs still required ÷ runs normally available from the wickets and balls left<br/>"
           "Setting demand = par total ÷ (current score + runs normally available)  — i.e. how far the innings is tracking below par", "formula"))
s.append(P("Demand > 1 means the side must out-perform its resources. It captures the familiar pressure signals in one number: a climbing required rate, "
           "a collapse (wickets falling early cut the resources), and few balls left."))
s.append(P("2.3 The Pressure Index", "h2"))
s.append(P("Chase: PI = √(Leverage Index × Demand)  — both must be high: a hopeless chase has high demand but no leverage; a cruise has neither.<br/>"
           "Setting: PI = Demand (projected total vs par)  — first-innings win probability is too uncertain ball-to-ball to measure leverage reliably (AUC only 0.68), but falling behind par is unambiguous pressure.<br/>"
           "Each PI is converted to a percentile within its innings; knockout matches (finals, qualifiers, eliminators, semi-finals) multiply it by 1.25.<br/>"
           "<b>Pressure ball</b> = adjusted percentile ≥ 0.75 → 25.5% of all deliveries.", "formula"))
s.append(img("02_pressure_heatmap", cap="Figure 1. Where pressure occurs. Left: when setting a total, pressure rises sharply with early wickets (a collapse) and stays high when the side is behind par. "
                                          "Right: in a chase it builds through the middle and death overs as wickets fall and the required rate climbs."))
s.append(img("01_pressure_validation", cap="Figure 2. The definition separates genuinely harder situations: on pressure balls scoring drops, dots and dismissals rise, and every ball swings the match more than twice as much."))
s.append(KeepTogether([P("2.4 Why this definition is meaningful", "h2"),
    P("Three checks: (1) <b>Face validity</b> — Figure 1 reproduces what any captain would call pressure: collapses, chases that are slipping away, tight death overs. "
      "(2) <b>Behavioural validity</b> — Figure 2 shows players actually perform worse in these moments, so the label is not arbitrary. "
      "(3) <b>Balance validity</b> — Figure 3 shows chase pressure is concentrated where the game is genuinely open (30–70% win probability) and almost absent in dead games (<10% or >90%), "
      "so we don't reward 'pressure' runs scored after the result is settled. The definition works identically for batting and bowling because it is a property of the ball, not the player.")]))
s.append(img("03_pressure_vs_wp", width=W * 0.62, cap="Figure 3. Share of chase balls flagged as pressure, by the chasing side's win probability before the ball."))
s.append(img("04_match_example", cap=f"Figure 4. The model reading a real match — Qualifier 2, IPL 2025 ({S['example_match']['result']}). Shaded = pressure balls; dots = {S['example_match']['hero']}'s boundaries, "
                                      "as the chasing side's win probability climbs from ~35% to victory."))

# ======================= 3. PERFORMANCE =======================
s.append(P("3. Measuring performance on every ball", "h1"))
s.append(P("Raw strike rate and economy are unfair under pressure because pressure balls happen in very different contexts (a death-over chase vs a powerplay collapse). "
           "So every player-ball is compared with what an average player would produce <i>in exactly that situation</i>. "
           "Two context models (gradient boosting, trained on all 199k balls) predict expected runs and expected dismissal probability from: innings, balls bowled, wickets down, "
           "required rate, current rate, par, competition and pace/spin."))
rows = [["Credit per ball", "Batter", "Bowler", "Unit"],
        ["Run value", "runs − expected runs", "expected runs conceded − runs conceded", "runs"],
        ["Wicket value", "(expected dismissal prob. − actual) × wicket cost", "(actual bowler wicket − expected) × wicket cost", "runs"],
        ["Win impact (WPA)", "change in batting side's win probability", "minus the change in batting side's win probability", "WP points"]]
s.append(table(rows, [30 * mm, 58 * mm, 64 * mm, 22 * mm]))
s.append(P("<b>Wicket cost</b> is situation-specific: the drop in expected remaining runs when one more wicket falls (≈10 runs in the powerplay, ≈5 in the middle overs, ≈3 at the death). "
           "This lets runs and wickets be added in a common currency: <b>Net Run Value = run value + wicket value</b>. "
           "<b>Baselines</b>: every player has a pressure figure and a normal (non-pressure) figure on the same scale, so 'performance compared with their usual level' is a direct subtraction. "
           "<b>Weights per ball</b>: recency (2026 = 1.0, 2025 = 0.9, 2024 = 0.75, 2023 = 0.6, 2022 = 0.45) × opposition strength (IPL teams and leading T20I sides 1.0; Ireland, Zimbabwe 0.85; A-teams 0.7; associates 0.6).", "body"))

# ======================= 4. RATINGS =======================
s.append(P("4. From ball credits to a player rating", "h1"))
s.append(P("4.1 Bayesian shrinkage — why a hot streak can't top the list", "h2"))
s.append(P("A batter with 150 pressure balls has a very noisy average. We estimated from the data how much of the spread between players is real (method of moments: "
           "observed variance minus sampling variance). The ratio gives the number of balls at which a metric is 50% signal and 50% noise (Figure 5). "
           "Each player's estimate is pulled toward the average by exactly that amount — a player needs a lot of evidence to be rated far from average."))
s.append(P("Pressure estimate = overall skill (all balls, shrunk to league)  +  pressure lift (pressure − normal, shrunk to zero)<br/>"
           "shrinkage factor = τ² ÷ (τ² + σ²/n)    where τ² = true between-player variance, σ² = per-ball variance, n = (weighted) balls", "formula"))
s.append(img("11_stabilisation", cap="Figure 5. Balls needed before a metric is half signal. Scoring rate stabilises quickly; wicket-taking, win impact and the pure 'clutch lift' need thousands of balls — "
                                       "so the model leans on them less. (Where the true variance couldn't be identified, a conservative 3,000-ball prior was used.)"))
s.append(P("4.2 The five components", "h2"))
rows = [["Component", "Definition (on pressure balls)", "Weight", "Why it matters"],
        ["Run value", "Net runs above context expectation per 100 pressure balls (shrunk)", "30%", "Scoring / restricting when the game is tight"],
        ["Wicket value", "Wicket runs saved (bat) or taken (bowl) per 100 pressure balls", "20%", "Staying in / breaking the partnership"],
        ["Consistency", "% of pressure innings/spells (≥5 pressure balls) with net run value ≥ 0, Beta-binomial shrunk", "20%", "Delivers match after match, not one blinder"],
        ["Pressure lift", "Pressure net run value minus own normal net run value (shrunk)", "15%", "Rises (or dips) relative to their usual level"],
        ["Win impact", "Win probability added per 100 pressure balls vs league average (shrunk)", "15%", "Contribution converted to match results"]]
s.append(table(rows, [24 * mm, 74 * mm, 14 * mm, 62 * mm]))
s.append(P("Components are on different scales, so each is divided by its <b>true-talent standard deviation</b> (√τ²) rather than the spread of the estimates. "
           "This is important: a component the data can barely measure (e.g. win impact) has estimates bunched near average after shrinkage, "
           "so it automatically carries less influence than a well-measured one, even with the same nominal weight. "
           "The weighted sum is standardised to <b>Rating = 50 + 10 × z</b> among eligible players.", "body"))
s.append(P("4.3 Fair comparisons and eligibility", "h2"))
s += B([
    f"<b>Sample size</b>: at least 120 pressure balls and 10 separate pressure innings/spells; below that, a player is rated but not ranked. "
    f"{S['eligible']['bat']} batters and {S['eligible']['bowl']} bowlers qualify.",
    "<b>Availability</b>: must have played in 2026, so the list reflects players who can actually feature in 2027 (e.g. a player who last played in mid-2025 is excluded).",
    "<b>Context</b>: every expectation conditions on innings, phase, wickets, required rate, par and pace/spin — openers, finishers, powerplay and death bowlers are each judged against their own situations.",
    "<b>IPL and T20I together</b>: combined because T20I adds most of the pressure sample for many overseas players; scoring differences are removed through year-specific par, "
    "and weaker oppositions are down-weighted. We report each top player's IPL and T20I pressure split so the reader can check the mix.",
])
s.append(PageBreak())

# ======================= 5. RESULTS: BATTERS =======================
s.append(P("5. Results — top 10 batters under pressure", "h1"))
s.append(img("05_bat_ratings", width=W * 0.86, cap="Figure 6. Ratings with 90% bootstrap intervals. Ranks 1–4 are clearly separated from the pack; ranks 5–10 overlap, so their order is a closer call (reflected in top-10 probabilities of 32–48%)."))
rows = [["#", "Batter (last IPL team)", "Press. balls / inns", "Runs-balls-outs", "SR (exp.)", "Normal SR (exp.)", "Run val.", "Wkt val.", "Consist.", "Lift", "Impact"]]
for a in TB:
    rows.append([a["rank"], Paragraph(f"<b>{a['name']}</b> ({a['team']})", st["cell"]), f"{a['press_balls']} / {a['p_inns']}", f"{a['runs_p']}-{a['balls_p']}-{a['outs_p']}",
                 f"{a['sr_p']:.0f} ({a['xsr_p']:.0f})", f"{a['sr_n']:.0f} ({a['xsr_n']:.0f})", sg(a["run_value"]), sg(a["wicket_value"]), f"{a['consistency']:.0f}%", sg(a["lift"]), sg(a["impact"])])
s.append(table(rows, [6 * mm, 37 * mm, 16 * mm, 19 * mm, 14 * mm, 17 * mm, 12 * mm, 12 * mm, 12 * mm, 11 * mm, 12 * mm]))
s.append(P("SR (exp.) = actual pressure strike rate (context-expected strike rate for the same balls). Run/Wkt value and Lift in net runs per 100 pressure balls; Impact in win-probability points per 100 pressure balls vs league average.", "cap"))
s.append(img("07_bat_components", width=W * 0.86, cap="Figure 7. Why each batter ranks where they do. Abhishek, Tim David and Salt are driven by explosive run value; Kohli, Tilak and Shreyas by not getting out (wicket value); Powell by consistency; Klaasen by an all-round profile."))
s.append(img("09_bat_pressure_vs_normal", width=W * 0.82, cap="Figure 8. Pressure vs normal scoring. Players above the diagonal score further above expectation under pressure than they normally do (Powell, Klaasen, Tilak, Kohli); "
                                                              "players near the line simply carry elite skill into pressure (Abhishek, David, Suryakumar)."))
s.append(PageBreak())

# ======================= 6. RESULTS: BOWLERS =======================
s.append(P("6. Results — top 10 bowlers under pressure", "h1"))
s.append(img("06_bowl_ratings", width=W * 0.86, cap="Figure 9. Bowler ratings with 90% bootstrap intervals. The top four (Narine, Hazlewood, Varun, Mustafizur) are in the top 10 in 73–86% of resamples."))
rows = [["#", "Bowler (last IPL team)", "Press. balls / spells", "Runs-balls-wkts", "Econ (exp.)", "Normal econ (exp.)", "Run val.", "Wkt val.", "Consist.", "Lift", "Impact"]]
for a in TW:
    rows.append([a["rank"], Paragraph(f"<b>{a['name']}</b> ({a['team'] if a['team'] != 'Not in IPL data' else 'no IPL'})", st["cell"]), f"{a['press_balls']} / {a['p_inns']}",
                 f"{a['runs_p']}-{a['balls_p']}-{a['wkts_p']}", f"{a['econ_p']:.2f} ({a['xecon_p']:.2f})", f"{a['econ_n']:.2f} ({a['xecon_n']:.2f})",
                 sg(a["run_value"]), sg(a["wicket_value"]), f"{a['consistency']:.0f}%", sg(a["lift"]), sg(a["impact"])])
s.append(table(rows, [6 * mm, 37 * mm, 16 * mm, 19 * mm, 15 * mm, 17 * mm, 12 * mm, 12 * mm, 12 * mm, 10 * mm, 12 * mm]))
s.append(P("Econ (exp.) = actual pressure economy (context-expected economy on the same balls). Values per 100 pressure balls as for batters. Bowler consistency is heavily shrunk because the data shows it is mostly noise for bowlers.", "cap"))
s.append(img("08_bowl_components", width=W * 0.86, cap="Figure 10. Narine, Mustafizur and Bumrah win on run suppression; Hazlewood, Varun and Kuldeep add wicket-taking; Hasaranga and Varun show the largest positive pressure lift."))
s.append(img("10_bowl_pressure_vs_normal", width=W * 0.80, cap="Figure 11. Most of our top 10 save more runs per over under pressure than they normally do. Bumrah (6) is the exception that proves the method: elite in every situation, so his pressure figure is great but below his own normal."))
s.append(PageBreak())

# ======================= 7. PLAYER PROFILES =======================
s.append(P("7. Player profiles and how each strengthens RR", "h1"))
s.append(P("Numbers are on pressure balls only unless stated. 'Exp.' = context-expected value for the same balls. The RR angle draws on Section 8: RR's 2026 squad lacks a high-rated middle-order "
           "batter (Jurel #78, Jadeja #86, Hetmyer #88 of 101) and has no bowler in the top 30."))
BAT_NOTE = {
    "Abhishek Sharma": "Explosive left-handed opener: the highest pressure run value in the dataset; dismissals are the price of that tempo. Strongest in T20Is (+41 net runs/100 vs −16 in IPL), so the IPL edge comes from his skill level more than pressure-specific form. <b>RR fit:</b> very likely retained by SRH; if he ever reaches auction he is the top batting target.",
    "Suryakumar Yadav": "Largest pressure workload among the top 4 (632 balls) with positive value in both IPL (+21) and T20I (+43). Scores 20 above expected strike rate while staying in. <b>RR fit:</b> exactly the No. 3–4 pressure batter RR lacks; realistic only via trade or release.",
    "Tim David": "Finisher who keeps a 167 strike rate when the chase tightens (exp. 141), positive in both competitions. <b>RR fit:</b> overseas finishing slot; a direct upgrade on Hetmyer's pressure numbers (#88).",
    "Heinrich Klaasen": "Highest consistency in the top 4 (62%) and better under pressure than normal relative to expectation (+1.1 lift). IPL-heavy sample (338 IPL vs 42 T20I pressure balls). <b>RR fit:</b> overseas No. 4–5 who dominates spin in the middle overs.",
    "Shreyas Iyer": "Chase controller: positive wicket value (+2.7) plus +7.1 win impact; the Qualifier 2, IPL 2025 chase (Fig. 4) is typical. <b>RR fit:</b> Indian middle-order anchor with captaincy experience.",
    "Rovman Powell": "The most consistent batter in the top 10 (65%) and one of few who score clearly more above expectation under pressure (+19.6 SR) than normally (+3.3). <b>RR fit:</b> value overseas finisher who has played for RR before (2024); likely affordable at a mini-auction.",
    "Virat Kohli": "Only 9 dismissals in 289 pressure balls (average 47) — the best wicket value in the top 10 (+5.4). Scores near expectation, but never gives it away. <b>RR fit:</b> unrealistic acquisition; included because the data puts him here.",
    "Phil Salt": "Scores 20 above expected strike rate on pressure balls; the smallest sample in the top 10 (197 balls), so the widest interval. <b>RR fit:</b> overseas opener-keeper option if released.",
    "Namboori Tilak Varma": "The biggest pressure workload in the dataset (826 balls, 44 innings) and the highest win impact (+9.5 WP pts/100). Positive lift: he gets better relative to expectation when it's tight. <b>RR fit:</b> Indian left-handed No. 4.",
    "Nicholas Pooran": "Strong IPL pressure record (+27 net runs/100) as a keeper-finisher. <b>RR fit:</b> overseas keeper who could bat 5–6 and lift a weak death-overs batting group.",
}
BOWL_NOTE = {
    "Sunil Narine": "Concedes 6.0 an over on pressure balls where 7.6 is expected — the best run suppression of any spinner. IPL-only sample. <b>RR fit:</b> elite middle-overs control; now in his late 30s, so a short-term buy.",
    "Josh Hazlewood": "41 wickets in 464 pressure balls (one every 11 balls) with economy 1.25 below expected; best wicket value (+5.3). <b>RR fit:</b> new-ball and death seamer to pair with Archer (#31).",
    "Varun Chakravarthy": "Largest positive pressure lift among bowlers (+3.2): normal economy ≈ expected, but 1.0 below expected under pressure, with 38 wickets. <b>RR fit:</b> mystery spin for Jaipur's middle overs — the type RR lacks with Bishnoi rated #48.",
    "Mustafizur Rahman": "6.93 economy vs 8.32 expected over 575 pressure balls; cutters at the death. <b>Availability flag:</b> KKR released him on a BCCI instruction in Jan 2026, so his IPL 2027 availability is uncertain.",
    "Kuldeep Yadav": "Wicket-taking wrist spin (34 wickets) at 0.8 below expected economy; very strong T20I pressure record. <b>RR fit:</b> attacking left-arm wrist-spinner; would complement Bishnoi.",
    "Jasprit Bumrah": "Best run value of all bowlers (+20.7). His pressure figure is lower than his own extraordinary normal, so lift is negative — he is elite everywhere. <b>RR fit:</b> unrealistic acquisition (MI).",
    "Sufiyan Muqeem": "4.19 economy vs 6.66 expected in a small T20I-only sample (169 balls) — strong but the least certain in the top 10. <b>Availability flag:</b> Pakistan players are not part of the IPL auction pool.",
    "Wanindu Hasaranga": "48 pressure wickets with economy 0.6 below expected and positive lift (+3.0). Released by RR before 2026; in LSG's 2026 squad but with no IPL 2026 appearance in this data. <b>RR fit:</b> the clearest buy-back target if LSG release him — already proven in RR colours.",
    "Rashid Khan": "Heaviest pressure workload of any bowler (877 legal balls, 61 spells): 48 wickets at 0.75 below expected economy. <b>RR fit:</b> leg-spin + lower-order hitting; likely retained by GT.",
    "Bhuvneshwar Kumar": "Powerplay and death seamer: 36 wickets, economy 0.7 below expected on hard overs. <b>RR fit:</b> Indian seamer to share death overs with Archer and Sandeep Sharma (#89).",
}
def card(a, note, role):
    if role == "bat":
        line = f"{a['runs_p']} runs off {a['balls_p']} pressure balls · SR {a['sr_p']:.0f} (exp. {a['xsr_p']:.0f}) · avg {a['avg_p']:.1f} · IPL / T20I net runs per 100: {sg(a['nrv_ipl'],0)} / {sg(a['nrv_t20i'],0)}"
    else:
        line = f"{a['wkts_p']} wkts in {a['balls_p']} pressure balls · econ {a['econ_p']:.2f} (exp. {a['xecon_p']:.2f}) · dot {a['dot_p']:.0f}% · IPL / T20I net runs saved per 100: {sg(a['nrv_ipl'],0)} / {sg(a['nrv_t20i'],0)}"
    t = Table([[Paragraph(f"{a['rank']}. {a['name']} <font color='#4a4a46' size='8'>· rating {a['rating']:.1f} · top-10 in {a['p_top10']*100:.0f}% of resamples</font>", st["card_t"])],
               [Paragraph(f"<font color='#4a4a46'>{line}</font>", st["small"])], [Paragraph(note, st["card"])]], colWidths=[W])
    t.setStyle(TableStyle([("LINEBEFORE", (0, 0), (0, -1), 2.2, BLUE if role == "bat" else ORANGE), ("LEFTPADDING", (0, 0), (-1, -1), 7),
                           ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return KeepTogether([t, Spacer(1, 5)])
s.append(P("Batters", "h2"))
for a in TB: s.append(card(a, BAT_NOTE[a["name"]], "bat"))
s.append(P("Bowlers", "h2"))
for a in TW: s.append(card(a, BOWL_NOTE[a["name"]], "bowl"))

# ======================= 8. RR =======================
s.append(P("8. What this means for Rajasthan Royals", "h1"))
rb = S["rr_squad"]["Batting"]; rw = S["rr_squad"]["Bowling"]
s.append(P(f"We rated RR's IPL 2026 squad with the same model (Figure 12). Batting: the best eligible RR batter is {rb[0]['name']} (#{rb[0]['rank']}), then {rb[1]['name']} (#{rb[1]['rank']}); "
           f"the middle and lower order — the batters who most often face chase pressure — sit at #{rb[-3]['rank']}–#{rb[-1]['rank']}. "
           f"Bowling: {rw[0]['name']} (#{rw[0]['rank']}) and {rw[1]['name']} (#{rw[1]['rank']}) lead; no RR bowler is in the top 30, and two frontline seamers rank in the bottom 20."))
s.append(img("13_rr_gap", width=W * 0.9, cap="Figure 12. RR 2026 squad (eligible players) against our top-10 range. 50 = eligible average. Vaibhav Sooryavanshi's early pressure numbers are outstanding (rating 92 on 107 balls) but below our sample threshold, so he is not ranked."))
s.append(P("Auction priorities (in order)", "h2"))
s += B([
    "<b>1. A pressure-proof middle-order/finishing batter.</b> Biggest gap. Targets by likely availability: Rovman Powell (#6, previous RR player), Tim David (#3), Nicholas Pooran (#10), Phil Salt (#8); "
    "next tier: Shai Hope (#11), Ashutosh Sharma (#12), Josh Inglis (#13).",
    "<b>2. A wicket-taking spinner for the middle overs.</b> Wanindu Hasaranga (#8) is the standout buy-back; Varun (#3) and Kuldeep (#5) if they become available.",
    "<b>3. A death/new-ball seamer alongside Archer.</b> Josh Hazlewood (#2), Bhuvneshwar Kumar (#10); auction-realistic alternatives from just outside the top 10: Matheesha Pathirana (#11), Lockie Ferguson (#17).",
    "<b>Availability-adjusted bowling list:</b> if Muqeem (not in the IPL pool) and Mustafizur (BCCI-directed release in 2026) are set aside, the next two bowlers are Matheesha Pathirana (#11) and Krunal Pandya (#12).",
])
s.append(PageBreak())

# ======================= 9. RELIABILITY =======================
s.append(P("9. Reliability checks and limitations", "h1"))
s.append(P("9.1 Consistency across matches (bootstrap)", "h2"))
s.append(P("We resampled whole matches with replacement 400 times (keeping every ball of a match together, as matches are the natural unit of dependence) and recomputed every rating. "
           "This gives the 90% intervals in Figures 6 and 9 and the probability of each player finishing in the top 10 (Figure 13)."))
s.append(img("12_rank_stability", cap="Figure 13. Rank stability. The top four batters and top four bowlers make the top 10 in 73–89% of resamples; positions 5–10 are a tighter contest (32–53%)."))
s.append(P("9.2 Sensitivity to our modelling choices", "h2"))
rows = [["Variant", "Batters: overlap with our top 10", "Batters: Spearman ρ", "Bowlers: overlap with our top 10", "Bowlers: Spearman ρ"]]
for x, y in zip(S["sensitivity"]["bat"], S["sensitivity"]["bowl"]):
    rows.append([x["variant"], f"{x['overlap']} / 10", f"{x['rho']:.3f}", f"{y['overlap']} / 10", f"{y['rho']:.3f}"])
s.append(table(rows, [52 * mm, 32 * mm, 26 * mm, 34 * mm, 28 * mm]))
s.append(P("Rankings change very little under any reasonable alternative; the most sensitive choice is widening 'pressure' to the top 30% of balls, which brings more low-stakes balls in.", "cap"))
s.append(P("9.3 How repeatable is pressure performance?", "h2"))
s.append(P(f"Splitting the data into 2022–24 and 2025–26, the correlation of a player's raw pressure net run value between periods is r = {S['temporal']['bat']['raw']:.2f} for batters "
           f"(n = {S['temporal']['bat']['n']}) and r = {S['temporal']['bowl']['raw']:.2f} for bowlers (n = {S['temporal']['bowl']['n']}). Raw pressure averages are therefore poor predictors on their own — "
           "the main reason we anchor each estimate on the player's overall skill and only add a shrunk pressure-specific lift. Ranking on raw pressure strike rate or economy would "
           "mostly reward luck."))
s.append(P("9.4 Limitations — where the model is less certain", "h2"))
s += B([
    "<b>Small samples</b>: Phil Salt (197 balls), Sufiyan Muqeem (169) and young players are least certain; promising players under 120 pressure balls (e.g. Vaibhav Sooryavanshi) are rated but not ranked.",
    "<b>Coverage</b>: only IPL and the listed T20Is. Franchise leagues (BBL, SA20, The Hundred, CPL, ILT20) are absent, which under-samples some overseas specialists.",
    "<b>First-innings stakes</b>: win probability in the first innings is inherently uncertain (AUC 0.68), so first-innings pressure is defined by demand vs par rather than leverage.",
    "<b>Attribution</b>: credits go to striker and bowler; fielding, non-striker running and captaincy are not modelled. Run-outs are not credited to bowlers.",
    "<b>Role confounding</b>: finishers and death bowlers face more pressure balls. Context expectations remove most of this, but role still shapes exposure.",
    "<b>Judgement calls</b>: recency and opposition weights, the 25% threshold and component weights are choices — Section 9.2 shows the result is robust to them.",
    "<b>Availability</b>: retention decisions for 2027 were not final when this was written; player-specific availability notes are flagged in Section 7.",
])
s.append(P("10. Reproducibility", "h1"))
s.append(P("All code is included with the submission: <b>s1_prep_wp.py</b> (cleaning, win-probability, leverage, demand, expected-runs models), <b>s2_ratings.py</b> (ball credits, "
           "Bayesian estimates, composite, bootstrap, sensitivity via environment flags), <b>s3_charts.py</b> (figures and tables), <b>s4_report.py</b> (this PDF). "
           "Full leaderboards for all eligible players are in bat_leaderboard.csv and bowl_leaderboard.csv. Random seeds are fixed (match split 7, bootstrap 2027). Run order: s1 → s2 → s3 → s4."))
if DASH:
    s.append(P(f"<b>Interactive dashboard:</b> {DASH}", "body"))

doc.build(s)
print("ok")
