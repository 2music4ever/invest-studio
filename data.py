"""Market + fundamental data layer (Yahoo Finance via yfinance).

All network calls are cached. Every accessor degrades gracefully to
None/empty so the UI can explain what is missing instead of crashing.
Yahoo rate-limits aggressively from shared cloud IPs, so reads retry.
"""
import random
import time

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

SECTOR_ETF = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial Services": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}


def _with_retry(fn, tries=3, base_delay=2.0):
    """Retry a Yahoo call; cloud IPs get rate-limited often."""
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(base_delay * (i + 1) + random.random())
    raise last


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if isinstance(df.columns, pd.DatetimeIndex):
        return df
    # financial statements carry dates as columns — keep them parseable
    try:
        df.columns = pd.to_datetime(df.columns)
    except Exception:
        df.columns = [str(c).strip() for c in df.columns]
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def get_history(ticker: str, period: str = "10y") -> pd.DataFrame:
    """Daily OHLCV, dividend/split adjusted."""
    df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    if df is None or df.empty:
        return pd.DataFrame()
    df = _flatten(df)
    df = df[[c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]]
    return df.dropna(subset=["Close"])


@st.cache_data(ttl=3600, show_spinner=False)
def get_snapshot(ticker: str) -> dict:
    """Key stats; missing fields come back as None."""
    t = yf.Ticker(ticker)
    try:
        info = _with_retry(lambda: t.info or {}, tries=3)
    except Exception:
        info = {}
    try:
        fast = dict(t.fast_info) if hasattr(t, "fast_info") else {}
    except Exception:
        fast = {}

    def pick(*keys):
        for k in keys:
            if k in info and info[k] is not None:
                return info[k]
        return None

    price = pick("currentPrice", "regularMarketPrice") or fast.get("lastPrice")
    # Yahoo quirk: trailingAnnualDividendYield is a ratio (0.0074), but
    # dividendYield comes back in percent units (0.74 = 0.74%).
    div_yield = pick("trailingAnnualDividendYield")
    if div_yield is None:
        raw_dy = pick("dividendYield")
        div_yield = raw_dy / 100 if raw_dy else None
    # fast_info is a separate endpoint — it often survives when t.info is throttled
    shares = pick("sharesOutstanding") or fast.get("shares")
    market_cap = pick("marketCap") or fast.get("marketCap")
    return {
        "price": price,
        "name": pick("longName", "shortName") or ticker,
        "sector": pick("sector"),
        "industry": pick("industry"),
        "market_cap": market_cap,
        "shares": shares,
        "trailing_pe": pick("trailingPE"),
        "forward_pe": pick("forwardPE"),
        "peg": pick("pegRatio", "trailingPegRatio"),
        "ps": pick("priceToSalesTrailing12Months"),
        "pb": pick("priceToBook"),
        "ev_ebitda": pick("enterpriseToEbitda"),
        "profit_margin": pick("profitMargins"),
        "op_margin": pick("operatingMargins"),
        "roe": pick("returnOnEquity"),
        "fcf": pick("freeCashflow"),
        "total_debt": pick("totalDebt"),
        "total_cash": pick("totalCash"),
        "beta": pick("beta"),
        "div_yield": div_yield,
        "payout": pick("payoutRatio"),
        "target_mean": pick("targetMeanPrice"),
        "target_high": pick("targetHighPrice"),
        "target_low": pick("targetLowPrice"),
    }


def _row(df: pd.DataFrame, *names):
    """Find a financial-statement row by fuzzy name match."""
    if df is None or df.empty:
        return None
    lower = {str(c).lower(): c for c in df.index}
    for n in names:
        key = n.lower()
        if key in lower:
            return df.loc[lower[key]]
        for lk, orig in lower.items():
            if key in lk:
                return df.loc[orig]
    return None


@st.cache_data(ttl=86400, show_spinner=False)
def get_annuals(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    out = {}
    for attr in ("financials", "cashflow", "balance_sheet"):
        try:
            out[attr] = _flatten(_with_retry(lambda a=attr: getattr(t, a).copy(), tries=2))
        except Exception:
            out[attr] = pd.DataFrame()
    return out


@st.cache_data(ttl=86400, show_spinner=False)
def get_fundamentals(ticker: str) -> dict:
    """Latest-annual revenue, FCF, net debt, shares — prefilled DCF inputs."""
    a = get_annuals(ticker)
    inc, cf, bs = a["financials"], a["cashflow"], a["balance_sheet"]
    rev = _row(inc, "total revenue")
    ni = _row(inc, "net income")
    ocf = _row(cf, "operating cash flow")
    capex = _row(cf, "capital expenditure")
    debt = _row(bs, "total debt")
    cash = _row(bs, "cash and cash equivalents")
    snap = get_snapshot(ticker)

    def latest(s):
        if s is None or s.empty:
            return None
        s = s.dropna()
        return float(s.iloc[0]) if not s.empty else None

    revenue = latest(rev)
    ocf_v, capex_v = latest(ocf), latest(capex)
    fcf = (ocf_v + capex_v) if (ocf_v is not None and capex_v is not None) else None
    # capex prints negative in Yahoo statements; guard both conventions
    if fcf is not None and capex_v is not None and capex_v > 0 and ocf_v is not None:
        fcf = ocf_v - capex_v
    debt_v, cash_v = latest(debt), latest(cash)
    net_debt = (debt_v - cash_v) if (debt_v is not None and cash_v is not None) else None
    ni_v = latest(ni)
    fcf_margin = (fcf / revenue) if (fcf and revenue) else None
    return {
        "revenue": revenue,
        "fcf": fcf,
        "fcf_margin": fcf_margin,
        "net_income": ni_v,
        "net_margin": (ni_v / revenue) if (ni_v and revenue) else None,
        "net_debt": net_debt if net_debt is not None else snap.get("total_debt"),
        "shares": snap.get("shares"),
    }


@st.cache_data(ttl=86400, show_spinner=False)
def get_ttm_pe(ticker: str, price: pd.Series) -> pd.DataFrame:
    """Historical P/E: weekly TTM P/E for the recent year (quarterly
    statements) plus annual P/E points for earlier years. Approximation."""
    t = yf.Ticker(ticker)
    snap = get_snapshot(ticker)
    shares = snap.get("shares")
    if not shares:
        return pd.DataFrame()
    pidx = price.index
    if getattr(pidx, "tz", None) is not None:
        pidx = pidx.tz_localize(None)
    px = pd.Series(price.to_numpy(), index=pidx).sort_index()

    points = []  # (date, pe)

    def price_at(dt):
        dt = pd.Timestamp(dt).tz_localize(None) if getattr(pd.Timestamp(dt), "tz", None) else pd.Timestamp(dt)
        sub = px.loc[:dt]
        return float(sub.iloc[-1]) if not sub.empty else None

    # 1) annual EPS -> yearly P/E points
    try:
        ann = _flatten(t.financials.copy())
    except Exception:
        ann = pd.DataFrame()
    ni_ann = _row(ann, "net income")
    if ni_ann is not None and not ni_ann.empty:
        for dt, val in ni_ann.dropna().items():
            try:
                eps = float(val) / shares
            except Exception:
                continue
            if eps > 0:
                p = price_at(dt)
                if p:
                    points.append((pd.Timestamp(dt).tz_localize(None), p / eps))

    # 2) quarterly TTM -> weekly P/E for the recent stretch
    try:
        q = _flatten(t.quarterly_financials.copy())
    except Exception:
        q = pd.DataFrame()
    ni_q = _row(q, "net income")
    if ni_q is not None and not ni_q.empty:
        ni_q = ni_q.dropna().sort_index()
        if getattr(ni_q.index, "tz", None) is not None:
            ni_q.index = ni_q.index.tz_localize(None)
        if len(ni_q) >= 4:
            ttm = ni_q.rolling(4).sum().dropna()
            eps_w = (ttm / shares).resample("W").last().ffill()
            wk = px.resample("W").last()
            j = pd.DataFrame({"price": wk}).join(eps_w.rename("eps"), how="inner")
            j = j[j["eps"] > 0]
            for dt, row in j.iterrows():
                points.append((dt, float(row["price"]) / float(row["eps"])))

    if not points:
        return pd.DataFrame()
    out = pd.DataFrame(points, columns=["date", "pe"]).drop_duplicates("date").set_index("date")
    return out.sort_index()[["pe"]]


@st.cache_data(ttl=3600, show_spinner=False)
def get_fundamentals_history(ticker: str) -> pd.DataFrame:
    """Annual income/cash-flow history plus a current TTM point.

    Index: period-end dates. Columns: revenue, gross, opinc, netinc, fcf, eps
    (diluted), kind ('FY' or 'TTM'). Yahoo's free tier only carries ~4 annuals
    and ~5 quarters, so this is short — but it's the full history available.
    """
    t = yf.Ticker(ticker)

    def val(s, dt):
        if s is None:
            return np.nan
        try:
            return float(s.get(dt, np.nan))
        except (TypeError, ValueError):
            return np.nan

    recs = []
    try:
        ann = _flatten(t.financials.copy())
        acf = _flatten(t.cashflow.copy())
    except Exception:
        ann, acf = pd.DataFrame(), pd.DataFrame()
    if not ann.empty:
        rev, gro = _row(ann, "total revenue"), _row(ann, "gross profit")
        opi, net = _row(ann, "operating income"), _row(ann, "net income")
        eps, fcf = _row(ann, "diluted eps"), _row(acf, "free cash flow")
        for dt in sorted(ann.columns):
            recs.append({"date": pd.Timestamp(dt).tz_localize(None), "kind": "FY",
                         "revenue": val(rev, dt), "gross": val(gro, dt),
                         "opinc": val(opi, dt), "netinc": val(net, dt),
                         "fcf": val(fcf, dt), "eps": val(eps, dt)})
    try:
        q = _flatten(t.quarterly_financials.copy())
        qcf = _flatten(t.quarterly_cashflow.copy())
    except Exception:
        q, qcf = pd.DataFrame(), pd.DataFrame()
    if not q.empty and len(q.columns) >= 4:
        cols = list(q.columns[:4])

        def qsum(s):
            vals = [val(s, c) for c in cols]
            return float(np.nansum(vals)) if not all(np.isnan(v) for v in vals) else np.nan

        recs.append({"date": pd.Timestamp(cols[0]).tz_localize(None), "kind": "TTM",
                     "revenue": qsum(_row(q, "total revenue")),
                     "gross": qsum(_row(q, "gross profit")),
                     "opinc": qsum(_row(q, "operating income")),
                     "netinc": qsum(_row(q, "net income")),
                     "fcf": qsum(_row(qcf, "free cash flow")),
                     "eps": qsum(_row(q, "diluted eps"))})
    if not recs:
        return pd.DataFrame()
    df = pd.DataFrame(recs).set_index("date").sort_index()
    # TTM can coincide with the latest fiscal year-end — prefer the TTM row
    return df[~df.index.duplicated(keep="last")]


@st.cache_data(ttl=3600, show_spinner=False)
def get_analyst(ticker: str) -> dict:
    """Consensus estimates, revisions, price targets, recommendation trend."""
    t = yf.Ticker(ticker)
    out = {}
    for attr in ("analyst_price_targets", "eps_trend", "eps_revisions",
                 "growth_estimates", "recommendation_trend"):
        try:
            v = _with_retry(lambda a=attr: getattr(t, a), tries=2)
            out[attr] = v
        except Exception:
            out[attr] = None
    # normalize DataFrames that came back transposed
    for k in ("eps_trend", "eps_revisions", "growth_estimates"):
        v = out.get(k)
        if isinstance(v, pd.DataFrame) and not v.empty:
            out[k] = _flatten(v)
    return out


def sector_benchmark(sector: str | None) -> str:
    if sector and sector in SECTOR_ETF:
        return SECTOR_ETF[sector]
    return "XLC"
