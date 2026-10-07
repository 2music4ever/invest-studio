"""Invest Studio — long-term investing workbench. Modeling & accumulation, not trading."""
import numpy as np
import pandas as pd
import streamlit as st

import charts
import data as D
import portfolio as PF
import technical as T
import valuation as V

st.set_page_config(page_title="Invest Studio", page_icon="assets/favicon.png", layout="wide")

# ---------- professional chrome: typography, theme, hide Streamlit branding ----------
CHROME_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stDeployButton {display: none;}
[data-testid="stToolbar"] {display: none;}
[data-testid="stStatusWidget"] {display: none;}
header[data-testid="stHeader"] {background: rgba(0,0,0,0);}

html, body, [class*="css"], .stApp {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
.block-container {padding-top: 1.4rem; max-width: 1220px;}

/* brand banner */
.is-banner {display: flex; align-items: center; gap: 16px; padding: 8px 2px 2px;}
.is-mark {width: 46px; height: 46px; border-radius: 12px; flex: 0 0 46px;
  background: linear-gradient(135deg, #E3BC63 0%, #C8A24B 55%, #8F6F2A 100%);
  color: #0B0E14; font-weight: 800; font-size: 19px; letter-spacing: 1px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 16px rgba(200,162,75,0.28);}
.is-title {font-size: 20px; font-weight: 700; letter-spacing: 3.5px; color: #F2F4F8; line-height: 1.1;}
.is-sub {font-size: 12.5px; color: #9AA4B2; margin-top: 4px;}
.is-rule {height: 1px; margin: 12px 0 4px;
  background: linear-gradient(90deg, #C8A24B 0%, rgba(200,162,75,0.18) 55%, transparent 100%);}

/* first-visit intro card */
.is-intro {background: #141926; border: 1px solid #232C42; border-left: 3px solid #C8A24B;
  border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #C6CDDB; margin: 8px 0 2px;}
.is-intro b {color: #E9ECF3; font-weight: 600;}

/* metric cards */
[data-testid="stMetric"] {background: #141926; border: 1px solid #232C42;
  border-radius: 10px; padding: 12px 16px;}
[data-testid="stMetricLabel"] {font-size: 10.5px; letter-spacing: 1.4px;
  text-transform: uppercase; color: #8B93A7;}
[data-testid="stMetricValue"] {font-size: 25px; font-weight: 600;}

/* tabs */
button[data-baseweb="tab"] {font-size: 12px; letter-spacing: 1.6px;
  text-transform: uppercase; color: #8B93A7; padding: 10px 16px;}
button[data-baseweb="tab"]:hover {color: #E9ECF3;}
button[data-baseweb="tab"][aria-selected="true"] {color: #E9ECF3; font-weight: 600;}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {background-color: #C8A24B;}

/* buttons */
.stButton > button {border-radius: 8px; border: 1px solid #C8A24B;
  color: #E3BC63; background: transparent; font-weight: 600;}
.stButton > button:hover {background: rgba(200,162,75,0.12); border-color: #E3BC63;}
.stDownloadButton > button {border: 1px solid #2A3348; color: #E9ECF3;
  background: #1A2130; font-weight: 500;}
.stDownloadButton > button:hover {border-color: #C8A24B; color: #E3BC63;}

/* sidebar + expanders + inputs */
[data-testid="stSidebar"] {background: #0D1119; border-right: 1px solid #1C2333;}
[data-testid="stExpander"] {border: 1px solid #232C42; border-radius: 10px; background: #11151F;}
[data-baseweb="input"], [data-baseweb="select"] {border-radius: 8px;}

h1, h2, h3 {letter-spacing: 0.2px;}
"""

st.markdown(f"<style>{CHROME_CSS}</style>", unsafe_allow_html=True)
st.markdown(
    '<div class="is-banner"><div class="is-mark">IS</div><div>'
    '<div class="is-title">INVEST STUDIO</div>'
    '<div class="is-sub">Long-term investing workbench — valuation modeling, '
    'accumulation footprints, entry planning</div></div></div>'
    '<div class="is-rule"></div>',
    unsafe_allow_html=True,
)
st.caption("For education and research only — not investment advice.")

if "intro_seen" not in st.session_state:
    st.session_state.intro_seen = False
if not st.session_state.intro_seen:
    st.markdown(
        '<div class="is-intro"><b>New here?</b> Enter a ticker below, then walk the deep dives in order: '
        "<b>Chart &amp; Trend</b> → <b>Valuation Lab</b> → "
        "<b>Accumulation</b> → <b>Dislocation</b> → <b>Entry Planner</b>. "
        "<b>One-Pager</b> summarizes the whole thesis on one screen. "
        "The <b>Portfolio</b> tab optimizes across many tickers at once "
        "(mean-variance, Sortino, min drawdown) with its own ticker list. "
        "Everything is assumption-driven — change the inputs and watch the outputs move. "
        "Built on free Yahoo Finance data: a starting point for your own research, not a verdict.</div>",
        unsafe_allow_html=True,
    )
    if st.button("Got it — hide this", key="intro_dismiss"):
        st.session_state.intro_seen = True
        st.rerun()


def fmt_money(x):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"${x:,.2f}"


def fmt_big(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if abs(x) >= div:
            return f"${x / div:,.1f}{unit}"
    return f"${x:,.0f}"


def fmt_pct(x, digits=1):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100:.{digits}f}%"


# ---------- ticker ----------
tcol, _ = st.columns([1, 2.4])
with tcol:
    ticker = st.text_input("Ticker", "MSFT").strip().upper()
st.caption("Data: Yahoo Finance (free). Estimates update intraday; fundamentals quarterly.")
period = "10y"  # single source of truth; chart zoom is controlled by the range pills

if not ticker:
    st.info("Enter a ticker to begin.")
    st.stop()

with st.spinner(f"Loading {ticker}…"):
    px = D.get_history(ticker, period)
    snap = D.get_snapshot(ticker)
    fund = D.get_fundamentals(ticker)

if px.empty or snap.get("price") is None:
    st.error(f"Could not load data for {ticker}. Check the ticker symbol.")
    st.stop()

price = float(snap["price"])
px = T.add_trend(px)
last = px.iloc[-1]
regime_text, regime_color = T.regime(price, last.get("WMA50", np.nan), last.get("WMA200", np.nan))

tabs = st.tabs(["Chart & Trend", "Valuation Lab", "Accumulation",
                "Dislocation", "Entry Planner", "Portfolio", "One-Pager"])

# ================= TAB 7 — ONE-PAGER =================
with tabs[6]:
    st.subheader("One-Pager — the whole thesis on one screen")
    st.caption("Snapshot summary for the ticker above. Valuations reuse your Valuation Lab "
               "defaults; the Strengths / Watch-outs are rule-based flags from the data, not analysis.")

    # ---- header ----
    chg = (px["Close"].iloc[-1] / px["Close"].iloc[-2] - 1) if len(px) > 1 else np.nan
    hi52 = float(px["High"].iloc[-252:].max())
    lo52 = float(px["Low"].iloc[-252:].min())
    st.markdown(f"## {snap['name']} ({ticker})")
    h1, h2, h3 = st.columns(3)
    h1.metric("Price", fmt_money(price),
              f"{chg * 100:+.2f}% today" if not np.isnan(chg) else None)
    h2.metric("52-week high", fmt_money(hi52), f"{(price / hi52 - 1) * 100:+.1f}% vs price")
    h3.metric("52-week low", fmt_money(lo52), f"{(price / lo52 - 1) * 100:+.1f}% vs price")

    # ---- TTM margins + 1y return ----
    fh_all = D.get_fundamentals_history(ticker)
    gross_m_ttm = fcf_m_ttm = rev_ttm = None
    if not fh_all.empty:
        ttm = fh_all[fh_all["kind"] == "TTM"]
        if not ttm.empty:
            r = ttm.iloc[-1]
            rev = r["revenue"]
            if pd.notna(rev) and rev:
                rev_ttm = rev
            if pd.notna(rev) and rev:
                if pd.notna(r["gross"]):
                    gross_m_ttm = r["gross"] / rev
                if pd.notna(r["fcf"]):
                    fcf_m_ttm = r["fcf"] / rev
    if fcf_m_ttm is None:
        fcf_m_ttm = fund["fcf_margin"]
    ret1y = (px["Close"].iloc[-1] / px["Close"].iloc[-252] - 1) if len(px) > 252 \
        else (px["Close"].iloc[-1] / px["Close"].iloc[0] - 1)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Price", fmt_money(price))
    m2.metric("Gross margin (TTM)", fmt_pct(gross_m_ttm))
    m3.metric("FCF margin (TTM)", fmt_pct(fcf_m_ttm))
    m4.metric("1-year return", fmt_pct(ret1y))

    # ---- price chart: 18 months + MAs ----
    st.markdown("### Price — last 18 months")
    st.plotly_chart(charts.onepager_ma_chart(px.iloc[-378:]), width="stretch")
    st.caption("White = close · teal = 21-day EMA · orange = 50-day SMA · blue = 200-day SMA. "
               "A series is omitted when it has no valid points in the window.")

    # ---- quarterly revenue & FCF ----
    st.markdown("### Revenue & FCF — quarterly")
    qdf = D.get_quarterly(ticker)
    qfig = charts.quarterly_bars(qdf)
    if qfig:
        st.plotly_chart(qfig, width="stretch")
        st.caption("Revenue and free cash flow (operating cash flow − capex) per fiscal quarter, in $B.")
    else:
        st.info("Quarterly statements unavailable for this ticker right now.")

    # ---- latest-quarter key metrics (computed once, reused by the rules) ----
    lq = qdf.iloc[-1] if not qdf.empty else None
    yoy = None
    if lq is not None and len(qdf) >= 5:
        base = qdf["revenue"].iloc[-5]
        if pd.notna(lq["revenue"]) and pd.notna(base) and base:
            yoy = lq["revenue"] / base - 1
    qgm = None
    if lq is not None and pd.notna(lq["gross"]) and pd.notna(lq["revenue"]) and lq["revenue"]:
        qgm = lq["gross"] / lq["revenue"]

    st.markdown("### Key metrics — latest quarter")
    if lq is not None:
        qlab = f"{lq.name.year}Q{((lq.name.month - 1) // 3) + 1}"
        kdf = pd.DataFrame([
            {"Metric": "Revenue", "Value": fmt_big(lq["revenue"])},
            {"Metric": "YoY revenue growth", "Value": fmt_pct(yoy)},
            {"Metric": "Gross margin", "Value": fmt_pct(qgm)},
            {"Metric": "FCF", "Value": fmt_big(lq["fcf"])},
            {"Metric": "Net cash", "Value": fmt_big(lq["net_cash"])},
        ])
        st.dataframe(kdf, width="stretch", hide_index=True)
        st.caption(f"Quarter ended {qlab}. Net cash = cash − total debt.")
    else:
        st.info("Quarterly data unavailable for this ticker right now.")

    # ---- peer comparison (hybrid: Finnhub auto-suggest, user-editable) ----
    st.markdown("### Peer comparison")
    auto = D.get_finnhub_peers(ticker)
    if auto["note"] == "no_key":
        st.caption("Tip: add a free Finnhub API key as FINNHUB_KEY in Streamlit secrets "
                   "(`.streamlit/secrets.toml` locally, or Settings → Secrets on Streamlit Cloud) "
                   "to auto-suggest peers. You can always type them below.")
    elif auto["note"] == "error":
        st.caption("Finnhub peer lookup failed — check the API key. Manual entry below still works.")
    peer_raw = st.text_input("Peers (comma-separated, up to 5)",
                             value=", ".join(auto["peers"][:5]),
                             key=f"op_peers_{ticker}")
    peer_list = [p.strip().upper() for p in peer_raw.split(",") if p.strip()][:5]
    universe = [ticker] + [p for p in peer_list if p != ticker]
    prows = []
    for t in universe[:6]:
        try:
            s = D.get_snapshot(t)
            if not s.get("price"):
                continue
            prows.append({"Ticker": t, "Price": s["price"],
                          "Forward P/E": s.get("forward_pe"),
                          "Gross margin TTM": s.get("gross_margin"),
                          "Market cap": s.get("market_cap")})
        except Exception:
            continue  # one bad peer never breaks the table
    if prows:
        pdf = pd.DataFrame(prows)
        pdf["Price"] = pdf["Price"].map(lambda x: f"${x:,.2f}" if pd.notna(x) else "n/a")
        pdf["Market cap"] = pdf["Market cap"].map(fmt_big)
        is_subj = (pdf["Ticker"] == ticker).to_numpy()
        sty = (pdf.style
               .format({"Forward P/E": "{:.1f}", "Gross margin TTM": "{:.1%}"}, na_rep="n/a")
               .apply(lambda _: ["background-color: rgba(200,162,75,0.16); font-weight: 600"
                                 if f else "" for f in is_subj], axis=0))
        st.dataframe(sty, width="stretch", hide_index=True)
        st.caption("Peers auto-suggested by Finnhub when a key is set; edit the list above any time. "
                   "The highlighted row is your ticker.")
    else:
        st.info("No peer data loaded — check the ticker symbols above.")

    # ---- rule-based strengths / watch-outs ----
    st.markdown("### Strengths / watch-outs")
    st.caption("Auto-generated from the data — threshold flags, not analysis.")
    strengths, watch = [], []
    if lq is not None and pd.notna(lq["net_cash"]):
        if lq["net_cash"] > 0:
            strengths.append(f"Net-cash balance sheet ({fmt_big(lq['net_cash'])} cash over debt)")
        else:
            watch.append(f"Net debt of {fmt_big(-lq['net_cash'])} — leverage to watch")
    if fcf_m_ttm is not None and fcf_m_ttm > 0.40:
        watch.append(f"Peak-cycle FCF margin ({fmt_pct(fcf_m_ttm)}) — normalize before extrapolating")
    elif fcf_m_ttm is not None and fcf_m_ttm > 0.15:
        strengths.append(f"Strong cash conversion ({fmt_pct(fcf_m_ttm)} FCF margin TTM)")
    tpe, fpe = snap.get("trailing_pe"), snap.get("forward_pe")
    if tpe and fpe and tpe > 0 and fpe > 0 and fpe < tpe:
        watch.append("Forward P/E below trailing — the market prices current earnings as temporary")
    if yoy is not None:
        if yoy > 0.50:
            strengths.append(f"Hypergrowth quarter ({fmt_pct(yoy)} YoY revenue)")
        elif yoy < 0:
            watch.append(f"Revenue declining YoY ({fmt_pct(yoy)})")
    if gross_m_ttm is not None and gross_m_ttm > 0.60:
        strengths.append(f"Pricing power ({fmt_pct(gross_m_ttm)} gross margin TTM)")
    if not np.isnan(ret1y) and ret1y > 1.0:
        watch.append(f"Up {fmt_pct(ret1y)} in a year — momentum is priced in; size accordingly")
    ma200 = px["Close"].rolling(200).mean().iloc[-1]
    if pd.notna(ma200):
        if price > ma200:
            strengths.append("Uptrend — price above the 200-day moving average")
        else:
            watch.append("Downtrend — price below the 200-day moving average")
    sc1, sc2 = st.columns(2)
    with sc1:
        st.markdown("**Strengths**")
        for s in strengths or ["—"]:
            st.markdown(f":green[+] {s}")
    with sc2:
        st.markdown("**Watch-outs**")
        for w in watch or ["—"]:
            st.markdown(f":red[−] {w}")

    # ---- valuation trio (TTM inputs; growth/discount/terminal match the Valuation Lab) ----
    st.markdown("### Valuation trio")
    rev0 = rev_ttm or fund["revenue"]
    shares0 = fund["shares"]
    fcf_m0 = fcf_m_ttm if fcf_m_ttm is not None else (fund["fcf_margin"] or 0.15)
    nd0 = (-lq["net_cash"] if (lq is not None and pd.notna(lq["net_cash"]))
           else (fund["net_debt"] or 0))
    v1, v2, v3 = st.columns(3)
    if rev0 and shares0:
        cons = D.get_consensus_growth(ticker)
        g1d, g2d = cons["g_early"], cons["g_late"]
        try:
            iv, ev, _ = V.dcf(rev0, g1d, g2d, fcf_m0, 0.09, 0.025, nd0, shares0)
            mos = V.margin_of_safety(iv, price)
            v1.metric("DCF fair value", fmt_money(iv),
                      f"{mos * 100:+.1f}% vs price" if mos is not None else None)
            v1.markdown(f"**{V.mos_label(mos)}**")
            with v1.expander("Assumptions"):
                st.markdown(
                    f"- Revenue (TTM): {fmt_big(rev0)}\n"
                    f"- FCF margin (TTM): {fcf_m0 * 100:.1f}%\n"
                    f"- Growth yrs 1–5 / 6–10: {g1d * 100:.1f}% / {g2d * 100:.1f}% "
                    f"({cons['early_src']}/{cons['late_src']})\n"
                    f"- Discount 9.0%, terminal growth 2.5%\n"
                    f"- Net debt {fmt_big(nd0)}, shares {shares0 / 1e6:,.0f}M")
        except (ValueError, TypeError, ZeroDivisionError):
            v1.metric("DCF fair value", "n/a")
            v1.caption("Could not value with these inputs.")
        implied = V.reverse_dcf(price, rev0, fcf_m0, 0.09, 0.025, nd0, shares0)
        if implied is None:
            v2.metric("Implied 10-yr growth", "n/a")
            v2.caption("Price implies growth outside −5%…+40% — expectations look extreme.")
        else:
            ach = ("Easy" if implied < 0.08 else "Doable" if implied < 0.15
                   else "Demanding" if implied < 0.25 else "Heroic")
            v2.metric("Implied 10-yr growth", f"{implied * 100:.1f}%")
            v2.markdown(f"**Achievability: {ach}**")
            v2.caption("Uniform annual revenue growth the price implies, at the DCF card's "
                       "margin/discount assumptions.")
    else:
        v1.metric("DCF fair value", "n/a")
        v2.metric("Implied 10-yr growth", "n/a")
        v1.caption("Insufficient data — revenue or shares missing.")
    v3.markdown("**Mid-cycle exit**")
    mc_rev = v3.number_input("Mid-cycle revenue ($M)",
                             value=(rev0 / 1e6 if rev0 else 0.0),
                             key=f"op_mc_rev_{ticker}", format="%.0f")
    mc_nm = v3.number_input("Mid-cycle net margin %",
                            value=((fund["net_margin"] or 0.20) * 100),
                            key=f"op_mc_nm_{ticker}", step=1.0) / 100
    mc_pe = v3.number_input("Exit P/E", value=15.0,
                            key=f"op_mc_pe_{ticker}", step=1.0)
    mc_sh = v3.number_input("Shares (M)",
                            value=(shares0 / 1e6 if shares0 else 0.0),
                            key=f"op_mc_sh_{ticker}", format="%.0f")
    if mc_rev > 0 and mc_sh > 0 and mc_pe > 0:
        mc_eps = mc_rev * 1e6 * mc_nm / (mc_sh * 1e6)
        mc_iv = mc_eps * mc_pe
        v3.metric("Exit-implied value", fmt_money(mc_iv),
                  f"{(mc_iv / price - 1) * 100:+.1f}%")
        v3.caption(f"Mid-cycle EPS {fmt_money(mc_eps)} × {mc_pe:.0f}x. The cyclical "
                   "cross-check: where the DCF sees growth, this sees the cycle.")
    else:
        v3.metric("Exit-implied value", "n/a")

# ================= TAB 1 — CHART & TREND =================
with tabs[0]:
    st.subheader(f"{snap['name']} ({ticker})")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Price", fmt_money(price))
    c2.metric("Market cap", fmt_big(snap["market_cap"]))
    c3.metric("Trailing P/E", f"{snap['trailing_pe']:.1f}" if snap["trailing_pe"] else "n/a")
    c4.metric("Forward P/E", f"{snap['forward_pe']:.1f}" if snap["forward_pe"] else "n/a")
    c5.metric("PEG", f"{snap['peg']:.2f}" if snap["peg"] else "n/a")
    rng = st.pills("Chart range", ["3M", "6M", "YTD", "1Y", "3Y", "5Y", "10Y"],
                   default="3Y", key="chart_rng")
    _days = {"3M": 63, "6M": 126, "1Y": 252, "3Y": 756, "5Y": 1260, "10Y": 2520}
    naive_idx = px.index.tz_localize(None)
    if rng in (None, "10Y"):
        cdf = px
    elif rng == "YTD":
        start = pd.Timestamp(year=naive_idx[-1].year, month=1, day=1)
        cdf = px[naive_idx >= start]
    else:
        cdf = px.iloc[-_days[rng]:]
    flags = [f for f in T.wyckoff_flags(px) if f["date"] >= cdf.index[0]]
    st.plotly_chart(charts.price_chart(cdf), width="stretch")

    st.markdown("### Trend readout")
    ro = T.trend_readout(px)
    st.markdown(f"**Regime:** {ro['regime']}")
    for b in ro["bullets"]:
        st.markdown(f"- {b}")

    st.markdown("### Wyckoff-style structure flags (heuristic)")
    if flags:
        fdf = pd.DataFrame([{"Date": f["date"].strftime("%Y-%m-%d"),
                             "Signal": f["type"], "Reading": f["note"]}
                            for f in flags])
        st.dataframe(fdf, width="stretch", hide_index=True)
        st.caption("Rule-based sketches from price/volume — spring = wick below the 60-day low "
                   "that closes back inside; breakout = close above the 60-day high on 1.5× volume; "
                   "test = narrow day holding above the spring low. Educational, not confirmed analysis.")
    else:
        st.caption("No structure flags in this range.")

    st.markdown("### Historical P/E zones")
    pe = D.get_ttm_pe(ticker, px["Close"])
    fwd_pe = snap.get("forward_pe")
    fig = charts.valuation_bands(pe)
    if fig:
        st.plotly_chart(fig, width="stretch")
        cur_pe = pe["pe"].iloc[-1]
        cap = (f"Trailing P/E **{cur_pe:.1f}**. The line is colored by where each point "
               f"sat relative to its own history up to that date — teal = bottom 10%, "
               f"red = top 10%. Relative to past P/E only, not a cheap/expensive call. ")
        if fwd_pe:
            cap += (f"Current forward P/E **{fwd_pe:.1f}** (Yahoo) — where the "
                    "market prices next-12-month earnings vs the trailing history. ")
        cap += ("Zones are trailing only: free data has no historical forward-estimate series. "
                "Built from annual EPS (yearly points) plus recent TTM EPS (weekly).")
        st.caption(cap)
    else:
        st.info("Not enough quarterly history to build P/E bands for this ticker.")

    with st.expander("Key stats"):
        rows = [("Sector", snap["sector"]), ("Industry", snap["industry"]),
                ("Beta", f"{snap['beta']:.2f}" if snap["beta"] else "n/a"),
                ("Profit margin", fmt_pct(snap["profit_margin"])),
                ("Operating margin", fmt_pct(snap["op_margin"])),
                ("ROE", fmt_pct(snap["roe"])),
                ("P/S", f"{snap['ps']:.1f}" if snap["ps"] else "n/a"),
                ("P/B", f"{snap['pb']:.1f}" if snap["pb"] else "n/a"),
                ("EV/EBITDA", f"{snap['ev_ebitda']:.1f}" if snap["ev_ebitda"] else "n/a"),
                ("Dividend yield", fmt_pct(snap["div_yield"], 2)),
                ("Free cash flow (TTM)", fmt_big(snap["fcf"]))]
        st.table(pd.DataFrame(rows, columns=["Metric", "Value"]))

    st.markdown("### Fundamental trends")
    fh = D.get_fundamentals_history(ticker)
    if fh.empty or len(fh) < 2:
        st.info("Not enough statement history to chart fundamentals for this ticker.")
    else:
        fh = fh.copy()
        pxc = px["Close"]
        pidx = pxc.index.tz_localize(None) if getattr(pxc.index, "tz", None) is not None else pxc.index
        pxc = pd.Series(pxc.to_numpy(), index=pidx).sort_index()
        fh["price"] = [float(pxc.iloc[-1]) if k == "TTM"
                       else (float(pxc.loc[:d].iloc[-1]) if not pxc.loc[:d].empty else np.nan)
                       for d, k in zip(fh.index, fh["kind"])]
        for m, num in (("gross_m", "gross"), ("op_m", "opinc"),
                       ("net_m", "netinc"), ("fcf_m", "fcf")):
            fh[m] = fh[num] / fh["revenue"]
        fh["label"] = ["TTM" if k == "TTM" else str(d.year)
                       for d, k in zip(fh.index, fh["kind"])]
        FMETS = {"revenue": ("Revenue", "$B"), "gross": ("Gross profit", "$B"),
                 "opinc": ("Operating income", "$B"), "netinc": ("Net income", "$B"),
                 "fcf": ("Free cash flow", "$B"), "eps": ("Diluted EPS", "$"),
                 "gross_m": ("Gross margin", "%"), "op_m": ("Operating margin", "%"),
                 "net_m": ("Net margin", "%"), "fcf_m": ("FCF margin", "%"),
                 "price": ("Stock price (period-end)", "$")}
        avail = [k for k in FMETS if fh[k].notna().sum() >= 2]
        mc = st.columns(2)
        akey = mc[0].selectbox("Metric — bars, left axis", avail,
                               format_func=lambda k: FMETS[k][0],
                               index=avail.index("revenue") if "revenue" in avail else 0,
                               key="fm_a")
        bopts = ["none"] + avail
        bkey = mc[1].selectbox("Compare with — line, right axis", bopts,
                               format_func=lambda k: "None" if k == "none" else FMETS[k][0],
                               index=bopts.index("price") if "price" in avail else 0,
                               key="fm_b")
        st.plotly_chart(charts.fundamentals_chart(
            fh, akey, None if bkey == "none" else bkey, FMETS), width="stretch")
        st.caption("Annual fiscal statements plus a current TTM point — the full history "
                   "Yahoo's free tier carries (about 4 years). Margins are period ratios; "
                   "price is the period-end close (TTM pairs with the latest close).")

# ================= TAB 2 — VALUATION LAB =================
with tabs[1]:
    st.subheader("DCF valuation — your assumptions drive the value")
    rev0 = fund["revenue"]
    shares0 = fund["shares"]
    if not rev0 or not shares0:
        st.error("Yahoo didn't return revenue or shares outstanding — it's likely "
                 "rate-limiting right now. Your assumptions can't be valued without them, "
                 "so nothing below is computed on bad data.")
        if st.button("Retry loading data", key="retry_fund"):
            st.cache_data.clear()
            st.rerun()
        st.stop()
    st.caption(f"Loaded from Yahoo: revenue **{fmt_big(rev0)}** · **{shares0 / 1e9:.2f}B** shares · "
               f"net debt **{fmt_big(fund['net_debt'])}** · FCF margin "
               f"**{fmt_pct(fund['fcf_margin'])}**. Every number below is editable — the value is yours.")
    c = st.columns(4)
    revenue = c[0].number_input("Revenue (TTM, $M)", value=rev0 / 1e6, format="%.0f") * 1e6
    fcf_m = c[1].number_input("FCF margin %", value=(fund["fcf_margin"] or 0.15) * 100,
                              step=0.5) / 100
    disc = c[2].number_input("Discount rate %", value=9.0, step=0.25) / 100
    tg = c[3].number_input("Terminal growth %", value=2.5, step=0.25) / 100
    c = st.columns(4)
    cons = D.get_consensus_growth(ticker)
    g1 = c[0].number_input("Revenue growth yrs 1–5 %", value=cons["g_early"] * 100, step=0.5) / 100
    g2 = c[1].number_input("Revenue growth yrs 6–10 %", value=cons["g_late"] * 100, step=0.5) / 100
    net_debt = c[2].number_input("Net debt ($M)", value=(fund["net_debt"] or 0) / 1e6,
                                 format="%.0f") * 1e6
    shares = c[3].number_input("Shares out (M)", value=shares0 / 1e6,
                               format="%.0f") * 1e6
    c = st.columns(4)
    norm_on = c[0].checkbox("Normalize FCF margin", value=False,
                            help="Glide from today's FCF margin to a mid-cycle margin over N years — "
                                 "for companies in a peak-capex phase. The terminal value then reflects "
                                 "normalized earning power, not today's depressed margin.")
    norm_m = c[1].number_input("Normalized FCF margin %", value=(fund["fcf_margin"] or 0.15) * 100,
                              step=0.5, disabled=not norm_on) / 100
    norm_yrs = int(c[2].number_input("Normalize over (yrs)", value=5, min_value=1, max_value=10,
                                    step=1, disabled=not norm_on))
    fcf_norm = norm_m if norm_on else None

    if cons["early_src"] == "consensus" or cons["late_src"] == "consensus":
        bits = []
        if cons["early_src"] == "consensus":
            bits.append(f"yrs 1–5: **{cons['g_early'] * 100:.0f}%** (+1y consensus revenue growth)")
        if cons["late_src"] == "consensus":
            bits.append(f"yrs 6–10: **{cons['g_late'] * 100:.1f}%** (consensus long-term growth)")
        st.caption("Growth prefilled from Yahoo consensus — " + ", ".join(bits) + ". Still fully editable.")

    def _mcell(m, mn):
        s = f"{m * 100:.1f}%"
        return s + (f" → {mn * 100:.1f}% over {norm_yrs}y" if norm_on else "")

    try:
        iv, ev, sched = V.dcf(revenue, g1, g2, fcf_m, disc, tg, net_debt, shares,
                              fcf_margin_norm=fcf_norm, norm_years=norm_yrs)
        mos = V.margin_of_safety(iv, price)
        st.session_state["base_iv"] = iv
        g1c, g2c = st.columns([1, 2])
        with g1c:
            st.plotly_chart(charts.mos_gauge(mos, iv, price), width="stretch")
            st.markdown(f"**Verdict:** {V.mos_label(mos)}")
            st.caption(f"Valued with your inputs: revenue **{fmt_big(revenue)}** · FCF margin "
                       f"**{fcf_m * 100:.1f}%**"
                       + (f" → **{fcf_norm * 100:.1f}%** normalized over {norm_yrs}y" if norm_on else "")
                       + f" · growth **{g1 * 100:.1f}% / {g2 * 100:.1f}%** · "
                       f"discount **{disc * 100:.2f}%** · terminal **{tg * 100:.2f}%** · net debt "
                       f"**{fmt_big(net_debt)}** · **{shares / 1e6:,.0f}M** shares → "
                       f"**${iv:,.2f}**/share.")
        with g2c:
            scen = pd.DataFrame([
                {"Scenario": "Bear", **dict(zip(("IV",),
                    [V.dcf(revenue, max(g1 - 0.05, -0.02), max(g2 - 0.03, 0), max(fcf_m - 0.02, 0.01),
                               disc + 0.01, tg, net_debt, shares,
                               fcf_margin_norm=(max(fcf_norm - 0.02, 0.01) if norm_on else None),
                               norm_years=norm_yrs)[0]]))},
                {"Scenario": "Base", "IV": iv},
                {"Scenario": "Bull", "IV": V.dcf(revenue, g1 + 0.05, g2 + 0.03, fcf_m + 0.02,
                                                 max(disc - 0.01, tg + 0.005), tg, net_debt, shares,
                                                 fcf_margin_norm=(fcf_norm + 0.02 if norm_on else None),
                                                 norm_years=norm_yrs)[0]},
            ])
            st.plotly_chart(charts.scenario_bars(scen, price), width="stretch")
            with st.expander("Where do bear / base / bull come from?"):
                st.table(pd.DataFrame([
                    {"Scenario": "Bear",
                     "Growth yrs 1–5": f"{max(g1 - 0.05, -0.02) * 100:.1f}%",
                     "Growth yrs 6–10": f"{max(g2 - 0.03, 0) * 100:.1f}%",
                     "FCF margin": _mcell(max(fcf_m - 0.02, 0.01),
                                          max(fcf_norm - 0.02, 0.01) if norm_on else 0),
                     "Discount": f"{(disc + 0.01) * 100:.2f}%"},
                    {"Scenario": "Base — your inputs above",
                     "Growth yrs 1–5": f"{g1 * 100:.1f}%",
                     "Growth yrs 6–10": f"{g2 * 100:.1f}%",
                     "FCF margin": _mcell(fcf_m, fcf_norm if norm_on else 0),
                     "Discount": f"{disc * 100:.2f}%"},
                    {"Scenario": "Bull",
                     "Growth yrs 1–5": f"{(g1 + 0.05) * 100:.1f}%",
                     "Growth yrs 6–10": f"{(g2 + 0.03) * 100:.1f}%",
                     "FCF margin": _mcell(fcf_m + 0.02, fcf_norm + 0.02 if norm_on else 0),
                     "Discount": f"{max(disc - 0.01, tg + 0.005) * 100:.2f}%"},
                ]))
                st.caption("Bear/base/bull are fixed sensitivity offsets around *your* base inputs — "
                           "±5pp growth, ±2pp margin, ±1pp discount rate. Terminal growth and share count stay constant.")

        st.markdown("### Reverse DCF — what growth is already priced in?")
        implied = V.reverse_dcf(price, revenue, fcf_m, disc, tg, net_debt, shares,
                                  fcf_margin_norm=fcf_norm, norm_years=norm_yrs)
        if implied is None:
            st.info("Current price implies growth outside a sane −5%…+40% range — "
                    "expectations are either euphoric or deeply pessimistic.")
        else:
            # Apples-to-apples: compare the implied flat 10-yr rate against the
            # base case's own 10-yr equivalent (geometric mean of g1 x5, g2 x5).
            g_base_equiv = (1 + g1) ** 0.5 * (1 + g2) ** 0.5 - 1
            st.markdown(f"The current price of **{fmt_money(price)}** implies **{implied * 100:.1f}%** "
                        f"annual revenue growth for 10 years at your margin/discount assumptions. "
                        f"Your base case ({g1 * 100:.0f}%/then {g2 * 100:.0f}%) works out to "
                        f"**{g_base_equiv * 100:.1f}%** annualized over 10 years — "
                        + ("the market is pricing in more growth than you expect." if implied > g_base_equiv
                           else "the market is pricing in less growth than you expect."))

        with st.expander("Year-by-year DCF schedule"):
            show = sched.copy()
            for col in ("Revenue", "FCF", "PV of FCF"):
                show[col] = show[col] / 1e6
            st.dataframe(show.style.format({"Revenue": "{:,.0f}", "FCF": "{:,.0f}",
                                            "PV of FCF": "{:,.0f}", "FCF margin": "{:.1%}"}),
                         width="stretch")
            st.caption("Figures in $M.")

        st.markdown("### Expected return bridge — where the return comes from")
        bb = D.get_buyback_yield(ticker)
        pe_hist = D.get_ttm_pe(ticker, px["Close"])
        pe_now = snap.get("trailing_pe")
        pe_med = float(pe_hist["pe"].median()) if not pe_hist.empty else None
        bc = st.columns(5)
        div_d = bc[0].number_input("Dividend yield %", value=float((snap.get("div_yield") or 0) * 100),
                                  step=0.05) / 100
        bb_d = bc[1].number_input("Buyback yield %", value=bb["yield"] * 100, step=0.05) / 100
        g_d = bc[2].number_input("Earnings growth %", value=g1 * 100, step=0.5) / 100
        pe_t = bc[3].number_input("Target P/E", value=round(pe_med, 1) if pe_med else (pe_now or 20.0),
                                 step=0.5)
        yrs = int(bc[4].number_input("Horizon (yrs)", value=5, min_value=1, max_value=10, step=1))
        rerate = (pe_t / pe_now) ** (1 / yrs) - 1 if (pe_now and pe_t > 0) else 0.0
        total_a = div_d + bb_d + g_d + rerate
        total_n = (1 + total_a) ** yrs - 1
        st.plotly_chart(charts.bridge_chart(
            [("Dividends", div_d), ("Buybacks", bb_d),
             ("Earnings growth", g_d), ("Multiple re-rating", rerate)], total_a),
            width="stretch")
        st.markdown(f"**Expected return: {total_a * 100:.1f}%/yr** "
                    f"({total_n * 100:+.0f}% over {yrs}y).")
        bcap = ("Annualized: dividend yield + buyback yield + earnings growth + "
                "multiple re-rating, where re-rating = (target P/E ÷ current P/E)^(1/yrs) − 1. ")
        if bb["amount"]:
            bcap += (f"Buyback yield from {bb['year']} repurchases ({fmt_big(bb['amount'])}) ÷ market cap. ")
        if pe_med:
            bcap += f"Target P/E defaults to the historical median ({pe_med:.1f})."
        st.caption(bcap)

        st.markdown("### Quality check — is it a compounder?")
        q = D.get_quality(ticker)
        if q["f_max"]:
            qc1, qc2 = st.columns([1, 2])
            with qc1:
                st.metric("Piotroski F-score", f"{q['f_score']}/{q['f_max']}")
                s = q["f_score"]
                st.markdown(f"**{'Strong' if s >= 7 else 'Average' if s >= 4 else 'Weak'}**")
                st.caption("9-point financial-strength score comparing the latest annual "
                           "to the prior one: 7–9 strong, 4–6 average, 0–3 weak.")
            with qc2:
                st.table(pd.DataFrame([{"Check": c, "Pass": "✓" if p else "✗"}
                                       for c, p in q["f_detail"]]))
        else:
            st.info("Not enough statement history to score quality for this ticker.")
        if not q["roic"].empty:
            st.plotly_chart(charts.roic_chart(q["roic"]), width="stretch")
            st.caption("Return on invested capital = EBIT × (1 − tax) / invested capital.")

        st.markdown("### Growth valuation — VC / exit-multiple method")
        st.caption("For unprofitable growers: project revenue to a horizon year, apply a mature "
                   "EV/Sales multiple, discount back at a hurdle rate. A cross-check for the DCF — "
                   "not a replacement for profitable companies.")
        gc = D.get_consensus_growth(ticker)
        v1 = st.columns(4)
        rev0 = v1[0].number_input("VC current revenue ($M)",
                                 value=fund["revenue"] / 1e6 if fund.get("revenue") else 0.0,
                                 step=10.0, format="%.1f")
        gvc = v1[1].number_input("VC revenue CAGR %", value=gc["g_early"] * 100, step=5.0) / 100
        nvc = int(v1[2].number_input("VC horizon (yrs)", value=5, min_value=1, max_value=15, step=1))
        mult = v1[3].number_input("VC exit EV/Sales", value=8.0, step=0.5)
        v2 = st.columns(3)
        hurdle = v2[0].number_input("VC hurdle rate %", value=15.0, step=0.5) / 100
        ndvc = v2[1].number_input("VC net debt ($M)",
                                 value=fund["net_debt"] / 1e6 if fund.get("net_debt") else 0.0,
                                 step=10.0, format="%.1f")
        shvc = v2[2].number_input("VC shares (M)",
                                 value=fund["shares"] / 1e6 if fund.get("shares") else 0.0,
                                 step=10.0, format="%.1f")

        def _vcv(gg, mm):
            if rev0 <= 0 or shvc <= 0 or mm <= 0 or (1 + hurdle) <= 0:
                return None
            fut_rev = rev0 * (1 + gg) ** nvc
            pv_ev = fut_rev * mm / (1 + hurdle) ** nvc
            return (pv_ev - ndvc) / shvc

        vcv = _vcv(gvc, mult)
        if vcv is not None:
            fut_rev = rev0 * (1 + gvc) ** nvc
            pv_ev = fut_rev * mult / (1 + hurdle) ** nvc
            c1, c2 = st.columns(2)
            c1.metric("VC-implied value", fmt_money(vcv), f"{vcv / price - 1:+.1%} vs price")
            need = (price * shvc + ndvc) * (1 + hurdle) ** nvc / mult
            impl_g = (need / rev0) ** (1 / nvc) - 1 if need > 0 else None
            c2.metric("Revenue CAGR priced in", f"{impl_g * 100:.0f}%" if impl_g is not None else "n/a",
                      "at this exit multiple & hurdle" if impl_g is not None else None)
            st.caption(f"Year-{nvc} revenue {fmt_big(fut_rev * 1e6)} → future EV "
                       f"{fmt_big(fut_rev * mult * 1e6)} at {mult:.1f}x sales → PV "
                       f"{fmt_big(pv_ev * 1e6)} at {hurdle * 100:.0f}% hurdle → equity "
                       f"{fmt_big((pv_ev - ndvc) * 1e6)} after net debt → {fmt_money(vcv)}/sh "
                       f"on {shvc:,.0f}M shares.")
            st.markdown("**Sensitivity — per-share value across growth × exit multiple**")
            g_vals = [max(0.0, gvc + d) for d in (-0.20, -0.10, 0.0, 0.10, 0.20)]
            m_vals = [max(0.5, mult + d) for d in (-4.0, -2.0, 0.0, 2.0, 4.0)]
            grid = pd.DataFrame(
                [[_vcv(gg, mm) for mm in m_vals] for gg in g_vals],
                index=[f"{gg * 100:.0f}% CAGR" for gg in g_vals],
                columns=[f"{mm:.0f}x sales" for mm in m_vals])
            st.plotly_chart(charts.sensitivity_heatmap(grid, price), width="stretch")
            st.caption("Ignores future dilution and the cash burn to get there — treat this as the "
                       "destination value, then haircut for the journey.")
        else:
            st.info("Enter current revenue and shares to run the growth valuation.")
    except ValueError as e:
        st.error(str(e))

# ================= TAB 3 — ACCUMULATION =================
with tabs[2]:
    st.subheader("Institutional footprint")
    prof = T.vpvr(px)
    poc = float(prof["poc"].iloc[0])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Volume profile (VPVR)**")
        st.plotly_chart(charts.vpvr_chart(prof, price), width="stretch")
    with c2:
        st.markdown("**Accumulation / distribution + money flow**")
        d = px.copy()
        d["AD"] = T.accumulation_distribution(px)
        d["CMF20"] = T.cmf(px, 20)
        d["CMF60"] = T.cmf(px, 60)
        st.plotly_chart(charts.flow_chart(d), width="stretch")
    st.caption("Tallest VPVR bars mark institutional support zones. "
               "A rising A/D line while price consolidates = demand absorbing supply.")
    cmf60_now = float(d["CMF60"].iloc[-1]) if d["CMF60"].notna().any() else None
    ad_trend = "rising" if d["AD"].iloc[-1] > d["AD"].iloc[-63] else "falling"
    st.markdown(f"**Point of control (heaviest volume):** {fmt_money(poc)} — "
                f"{'below' if poc < price else 'above'} current price. "
                f"**A/D line** is {ad_trend} over 3 months. "
                f"**CMF(60):** {cmf60_now:+.2f}" if cmf60_now is not None else "" +
                " — sustained positive = quiet accumulation.")

# ================= TAB 4 — DISLOCATION =================
with tabs[3]:
    st.subheader("Estimates vs price — the dislocation tracker")
    an = D.get_analyst(ticker)
    tgt = an.get("analyst_price_targets")
    if isinstance(tgt, dict) and tgt.get("mean"):
        c1, c2 = st.columns(2)
        c1.metric("Consensus target", fmt_money(tgt.get("mean")),
                  f"{(tgt['mean'] / price - 1) * 100:+.1f}% vs price" if price else None)
        c2.metric("Analysts", tgt.get("numberOfAnalysts") or "n/a")
        if tgt.get("low") and tgt.get("high"):
            st.plotly_chart(charts.target_range(tgt["low"], tgt["mean"],
                                                tgt["high"], price),
                            width="stretch")
    else:
        st.info("No analyst price targets available for this ticker right now — "
                "Yahoo may be rate-limiting. (Google Finance blocks automated access, "
                "so the app can't pull its Analysis tab directly.)")
        if st.button("Retry analyst data", key="retry_an"):
            st.cache_data.clear()
            st.rerun()

    et = an.get("eps_trend")
    er = an.get("eps_revisions")
    drift_0q = breadth_0q = None
    if isinstance(et, pd.DataFrame) and not et.empty and "0q" in et.index:
        r = et.loc["0q"]
        if r.get("current") and r.get("90daysAgo"):
            drift_0q = r["current"] / r["90daysAgo"] - 1
        cols = st.columns(4)
        for i, per in enumerate([p for p in ("0q", "+1q", "0y", "+1y") if p in et.index]):
            row = et.loc[per]
            cols[i].metric(f"EPS est {per}", f"${row['current']:.2f}" if row.get("current") else "n/a",
                           f"{(row['current'] / row['90daysAgo'] - 1) * 100:+.1f}% vs 90d ago"
                           if row.get("current") and row.get("90daysAgo") else None)
    if isinstance(er, pd.DataFrame) and not er.empty and "0q" in er.index:
        r = er.loc["0q"]
        up = int(r.get("upLast30days") or 0)
        down = int(r.get("downLast30days") or 0)
        breadth_0q = up - down
        st.caption(f"Current-quarter revisions (30d): **{up} up / {down} down**.")

    rt = an.get("recommendation_trend")
    if isinstance(rt, pd.DataFrame) and not rt.empty:
        latest_rec = rt.iloc[0]
        buys = int(latest_rec.get("strongBuy", 0) + latest_rec.get("buy", 0))
        total = int(latest_rec.get("strongBuy", 0) + latest_rec.get("buy", 0) +
                    latest_rec.get("hold", 0) + latest_rec.get("sell", 0) +
                    latest_rec.get("strongSell", 0))
        if total:
            st.caption(f"Analyst ratings: **{buys}/{total} buy or strong-buy** "
                       f"({latest_rec.get('hold', 0)} hold).")

    st.markdown("### Verdict")
    below_200 = last.get("MA200", np.nan)
    mom3 = px["Close"].iloc[-1] / px["Close"].iloc[-63] - 1 if len(px) > 63 else 0
    if drift_0q is not None:
        disloc = (drift_0q > 0.02 and (breadth_0q or 0) >= 0 and
                  (price < below_200 or mom3 < -0.05))
        if disloc:
            st.success(f"**Potential dislocation:** estimates revised **up {drift_0q * 100:+.1f}%** "
                       f"over 90 days while the price lags "
                       f"({'below' if price < below_200 else 'near'} the 200-day MA, "
                       f"3-month return {mom3 * 100:+.1f}%). Classic accumulation setup — verify the thesis.")
        elif drift_0q < -0.02:
            st.warning(f"Estimates are being **cut ({drift_0q * 100:.1f}% over 90d)** — "
                       "a falling price here is repricing, not mispricing.")
        else:
            st.info("Estimates and price are moving together — no clear dislocation right now.")
    else:
        st.info("Estimate history unavailable — cannot score dislocation for this ticker.")

    st.markdown("### Relative strength")
    with st.spinner("Loading benchmarks…"):
        spy = D.get_history("SPY", period)["Close"]
        sec_sym = D.sector_benchmark(snap["sector"])
        sec = D.get_history(sec_sym, period)["Close"]
    rs_spy = T.relative_strength(px["Close"], spy)
    rs_sec = T.relative_strength(px["Close"], sec)
    if not rs_spy.empty:
        st.plotly_chart(charts.rs_chart(rs_spy, rs_sec), width="stretch")
        st.caption(f"Sector benchmark: {sec_sym} ({snap['sector'] or 'sector unknown'}). "
                   "A rising line while price consolidates = institutional demand absorbing supply.")

# ================= TAB 5 — ENTRY PLANNER =================
with tabs[4]:
    st.subheader("Risk-managed entry & scaling")
    prof = T.vpvr(px)
    poc = float(prof["poc"].iloc[0])
    wma200 = last.get("WMA200", np.nan)
    anchor_200 = float(wma200) if not np.isnan(wma200) else float(last.get("MA200", price))
    low52 = T.swing_low(px, 252)
    levels = {"Current price": price, "200-week MA": anchor_200,
              "Volume POC": poc, "52-week low": low52}
    st.markdown("#### Tranche planner")
    cap = st.number_input("Total capital ($)", value=10000, step=1000)
    target = st.number_input("Base-case target ($/share)",
                             value=float(st.session_state.get("base_iv") or price))
    cols = st.columns(4)
    weights, lvl_names = [], []
    for i, (name, lv) in enumerate(levels.items()):
        with cols[i]:
            st.markdown(f"**{name}** — {fmt_money(lv)}")
            w = st.number_input(f"Weight % ({name})", value=[40, 25, 20, 15][i],
                                step=5, key=f"w{i}")
            weights.append(w)
            lvl_names.append(name)
    wsum = sum(weights) or 1
    plan = pd.DataFrame({
        "Level": lvl_names,
        "Price": [levels[n] for n in lvl_names],
        "Weight %": [w / wsum * 100 for w in weights],
    })
    plan["Capital $"] = cap * plan["Weight %"] / 100
    plan["Shares"] = plan["Capital $"] / plan["Price"]
    blended = (plan["Capital $"] * plan["Price"]).sum() / plan["Capital $"].sum()
    st.dataframe(plan.style.format({"Price": "${:,.2f}", "Weight %": "{:.1f}%",
                                    "Capital $": "${:,.0f}", "Shares": "{:.1f}"}),
                 width="stretch")
    c1, c2, c3 = st.columns(3)
    c1.metric("Blended cost", fmt_money(blended))
    c2.metric("Total shares", f"{plan['Shares'].sum():,.1f}")
    c3.metric("Upside to target", f"{(target / blended - 1) * 100:+.1f}%")

    st.markdown("#### Drawdown & pain-threshold simulator")
    dd = T.drawdown_stats(px["Close"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Max drawdown", f"{dd['max_drawdown'] * 100:.1f}%",
              f"trough {dd['trough'].date()}")
    c2.metric("Recovery time",
              f"{dd['days_to_recover']} days" if dd["days_to_recover"] is not None else "not yet")
    c3.metric("Worst 3-yr hold", f"{(dd['worst_3y'] or 0) * 100:.1f}%" if dd["worst_3y"] else "n/a")
    c4.metric("Worst 5-yr hold", f"{(dd['worst_5y'] or 0) * 100:.1f}%" if dd["worst_5y"] else "n/a")
    st.caption("Worst rolling buy-and-hold returns over the available history. "
               "If the worst 5-year hold is negative, size the position for capital lockup.")

    st.markdown("#### Export")
    mos_now = V.margin_of_safety(st.session_state.get("base_iv") or 0, price)
    report = f"""# Invest Studio — {ticker} ({snap['name']})
_Date: {pd.Timestamp.now().date()}_

## Snapshot
- Price: {fmt_money(price)} | Market cap: {fmt_big(snap['market_cap'])}
- Trailing P/E: {snap['trailing_pe']} | Forward P/E: {snap['forward_pe']}
- Trend regime: {regime_text}

## Valuation (base case)
- Intrinsic value: {fmt_money(st.session_state.get('base_iv'))}
- Margin of safety: {fmt_pct(mos_now)}
- Implied 10-yr growth priced in: see app

## Entry plan
- Total capital: ${cap:,.0f} | Blended cost: {fmt_money(blended)}
- Upside to base target {fmt_money(target)}: {(target / blended - 1) * 100:+.1f}%

## Stress
- Max drawdown: {dd['max_drawdown'] * 100:.1f}% (trough {dd['trough'].date()})
- Worst 3-yr / 5-yr holds: {(dd['worst_3y'] or 0) * 100:.1f}% / {(dd['worst_5y'] or 0) * 100:.1f}%

_For education and research only — not investment advice._
"""
    st.download_button("Download research note (.md)", report,
                       file_name=f"{ticker}_research_note.md")

# ================= TAB 6 — PORTFOLIO =================
with tabs[5]:
    st.subheader("Portfolio optimization")
    st.caption("Mean-variance, max Sortino, and min max-drawdown — up to 30 tickers. "
               "Backward-looking: it optimizes on historical returns, so treat the output "
               "as a starting point, not a recommendation.")

    pf_tickers_raw = st.text_area(
        "Tickers (comma-separated, up to 30)",
        value="NVDA, MSFT, META, AMD, AVGO, TSM, AAPL, GOOGL", key="pf_tickers")
    c1, c2 = st.columns(2)
    with c1:
        objective = st.selectbox(
            "Objective",
            ["Mean-variance (max Sharpe)", "Max Sortino ratio", "Min max drawdown"],
            key="pf_obj")
    with c2:
        pf_lookback = st.pills("Lookback", ["1Y", "3Y", "5Y", "10Y"],
                               default="5Y", key="pf_lookback")
    with st.expander("Constraints & assumptions"):
        cc1, cc2 = st.columns(2)
        with cc1:
            long_only = st.checkbox("Long only", value=True, key="pf_longonly")
            max_w = st.slider("Max weight per asset", 10, 100, 50, 5, key="pf_maxw") / 100
        with cc2:
            mar = st.number_input("Min acceptable return, % (Sortino)",
                                  value=0.0, step=0.5, key="pf_mar") / 100
            min_ret = st.number_input("Min acceptable return, % (min drawdown)",
                                      value=0.0, step=0.5, key="pf_minret") / 100

    with st.expander("Compare with my current allocation (optional)"):
        pf_alloc_raw = st.text_input(
            "Current weights, % — same order as the tickers above",
            value="", key="pf_alloc", placeholder="e.g. 30, 20, 15, 10, 10, 5, 5, 5")
        st.caption("One number per ticker, in the same order. Leave blank to skip. "
                   "They'll be normalized to 100%.")

    if st.button("Run optimization", type="primary", key="pf_run"):
        tickers = [t.strip().upper() for t in pf_tickers_raw.split(",") if t.strip()][:30]
        if len(tickers) < 2:
            st.error("Enter at least 2 tickers.")
        else:
            with st.spinner(f"Loading {len(tickers)} tickers and optimizing…"):
                rets, dropped = PF.get_returns(
                    tickers, {"1Y": "1y", "3Y": "3y", "5Y": "5y", "10Y": "10y"}[pf_lookback or "5Y"])
                if not rets.empty:
                    mu, sigma = PF.annualized(rets)
                    if objective.startswith("Mean"):
                        w = PF.max_sharpe(mu, sigma, max_w, long_only)
                    elif objective.startswith("Max Sortino"):
                        w = PF.max_sortino(rets, mar, max_w, long_only)
                    else:
                        w = PF.min_max_drawdown(rets, min_ret, max_w, long_only)
                    w_cur, alloc_msg = PF.parse_weights(pf_alloc_raw, len(rets.columns))
                    if w_cur is None and alloc_msg:
                        st.error(alloc_msg)
                    else:
                        st.session_state["pf_result"] = {
                            "tickers": list(rets.columns), "w": w,
                            "w_eq": np.full(len(rets.columns), 1.0 / len(rets.columns)),
                            "w_cur": w_cur, "alloc_note": alloc_msg,
                            "rets": rets, "mu": mu, "sigma": sigma,
                            "objective": objective, "mar": mar, "dropped": dropped,
                            "max_w": max_w, "long_only": long_only}
            if dropped:
                st.warning(f"Could not load: {', '.join(dropped)}")
            if rets.empty or rets.shape[1] < 2:
                st.error("Not enough usable tickers — need at least 2 with overlapping history.")

    res = st.session_state.get("pf_result")
    if res is not None:
        tickers, w, w_eq = res["tickers"], res["w"], res["w_eq"]
        rets, mu, sigma = res["rets"], res["mu"], res["sigma"]
        res_max_w, res_long_only = res.get("max_w", 0.5), res.get("long_only", True)
        s_opt, s_eq = PF.stats(w, rets, res["mar"]), PF.stats(w_eq, rets, res["mar"])

        st.markdown(f"#### Optimized weights — {res['objective']}")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Ann. return", f"{s_opt['ann_ret'] * 100:.1f}%")
        m2.metric("Ann. volatility", f"{s_opt['ann_vol'] * 100:.1f}%")
        m3.metric("Sharpe", f"{s_opt['sharpe']:.2f}")
        m4.metric("Sortino", f"{s_opt['sortino']:.2f}")
        m5.metric("Max drawdown", f"{s_opt['max_dd'] * 100:.1f}%")

        wdf = pd.DataFrame({"Ticker": tickers, "Weight": w,
                            "Ann. return %": [mu[t] * 100 for t in tickers],
                            "Ann. vol %": [np.sqrt(sigma.loc[t, t]) * 100 for t in tickers]})
        wdf = wdf.sort_values("Weight", ascending=False).reset_index(drop=True)
        c1, c2 = st.columns([3, 2])
        with c1:
            st.plotly_chart(charts.weights_bar(wdf), width="stretch")
        with c2:
            st.dataframe(wdf.style.format({"Weight": "{:.1%}", "Ann. return %": "{:.1f}%",
                                                   "Ann. vol %": "{:.1f}%"}),
                         width="stretch", hide_index=True)

        comp_rows = [{"Portfolio": "Optimized", **s_opt},
                     {"Portfolio": "Equal weight", **s_eq}]
        w_cur = res.get("w_cur")
        if w_cur is not None:
            comp_rows.append({"Portfolio": "Current allocation",
                              **PF.stats(w_cur, rets, res["mar"])})
            if res.get("alloc_note"):
                st.caption(res["alloc_note"])
        comp = pd.DataFrame(comp_rows)
        st.markdown("#### Optimized vs equal weight vs current")
        st.dataframe(comp.style.format({"ann_ret": "{:.1%}", "ann_vol": "{:.1%}",
                                                "sharpe": "{:.2f}", "sortino": "{:.2f}",
                                                "max_dd": "{:.1%}"}),
                     width="stretch", hide_index=True)

        if res["objective"].startswith("Mean"):
            st.markdown("#### Efficient frontier")
            front = PF.efficient_frontier(mu, sigma, res_max_w, res_long_only)
            opt_pt = (s_opt["ann_vol"], s_opt["ann_ret"])
            eq_pt = (s_eq["ann_vol"], s_eq["ann_ret"])
            cur_pt = None
            if w_cur is not None:
                s_cur = PF.stats(w_cur, rets, res["mar"])
                cur_pt = (s_cur["ann_vol"], s_cur["ann_ret"])
            st.plotly_chart(charts.frontier_chart(front, opt_pt, eq_pt, cur_pt),
                            width="stretch")
            st.caption("Frontier uses the same bounds as the optimizer.")

        st.markdown("#### Growth of $10,000")
        gseries = {"Optimized": PF.growth(w, rets),
                   "Equal weight": PF.growth(w_eq, rets)}
        if w_cur is not None:
            gseries["Current allocation"] = PF.growth(w_cur, rets)
        st.plotly_chart(charts.growth_chart(gseries), width="stretch")

        st.markdown("#### Growth vs valuation")
        with st.spinner("Loading forward P/E and consensus EPS growth…"):
            gv = D.get_growth_valuation(tuple(tickers))
        gv_ok = gv.dropna(subset=["forward_pe", "eps_cagr"])
        gv_ok = gv_ok[gv_ok["forward_pe"] > 0].reset_index(drop=True)
        if gv_ok.empty:
            st.caption("No forward P/E / consensus EPS growth data available for these tickers right now.")
        else:
            st.plotly_chart(charts.growth_valuation_scatter(gv_ok), width="stretch")
            skipped = sorted(set(tickers) - set(gv_ok["ticker"]))
            if skipped:
                st.caption(f"Skipped (missing forward P/E or consensus growth): {', '.join(skipped)}")
            st.caption("X: forward P/E (Yahoo). Y: 1-yr forward consensus EPS growth "
                       "(+1y vs current-year analyst EPS). Lower-left = cheaper for the growth; "
                       "upper-left = the GARP sweet spot.")
            gv_tbl = gv_ok[["ticker", "forward_pe", "eps_cagr"]].rename(
                columns={"ticker": "Ticker", "forward_pe": "Forward P/E",
                         "eps_cagr": "EPS growth 1Y"})
            st.dataframe(gv_tbl.style.format({"Forward P/E": "{:.1f}", "EPS growth 1Y": "{:.1%}"}),
                         width="stretch", hide_index=True)
