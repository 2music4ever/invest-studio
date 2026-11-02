"""Matrix tab data: one row per name, live Yahoo metrics + DCF stacks and
reverse-DCF priced-in figures from prior analyses, set against consensus
price targets so valuation methods can be compared side by side.

A blank DCF or priced-in cell means no stack exists for that name — it is
left blank rather than invented. No adopted bases are shown here by design.
"""
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

import data as D

# Book names + watchlist, in the user's usual order.
MATRIX_TICKERS = ["NVDA", "META", "MSFT", "AVGO", "TSM", "AMZN", "GOOGL",
                  "AMD", "MU", "ANET", "VST", "SPCX", "PLTR", "MRVL",
                  "LLY", "TSLA", "ASML", "CRWD"]

# ticker -> (bear, base, bull) DCF values where a full stack exists.
DCF_STACKS = {
    "MU": (342.0, 811.0, 1709.0),
    "NVDA": (227.0, 292.0, 387.0),
    "AMD": (341.0, 470.0, 583.0),
    "GOOGL": (np.nan, 257.0, np.nan),
}

# ticker -> (display label, anchor price the reverse-DCF was run at)
PRICED_IN = {
    "GOOGL": ("14.9% @ $322", 322.0),
    "AMD": ("27–30% @ $557", 557.0),
    "NVDA": ("16.7% @ $204.64", 204.64),
}

# Yahoo reports one share class only for multi-class names; total shares
# (class A+B) confirmed from the Q3 report. Market cap is rebuilt from it.
SHARES_OVERRIDE = {"SPCX": 13.58e9}

GROUPS = {
    "Price & move": ["Price", "Day %", "Market cap ($B)"],
    "Analyst consensus": ["Consensus", "Gap to consensus %"],
    "DCF": ["DCF bear", "DCF base", "DCF bull", "Priced-in growth"],
    "Multiples": ["Fwd P/E", "Trail P/E", "PEG", "P/S", "EV/EBITDA"],
    "Growth & quality": ["Rev growth %", "Op margin %", "Profit margin %",
                         "Beta", "Div %"],
    "Position": ["52wk position %", "Next earnings"],
}


@st.cache_data(ttl=3600, show_spinner=False)
def _extra(ticker: str) -> dict:
    """Fields get_snapshot doesn't carry: prev close, 52wk range, growth, earnings date."""
    out = {"prev_close": None, "wk52_high": None, "wk52_low": None,
           "rev_growth": None, "next_earnings": None}
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        out["prev_close"] = info.get("previousClose")
        out["wk52_high"] = info.get("fiftyTwoWeekHigh")
        out["wk52_low"] = info.get("fiftyTwoWeekLow")
        out["rev_growth"] = info.get("revenueGrowth")
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


def build_matrix(on_progress=None) -> pd.DataFrame:
    """One row per MATRIX_TICKERS name. on_progress(i, n, ticker) for a progress bar."""
    rows = []
    for i, tk in enumerate(MATRIX_TICKERS):
        if on_progress is not None:
            on_progress(i, len(MATRIX_TICKERS), tk)
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
            "Fwd P/E": _num(snap.get("forward_pe")),
            "Trail P/E": _num(snap.get("trailing_pe")),
            "PEG": _num(snap.get("peg")),
            "P/S": _num(snap.get("ps")),
            "EV/EBITDA": _num(snap.get("ev_ebitda")),
            "Rev growth %": _num(ex["rev_growth"]),
            "Op margin %": _num(snap.get("op_margin")),
            "Profit margin %": _num(snap.get("profit_margin")),
            "Beta": _num(snap.get("beta")),
            "Div %": _num(snap.get("div_yield")),
            "52wk position %": pos,
            "Next earnings": ex["next_earnings"] or np.nan,
        })
    if on_progress is not None:
        on_progress(len(MATRIX_TICKERS), len(MATRIX_TICKERS), "done")
    cols = ["Ticker", "Name"] + [c for grp in GROUPS.values() for c in grp]
    return pd.DataFrame(rows, columns=cols)


_FORMATS = {
    "Price": "${:,.2f}", "Market cap ($B)": "{:,.0f}",
    "Consensus": "${:,.2f}", "DCF bear": "${:,.0f}", "DCF base": "${:,.0f}",
    "DCF bull": "${:,.0f}",
    "Day %": "{:.1%}", "Gap to consensus %": "{:+.1%}",
    "Rev growth %": "{:.1%}", "Op margin %": "{:.1%}", "Profit margin %": "{:.1%}",
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
    return sty
