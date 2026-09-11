"""Invest Studio — long-term investing workbench. Modeling & accumulation, not trading."""
import numpy as np
import pandas as pd
import streamlit as st

import charts
import data as D
import technical as T
import valuation as V

st.set_page_config(page_title="Invest Studio", page_icon="📈", layout="wide")
st.title("📈 Invest Studio")
st.caption("Long-term investing workbench — valuation modeling, accumulation footprints, and entry planning. "
           "For education and research only, not investment advice.")


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


# ---------- sidebar ----------
ticker = st.sidebar.text_input("Ticker", "MSFT").strip().upper()
period = st.sidebar.selectbox("History", ["5y", "10y", "max"], index=1)
log_scale = st.sidebar.checkbox("Log price scale", True)
st.sidebar.caption("Data: Yahoo Finance (free). Estimates update intraday; fundamentals quarterly.")

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

tabs = st.tabs(["📊 Chart & Trend", "🧮 Valuation Lab", "🐋 Accumulation",
                "🔭 Dislocation", "🎯 Entry Planner"])

# ================= TAB 1 — CHART & TREND =================
with tabs[0]:
    st.subheader(f"{snap['name']} ({ticker})")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Price", fmt_money(price))
    c2.metric("Market cap", fmt_big(snap["market_cap"]))
    c3.metric("Trailing P/E", f"{snap['trailing_pe']:.1f}" if snap["trailing_pe"] else "n/a")
    c4.metric("Forward P/E", f"{snap['forward_pe']:.1f}" if snap["forward_pe"] else "n/a")
    c5.metric("PEG", f"{snap['peg']:.2f}" if snap["peg"] else "n/a")
    st.markdown(f"**Trend regime:** :{regime_color}[{regime_text}]")
    st.plotly_chart(charts.price_chart(px, log=log_scale,
                                       flags=T.wyckoff_flags(px)),
                    width="stretch")

    st.markdown("### Historical valuation bands")
    pe = D.get_ttm_pe(ticker, px["Close"])
    fig = charts.valuation_bands(pe)
    if fig:
        st.plotly_chart(fig, width="stretch")
        cur_pe = pe["pe"].iloc[-1]
        st.caption(f"Current P/E **{cur_pe:.1f}** vs 10th percentile "
                   f"**{pe['pe'].quantile(0.1):.1f}** and median "
                   f"**{pe['pe'].quantile(0.5):.1f}**. "
                   "Built from annual EPS (yearly points) plus recent TTM EPS (weekly) — "
                   "a coarse but honest read of where the multiple sits in its own history.")
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

# ================= TAB 2 — VALUATION LAB =================
with tabs[1]:
    st.subheader("DCF valuation — your assumptions drive the value")
    rev0 = fund["revenue"]
    if not rev0:
        st.warning("Revenue data unavailable for this ticker — enter assumptions manually.")
        rev0 = 1e9
    c = st.columns(4)
    revenue = c[0].number_input("Revenue (TTM, $M)", value=rev0 / 1e6, format="%.0f") * 1e6
    fcf_m = c[1].number_input("FCF margin %", value=(fund["fcf_margin"] or 0.15) * 100,
                              step=0.5) / 100
    disc = c[2].number_input("Discount rate %", value=9.0, step=0.25) / 100
    tg = c[3].number_input("Terminal growth %", value=2.5, step=0.25) / 100
    c = st.columns(4)
    g1 = c[0].number_input("Revenue growth yrs 1–5 %", value=12.0, step=0.5) / 100
    g2 = c[1].number_input("Revenue growth yrs 6–10 %", value=5.0, step=0.5) / 100
    net_debt = c[2].number_input("Net debt ($M)", value=(fund["net_debt"] or 0) / 1e6,
                                 format="%.0f") * 1e6
    shares = c[3].number_input("Shares out (M)", value=(fund["shares"] or 1e9) / 1e6,
                               format="%.0f") * 1e6

    try:
        iv, ev, sched = V.dcf(revenue, g1, g2, fcf_m, disc, tg, net_debt, shares)
        mos = V.margin_of_safety(iv, price)
        st.session_state["base_iv"] = iv
        g1c, g2c = st.columns([1, 2])
        with g1c:
            st.plotly_chart(charts.mos_gauge(mos, iv, price), width="stretch")
            st.markdown(f"**Verdict:** {V.mos_label(mos)}")
        with g2c:
            scen = pd.DataFrame([
                {"Scenario": "Bear", **dict(zip(("IV",),
                    [V.dcf(revenue, max(g1 - 0.05, -0.02), max(g2 - 0.03, 0), max(fcf_m - 0.02, 0.01),
                               disc + 0.01, tg, net_debt, shares)[0]]))},
                {"Scenario": "Base", "IV": iv},
                {"Scenario": "Bull", "IV": V.dcf(revenue, g1 + 0.05, g2 + 0.03, fcf_m + 0.02,
                                                 max(disc - 0.01, tg + 0.005), tg, net_debt, shares)[0]},
            ])
            st.plotly_chart(charts.scenario_bars(scen, price), width="stretch")

        st.markdown("### Reverse DCF — what growth is already priced in?")
        implied = V.reverse_dcf(price, revenue, fcf_m, disc, tg, net_debt, shares)
        if implied is None:
            st.info("Current price implies growth outside a sane −5%…+40% range — "
                    "expectations are either euphoric or deeply pessimistic.")
        else:
            st.markdown(f"The current price of **{fmt_money(price)}** implies **{implied * 100:.1f}%** "
                        f"annual revenue growth for 10 years at your margin/discount assumptions. "
                        f"Your base case assumes {g1 * 100:.0f}%/then {g2 * 100:.0f}% — "
                        + ("the market is more optimistic than you." if implied > g1
                           else "the market is pricing in less growth than you expect."))

        with st.expander("Year-by-year DCF schedule"):
            show = sched.copy()
            for col in ("Revenue", "FCF", "PV of FCF"):
                show[col] = show[col] / 1e6
            st.dataframe(show.style.format({"Revenue": "{:,.0f}", "FCF": "{:,.0f}",
                                            "PV of FCF": "{:,.0f}"}),
                         width="stretch")
            st.caption("Figures in $M.")
    except ValueError as e:
        st.error(str(e))

# ================= TAB 3 — ACCUMULATION =================
with tabs[2]:
    st.subheader("Institutional footprint")
    prof = T.vpvr(px)
    poc = float(prof["poc"].iloc[0])
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(charts.vpvr_chart(prof, price), width="stretch")
    with c2:
        d = px.copy()
        d["AD"] = T.accumulation_distribution(px)
        d["CMF20"] = T.cmf(px, 20)
        d["CMF60"] = T.cmf(px, 60)
        st.plotly_chart(charts.flow_chart(d), width="stretch")
    cmf60_now = float(d["CMF60"].iloc[-1]) if d["CMF60"].notna().any() else None
    ad_trend = "rising" if d["AD"].iloc[-1] > d["AD"].iloc[-63] else "falling"
    st.markdown(f"**Point of control (heaviest volume):** {fmt_money(poc)} — "
                f"{'below' if poc < price else 'above'} current price. "
                f"**A/D line** is {ad_trend} over 3 months. "
                f"**CMF(60):** {cmf60_now:+.2f}" if cmf60_now is not None else "" +
                " — sustained positive = quiet accumulation.")

    st.markdown("### Wyckoff-style structure flags (heuristic)")
    flags = T.wyckoff_flags(px)
    if flags:
        st.table(pd.DataFrame([{"Date": f["date"].date(), "Signal": f["type"],
                                "Read": f["note"]} for f in flags]))
    else:
        st.info("No classic accumulation structures flagged in the last 12 months.")
    st.caption("Heuristic pattern flags for research — not confirmed Wyckoff analysis.")

# ================= TAB 4 — DISLOCATION =================
with tabs[3]:
    st.subheader("Estimates vs price — the dislocation tracker")
    an = D.get_analyst(ticker)
    tgt = an.get("analyst_price_targets")
    if isinstance(tgt, dict) and tgt.get("mean"):
        c1, c2, c3 = st.columns(3)
        c1.metric("Consensus target", fmt_money(tgt.get("mean")),
                  f"{(tgt['mean'] / price - 1) * 100:+.1f}% vs price" if price else None)
        c2.metric("Target range", f"{fmt_money(tgt.get('low'))} – {fmt_money(tgt.get('high'))}")
        c3.metric("Analysts", tgt.get("numberOfAnalysts") or "n/a")
    else:
        st.info("No analyst price targets available for this ticker.")

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
            st.success(f"⚡ **Potential dislocation:** estimates revised **up {drift_0q * 100:+.1f}%** "
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
