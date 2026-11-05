"""Matrix tab data: one row per name, live Yahoo metrics + DCF stacks and
reverse-DCF priced-in figures from prior analyses, set against consensus
price targets so valuation methods can be compared side by side.

A blank DCF or priced-in cell means no stack exists for that name yet — it is
left blank rather than invented, and every added name gets at least a base-case
DCF run instead of a permanent blank.
"""
import numpy as np
import pandas as pd
import re
import streamlit as st
import yfinance as yf

import data as D

# Book names + watchlist, in the user's usual order.
MATRIX_TICKERS = ["NVDA", "META", "MSFT", "AVGO", "TSM", "AMZN", "GOOGL",
                  "AMD", "MU", "ANET", "VST", "SPCX", "PLTR", "MRVL",
                  "LLY", "TSLA", "ASML", "CRWD", "ARM", "ALAB", "COHR"]

# ticker -> (bear, base, bull) DCF values where a full stack exists.
# All 18 book names have stacks (Nov 2, 2026 run, 10% hurdle, 3% terminal);
# ARM added Nov 5, 2026 (post-FQ2 FY27 refresh, same convention);
# ALAB + COHR added Nov 5, 2026 (post-print stacks, same convention).
# VST bear is floored at $0: raw model value is -$0.50 (EV below net debt),
# but limited liability floors equity at zero — see the tab footnote.
DCF_STACKS = {
    "MU": (342.0, 811.0, 1709.0),
    "NVDA": (227.0, 292.0, 387.0),
    "AMD": (341.0, 470.0, 583.0),
    "GOOGL": (169.0, 281.0, 459.0),
    "META": (392.0, 738.0, 1128.0),
    "MSFT": (264.0, 390.0, 554.0),
    "AVGO": (134.0, 231.0, 421.0),
    "AMZN": (84.0, 148.0, 248.0),
    "TSM": (219.0, 414.0, 599.0),
    "ANET": (80.0, 141.0, 226.0),
    "VST": (0.0, 50.0, 95.0),
    "SPCX": (17.0, 81.0, 273.0),
    "PLTR": (48.0, 106.0, 222.0),
    "MRVL": (39.0, 78.0, 149.0),
    "LLY": (322.0, 592.0, 976.0),
    "TSLA": (28.0, 71.0, 145.0),
    "ASML": (727.0, 1217.0, 2031.0),
    "CRWD": (38.0, 71.0, 117.0),
    "ARM": (33.0, 87.0, 141.0),
    "ALAB": (110.0, 244.0, 555.0),
    "COHR": (74.0, 231.0, 566.0),
}

# ticker -> (display label, anchor price the reverse-DCF was run at)
# All 18 book names have reverse-DCF priced-in growth (Nov 2, 2026 run,
# uniform 10-yr growth, 10% hurdle, 3% terminal, lab FCF convention gross of SBC).
# ARM added Nov 5, 2026 (anchor = live price at run time, $168.57).
# ALAB + COHR added Nov 5, 2026 (anchors = live prices at run time).
PRICED_IN = {
    "GOOGL": ("11.8% @ $279", 279.0),
    "AMD": ("27–30% @ $557", 557.0),
    "NVDA": ("16.7% @ $204.64", 204.64),
    "META": ("9.2% @ $612", 612.0),
    "MSFT": ("14.0% @ $514", 514.0),
    "AVGO": ("16.4% @ $326", 326.0),
    "AMZN": ("16.3% @ $249", 249.0),
    "TSM": ("15.0% @ $403", 403.0),
    "ANET": ("16.8% @ $165", 165.0),
    "VST": ("10.9% @ $135", 135.0),
    "SPCX": ("42.5% @ $138", 138.0),
    "PLTR": ("31.7% @ $181", 181.0),
    "MRVL": ("26.0% @ $170", 170.0),
    "LLY": ("20.9% @ $1,419", 1419.0),
    "TSLA": ("33.9% @ $404", 404.0),
    "ASML": ("15.2% @ $1,537", 1537.0),
    "CRWD": ("35.1% @ $243", 243.0),
    "MU": ("8.4% @ $839", 839.0),
    "ARM": ("28.2% @ $168.57", 168.57),
    "ALAB": ("22.4% @ $184.06", 184.06),
    "COHR": ("15.8% @ $195.09", 195.09),
}

# Base-case DCF assumptions behind the DCF base column, in MATRIX_TICKERS order:
# (growth yrs 1–5, growth yrs 6–10, TTM FCF margin, normalized FCF margin).
# Uniform for every name: 10% hurdle, 3% terminal growth, 5-yr margin convergence.
# TTM margin is the lab's quarterly-sum FCF margin, except GOOGL (maintenance-capex
# margin 24.2%; trough total-capex margin is 4.2%) and SPCX (TTM margin deeply
# negative on peak capex, converging to norm over 5 yrs). NVDA/AMD paths were
# reconstructed Nov 2 — each reproduces its displayed base exactly (NVDA $291.63
# vs $292; AMD $470 exactly), as the original paths weren't recorded in the run log.
BASE_ASSUMPTIONS = {
    "NVDA": (0.30, 0.12, 0.419, 0.40),
    "META": (0.17, 0.05, 0.1186, 0.30),
    "MSFT": (0.14, 0.06, 0.173, 0.35),
    "AVGO": (0.15, 0.08, 0.4422, 0.45),
    "TSM": (0.20, 0.10, 0.2958, 0.37),
    "AMZN": (0.14, 0.06, -0.0436, 0.10),
    "GOOGL": (0.15, 0.08, 0.2421, 0.25),
    "AMD": (0.25, 0.15, 0.203, 0.35),
    "MU": (0.10, 0.05, 0.4427, 0.30),
    "ANET": (0.20, 0.08, 0.489, 0.45),
    "VST": (0.04, 0.02, 0.1174, 0.13),
    "SPCX": (0.45, 0.25, -1.253, 0.25),
    "PLTR": (0.32, 0.15, 0.5455, 0.58),
    "MRVL": (0.20, 0.10, 0.1823, 0.20),
    "LLY": (0.14, 0.05, 0.1352, 0.28),
    "TSLA": (0.12, 0.06, 0.0318, 0.11),
    "ASML": (0.15, 0.08, 0.532, 0.35),
    "CRWD": (0.22, 0.12, 0.2822, 0.30),
    "ARM": (0.25, 0.12, 0.215, 0.35),
    "ALAB": (0.40, 0.12, 0.2215, 0.35),
    "COHR": (0.25, 0.10, -0.1448, 0.15),
}

# Yahoo's sharesOutstanding is incomplete for multi-class names; use total shares
# confirmed from market cap / price. SPCX: Q3 report total A+B. META: Class A only
# in Yahoo's count (2.214B) vs 2.557B total A+B. PLTR: total A+B+F vs 2.301B reported.
# Market cap is rebuilt from the override, which also corrects it.
SHARES_OVERRIDE = {"SPCX": 13.58e9, "META": 2.557e9, "PLTR": 2.4031e9}

GROUPS = {
    "Score": ["Score"],
    "Price & move": ["Price", "Day %", "Market cap ($B)"],
    "Analyst consensus": ["Consensus", "Gap to consensus %"],
    "DCF": ["DCF bear", "DCF base", "DCF bull", "Priced-in growth"],
    "VC exit value": ["Revenue ($B)", "Growth used %", "Shares (B)",
                      "Net cash ($B)", "VC exit value", "VC upside %",
                      "VC priced-in growth %"],
    "Multiples": ["Fwd P/E", "Trail P/E", "PEG", "P/S", "EV/EBITDA"],
    "Growth & quality": ["Rev growth % (Q YoY)", "Op margin % (TTM)", "Profit margin % (TTM)",
                         "Beta", "Div %"],
    "Position": ["52wk position %", "Next earnings"],
}


@st.cache_data(ttl=3600, show_spinner=False)
def _extra(ticker: str) -> dict:
    """Fields get_snapshot doesn't carry: prev close, 52wk range, growth, revenue, earnings date."""
    out = {"prev_close": None, "wk52_high": None, "wk52_low": None,
           "rev_growth": None, "revenue": None, "currency": "USD",
           "next_earnings": None}
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        out["prev_close"] = info.get("previousClose")
        out["wk52_high"] = info.get("fiftyTwoWeekHigh")
        out["wk52_low"] = info.get("fiftyTwoWeekLow")
        out["rev_growth"] = info.get("revenueGrowth")
        out["revenue"] = info.get("totalRevenue")
        out["currency"] = info.get("financialCurrency") or info.get("currency") or "USD"
        try:
            cal = t.calendar
            if isinstance(cal, dict):
                dates = cal.get("Earnings Date")
                if dates:
                    d = dates[0] if isinstance(dates, (list, tuple)) else dates
                    out["next_earnings"] = pd.Timestamp(d).strftime("%Y-%m-%d")
        except Exception:
            pass
    except Exception:
        pass
    return out


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return np.nan
    return v if np.isfinite(v) else np.nan


@st.cache_data(ttl=3600, show_spinner=False)
def _fx_per_usd(currency: str):
    """Foreign-currency units per USD (1.0 for USD). None if Yahoo lacks the pair."""
    if not currency or currency == "USD":
        return 1.0
    try:
        t = yf.Ticker(f"USD{currency}=X")
        fast = dict(t.fast_info) if hasattr(t, "fast_info") else {}
        rate = fast.get("lastPrice") or (t.info or {}).get("previousClose")
        rate = _num(rate)
        return rate if rate and rate > 0 else None
    except Exception:
        return None


def build_matrix(tickers=None, on_progress=None) -> pd.DataFrame:
    """One row per ticker. Defaults to MATRIX_TICKERS (the user's book names).
    on_progress(i, n, ticker) drives a progress bar. Unknown tickers still get
    a row with blank metrics rather than breaking the table."""
    tickers = list(tickers) if tickers else list(MATRIX_TICKERS)
    rows = []
    for i, tk in enumerate(tickers):
        if on_progress is not None:
            on_progress(i, len(tickers), tk)
        snap = D.get_snapshot(tk) or {}
        ex = _extra(tk)
        price = _num(snap.get("price"))
        mcap = _num(snap.get("market_cap"))
        if tk in SHARES_OVERRIDE and np.isfinite(price):
            mcap = price * SHARES_OVERRIDE[tk]
        prev = _num(ex["prev_close"])
        day = (price / prev - 1) if np.isfinite(price) and np.isfinite(prev) and prev else np.nan
        hi, lo = _num(ex["wk52_high"]), _num(ex["wk52_low"])
        pos = ((price - lo) / (hi - lo) if np.isfinite(price) and np.isfinite(hi)
               and np.isfinite(lo) and hi > lo else np.nan)
        cons = _num(snap.get("target_mean"))
        gap_cons = (price / cons - 1) if np.isfinite(price) and np.isfinite(cons) and cons else np.nan
        bear, dbase, bull = DCF_STACKS.get(tk, (np.nan, np.nan, np.nan))
        priced, _anchor = PRICED_IN.get(tk, (np.nan, np.nan))
        # VC-method inputs (the value itself is computed in the tab, where the
        # user tunes years / exit multiple / hurdle). Growth is Yahoo YoY
        # revenue growth clipped to [0%, 30%]; 10% when Yahoo lacks it.
        # Non-USD reporters (e.g. TSM in TWD) are converted at Yahoo's FX rate;
        # their share count uses market-cap-implied ADR shares, since Yahoo's
        # share count is in ordinary shares while the price is the ADR price.
        fx = _fx_per_usd(ex.get("currency") or "USD")
        rev_raw = _num(ex["revenue"])
        rev_b = rev_raw / fx / 1e9 if np.isfinite(rev_raw) and fx else np.nan
        raw_g = _num(ex["rev_growth"])
        g_used = float(np.clip(raw_g, 0.0, 0.30)) if np.isfinite(raw_g) else 0.10
        shares_b = _num(snap.get("shares")) / 1e9
        if tk in SHARES_OVERRIDE:
            shares_b = SHARES_OVERRIDE[tk] / 1e9
        elif (ex.get("currency") or "USD") != "USD" and np.isfinite(price) and price \
                and np.isfinite(mcap):
            shares_b = mcap / price / 1e9
        cash_raw = _num(snap.get("total_cash"))
        debt_raw = _num(snap.get("total_debt"))
        net_cash_b = ((cash_raw - debt_raw) / fx / 1e9
                      if np.isfinite(cash_raw) and np.isfinite(debt_raw) and fx else np.nan)
        rows.append({
            "Ticker": tk,
            "Name": snap.get("name") or tk,
            "Price": price,
            "Day %": day,
            "Market cap ($B)": mcap / 1e9 if np.isfinite(mcap) else np.nan,
            "Consensus": cons,
            "Gap to consensus %": gap_cons,
            "DCF bear": bear,
            "DCF base": dbase,
            "DCF bull": bull,
            "Priced-in growth": priced,
            "Revenue ($B)": rev_b,
            "Growth used %": g_used,
            "Shares (B)": shares_b,
            "Net cash ($B)": net_cash_b,
            "Fwd P/E": _num(snap.get("forward_pe")),
            "Trail P/E": _num(snap.get("trailing_pe")),
            "PEG": _num(snap.get("peg")),
            "P/S": _num(snap.get("ps")),
            "EV/EBITDA": _num(snap.get("ev_ebitda")),
            "Rev growth % (Q YoY)": _num(ex["rev_growth"]),
            "Op margin % (TTM)": _num(snap.get("op_margin")),
            "Profit margin % (TTM)": _num(snap.get("profit_margin")),
            "Beta": _num(snap.get("beta")),
            "Div %": _num(snap.get("div_yield")),
            "52wk position %": pos,
            "Next earnings": ex["next_earnings"] or np.nan,
        })
    if on_progress is not None:
        on_progress(len(tickers), len(tickers), "done")
    cols = ["Ticker", "Name"] + [c for grp in GROUPS.values() for c in grp]
    return pd.DataFrame(rows, columns=cols)


def vc_exit_value(rev_b, g, shares_b, net_cash_b, years, ev_sales, hurdle):
    """VC-method value per share, vectorized over DataFrame columns ($B units).

    Exit EV = revenue grown at g for `years`, times `ev_sales`. Equity value =
    exit EV discounted at `hurdle`, plus today's net cash, divided by shares.
    """
    rev_b = np.asarray(rev_b, dtype=float)
    g = np.asarray(g, dtype=float)
    shares_b = np.asarray(shares_b, dtype=float)
    net_cash_b = np.asarray(net_cash_b, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        exit_ev = rev_b * (1.0 + g) ** years * ev_sales
        pv = exit_ev / (1.0 + hurdle) ** years
        val = (pv + net_cash_b) / shares_b
    return np.where(np.isfinite(val) & (shares_b > 0) & (rev_b > 0), val, np.nan)


def vc_priced_in_growth(price, rev_b, shares_b, net_cash_b, years, ev_sales,
                        hurdle, lo=-0.20, hi=3.0, iters=50):
    """Uniform priced-in growth: the g that makes the VC exit value equal today's
    price, holding years / exit multiple / hurdle fixed. Vectorized bisection.
    NaN where the price falls outside the solvable bracket (or inputs missing)."""
    price = np.asarray(price, dtype=float)
    rev_b = np.asarray(rev_b, dtype=float)
    shares_b = np.asarray(shares_b, dtype=float)
    net_cash_b = np.asarray(net_cash_b, dtype=float)

    def _val(g):
        exit_ev = rev_b * (1.0 + g) ** years * ev_sales
        return (exit_ev / (1.0 + hurdle) ** years + net_cash_b) / shares_b

    lo_a = np.full(price.shape, lo, dtype=float)
    hi_a = np.full(price.shape, hi, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        vlo, vhi = _val(lo_a), _val(hi_a)
        ok = np.isfinite(price) & np.isfinite(vlo) & np.isfinite(vhi) & (vlo <= price) & (price <= vhi)
        for _ in range(iters):
            mid = (lo_a + hi_a) / 2
            vm = _val(mid)
            go_up = vm < price
            lo_a = np.where(go_up, mid, lo_a)
            hi_a = np.where(go_up, hi_a, mid)
        g = (lo_a + hi_a) / 2
    return np.where(ok, g, np.nan)


# Composite Score: one 0–100 rank from existing Matrix columns only (no outside
# inputs, no personal overrides). Weights: DCF priced-in growth 35%, gap to DCF base 25%,
# gap to consensus 30%, VC priced-in growth (multiple-risk gauge) 10%.
# Each leg is clipped-linear scaled so small differences stay small (percentile
# ranks exaggerated clustered values, e.g. 15.0% vs 16.7% priced-in).
SCORE_WEIGHTS = {"pi": 0.35, "base": 0.25, "cons": 0.30, "vc": 0.10}
SCORE_CLIPS = {"pi": (8.0, 43.0), "base": (-0.85, 0.45),
               "cons": (0.0, 1.0), "vc": (0.0, 0.87)}


def parse_priced_in(label):
    """'26.0% @ $170' -> 26.0; ranges ('27–30% @ $557') -> midpoint 28.5."""
    if label is None or (isinstance(label, float) and np.isnan(label)):
        return np.nan
    m = re.match(r"\s*([\d.]+)(?:\s*[–-]\s*([\d.]+))?\s*%", str(label))
    if not m:
        return np.nan
    a = float(m.group(1))
    return (a + float(m.group(2))) / 2 if m.group(2) else a


def _clip_score(values, lo, hi, lower_better):
    v = np.clip(np.asarray(values, dtype=float), lo, hi)
    sc = (v - lo) / (hi - lo) * 100.0
    return 100.0 - sc if lower_better else sc


def add_score(df):
    """Append the composite Score (0–100, higher is better) from columns already
    in the frame. NaN where any leg is missing (e.g. added tickers without a
    DCF stack, consensus target, priced-in run, or VC inputs). The VC leg moves
    with the tab's VC sliders, so the Score moves with them too."""
    df = df.copy()
    pi = (df["Priced-in growth"].map(parse_priced_in)
          if "Priced-in growth" in df else np.nan)
    gap_base = (df["DCF base"] - df["Price"]) / df["Price"]
    gap_cons = (df["Consensus"] - df["Price"]) / df["Price"]
    vc = df["VC priced-in growth %"] if "VC priced-in growth %" in df else np.nan
    s = (SCORE_WEIGHTS["pi"] * _clip_score(pi, *SCORE_CLIPS["pi"], True)
         + SCORE_WEIGHTS["base"] * _clip_score(gap_base, *SCORE_CLIPS["base"], False)
         + SCORE_WEIGHTS["cons"] * _clip_score(gap_cons, *SCORE_CLIPS["cons"], False)
         + SCORE_WEIGHTS["vc"] * _clip_score(vc, *SCORE_CLIPS["vc"], True))
    missing = (pd.isna(pi) | pd.isna(gap_base) | pd.isna(gap_cons) | pd.isna(vc))
    df["Score"] = np.where(missing, np.nan, s)
    return df


_FORMATS = {
    "Price": "${:,.2f}", "Market cap ($B)": "{:,.0f}",
    "Score": "{:.0f}",
    "Consensus": "${:,.2f}", "DCF bear": "${:,.0f}", "DCF base": "${:,.0f}",
    "DCF bull": "${:,.0f}",
    "Revenue ($B)": "{:,.0f}", "Shares (B)": "{:.2f}", "Net cash ($B)": "{:,.0f}",
    "VC exit value": "${:,.2f}", "VC upside %": "{:+.1%}",
    "VC priced-in growth %": "{:.0%}",
    "Day %": "{:.1%}", "Gap to consensus %": "{:+.1%}",
    "Growth used %": "{:.0%}",
    "Rev growth % (Q YoY)": "{:.1%}", "Op margin % (TTM)": "{:.1%}", "Profit margin % (TTM)": "{:.1%}",
    "Div %": "{:.2%}", "52wk position %": "{:.0%}",
    "Fwd P/E": "{:.1f}", "Trail P/E": "{:.1f}", "PEG": "{:.2f}",
    "P/S": "{:.1f}", "EV/EBITDA": "{:.1f}", "Beta": "{:.2f}",
}


def _gap_bg(val, good_below=True):
    """Gap-to-consensus: below the Street target (upside to target) = green tint,
    above it = red tint (dark-theme safe)."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    below = val < 0
    good = below if good_below else not below
    return ("background-color: rgba(46,160,67,0.28);" if good
            else "background-color: rgba(248,81,73,0.25);")


def style_matrix(df: pd.DataFrame):
    """Formats + gap coloring for st.dataframe."""
    sty = df.style.format(_FORMATS, na_rep="n/a")
    if "Gap to consensus %" in df.columns:
        sty = sty.map(_gap_bg, subset=["Gap to consensus %"])
    if "VC upside %" in df.columns:
        sty = sty.map(lambda v: _gap_bg(v, good_below=False), subset=["VC upside %"])
    return sty
