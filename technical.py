"""Technical / accumulation math: MAs, VPVR, A/D, CMF, drawdowns, Wyckoff heuristics."""
import numpy as np
import pandas as pd


def add_trend(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    c = out["Close"]
    out["MA20"] = c.rolling(20).mean()
    out["MA50"] = c.rolling(50).mean()
    out["MA200"] = c.rolling(200).mean()
    wk = c.resample("W").last()
    out["WMA50"] = wk.rolling(50).mean().reindex(out.index, method="ffill")
    out["WMA200"] = wk.rolling(200).mean().reindex(out.index, method="ffill")
    return out


def regime(price: float, wma50: float, wma200: float) -> tuple[str, str]:
    if np.isnan(wma200):
        return ("Not enough history", "gray")
    if price > wma50 > wma200:
        return ("Secular uptrend — pullbacks are the setup", "green")
    if price > wma200:
        return ("Above long-term trend — constructive", "green")
    if price > wma50:
        return ("Repairing — below 200-week, watch closely", "orange")
    return ("Below long-term trend — falling-knife check required", "red")


def trend_readout(df: pd.DataFrame) -> dict:
    """Automated chart reading: price vs MAs, MA vs MA, crossovers, MA slope,
    distance from 52-week high. Returns {'regime': str, 'bullets': [str]}."""
    d = df.dropna(subset=["Close"])
    bullets: list[str] = []
    if d.empty:
        return {"regime": "Not enough data", "bullets": bullets}
    last = d.iloc[-1]
    price = float(last["Close"])

    def _pct(a, b):
        return (a / b - 1) * 100 if b else float("nan")

    # Price vs daily MAs
    for col, label in (("MA50", "50-day"), ("MA200", "200-day")):
        v = last.get(col, np.nan)
        if col in d and not np.isnan(v):
            p = _pct(price, float(v))
            side = "above" if p >= 0 else "below"
            bullets.append(f"Price is **{abs(p):.1f}% {side}** the {label} moving average "
                           f"(${float(v):,.2f}).")

    # Golden/death cross + recent crossover
    if "MA50" in d and "MA200" in d:
        s = (d["MA50"] - d["MA200"]).dropna()
        if len(s) >= 2 and not np.isnan(s.iloc[-1]):
            cur = float(np.sign(s.iloc[-1]))
            if cur > 0:
                state = "**Golden cross** — 50-day above 200-day"
            elif cur < 0:
                state = "**Death cross** — 50-day below 200-day"
            else:
                state = "50-day and 200-day are effectively tied"
            cross_date = None
            for i in range(len(s) - 2, -1, -1):
                if float(np.sign(s.iloc[i])) not in (cur, 0.0):
                    cross_date = s.index[i + 1]
                    break
            if cross_date is not None and (s.index[-1] - cross_date).days <= 120:
                kind = "golden cross" if cur > 0 else "death cross"
                state += f" — the {kind} fired on {cross_date.strftime('%Y-%m-%d')}"
            bullets.append(state + ".")

    # MA50 slope
    if "MA50" in d:
        m = d["MA50"].dropna()
        if len(m) >= 22:
            chg = (m.iloc[-1] / m.iloc[-22] - 1) * 100
            direction = "rising" if chg >= 0 else "falling"
            bullets.append(f"The 50-day average is **{direction}** ({chg:+.1f}% over the last month).")

    # Weekly picture
    for col, label in (("WMA50", "50-week"), ("WMA200", "200-week")):
        v = last.get(col, np.nan)
        if col in d and not np.isnan(v):
            p = _pct(price, float(v))
            side = "above" if p >= 0 else "below"
            bullets.append(f"Price is **{abs(p):.1f}% {side}** the {label} average "
                           f"(${float(v):,.2f}).")
    if "WMA50" in d and "WMA200" in d:
        a, b = last.get("WMA50", np.nan), last.get("WMA200", np.nan)
        if not np.isnan(a) and not np.isnan(b):
            p = _pct(float(a), float(b))
            rel = "above" if p >= 0 else "below"
            bullets.append(f"The 50-week average sits **{abs(p):.1f}% {rel}** the 200-week average.")

    # Distance from 52-week high
    if "High" in d:
        hi = float(d["High"].iloc[-260:].max())
        off = (price / hi - 1) * 100
        bullets.append(f"**{abs(off):.1f}% below** the 52-week high (${hi:,.2f}).")

    regime_text, _ = regime(price, last.get("WMA50", np.nan), last.get("WMA200", np.nan))
    return {"regime": regime_text, "bullets": bullets}


def vpvr(df: pd.DataFrame, bins: int = 36) -> pd.DataFrame:
    """Volume profile by price: volume traded in each price bin."""
    lo, hi = df["Low"].min(), df["High"].max()
    edges = np.linspace(lo, hi, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    vol = np.zeros(bins)
    mids = ((df["High"] + df["Low"] + df["Close"]) / 3).to_numpy()
    v = df["Volume"].to_numpy()
    idx = np.clip(np.digitize(mids, edges) - 1, 0, bins - 1)
    np.add.at(vol, idx, v)
    prof = pd.DataFrame({"price": centers, "volume": vol}).sort_values("price")
    prof["poc"] = prof["price"].iloc[prof["volume"].idxmax()]
    return prof


def accumulation_distribution(df: pd.DataFrame) -> pd.Series:
    rng = df["High"] - df["Low"]
    mfm = np.where(rng == 0, 0,
                   ((df["Close"] - df["Low"]) - (df["High"] - df["Close"])) / rng)
    return pd.Series(mfm * df["Volume"], index=df.index).cumsum().rename("AD")


def cmf(df: pd.DataFrame, window: int = 20) -> pd.Series:
    rng = df["High"] - df["Low"]
    mfm = np.where(rng == 0, 0,
                   ((df["Close"] - df["Low"]) - (df["High"] - df["Close"])) / rng)
    mfv = pd.Series(mfm * df["Volume"], index=df.index)
    return (mfv.rolling(window).sum() / df["Volume"].rolling(window).sum()).rename(f"CMF{window}")


def relative_strength(price: pd.Series, bench: pd.Series) -> pd.Series:
    j = pd.DataFrame({"p": price, "b": bench}).dropna()
    if j.empty:
        return pd.Series(dtype=float)
    rs = j["p"] / j["b"]
    return (rs / rs.iloc[0] * 100).rename("RS")


def drawdown_stats(close: pd.Series) -> dict:
    run_max = close.cummax()
    dd = (close - run_max) / run_max
    trough = dd.idxmin()
    max_dd = float(dd.min())
    rec = close.loc[trough:][close.loc[trough:] >= run_max.loc[trough]]
    days_to_recover = int((rec.index[0] - trough).days) if not rec.empty else None
    out = {"max_drawdown": max_dd, "trough": trough,
           "days_to_recover": days_to_recover, "series": dd}
    for label, w in (("1y", 252), ("3y", 756), ("5y", 1260)):
        if len(close) > w:
            worst = float((close / close.shift(w) - 1).min())
            wdate = (close / close.shift(w) - 1).idxmin()
        else:
            worst, wdate = None, None
        out[f"worst_{label}"] = worst
        out[f"worst_{label}_end"] = wdate
    return out


def swing_low(df: pd.DataFrame, lookback: int = 252) -> float:
    return float(df["Low"].iloc[-lookback:].min())


def wyckoff_flags(df: pd.DataFrame) -> list[dict]:
    """Heuristic accumulation-structure flags. Educational, not confirmed analysis."""
    flags = []
    d = df.iloc[-260:].copy()
    if len(d) < 130:
        return flags
    roll_low = d["Low"].rolling(60).min()
    roll_high = d["High"].rolling(60).max()
    avg_vol = d["Volume"].rolling(20).mean()
    for i in range(60, len(d)):
        row, dt = d.iloc[i], d.index[i]
        # Spring: wick below 60-day low, closes back inside the range
        if row["Low"] < roll_low.iloc[i - 1] and row["Close"] > roll_low.iloc[i - 1]:
            flags.append({"date": dt, "type": "Spring?",
                          "note": "Wick pierced the range low but closed back inside — possible shakeout."})
        # Sign of strength: breakout over 60-day high on expanding volume
        if row["Close"] > roll_high.iloc[i - 1] and row["Volume"] > 1.5 * avg_vol.iloc[i]:
            flags.append({"date": dt, "type": "Breakout",
                          "note": "Close above 60-day high on 1.5x average volume."})
        # Test: narrow-range down day holding above a recent spring low
        springs = [f["date"] for f in flags if f["type"] == "Spring?"]
        if springs and (row["High"] - row["Low"]) / row["Close"] < 0.015 and row["Low"] > d.loc[springs[-1]:]["Low"].min() * 0.99:
            if not any(f["type"] == "Test?" and (dt - f["date"]).days < 20 for f in flags):
                flags.append({"date": dt, "type": "Test?",
                              "note": "Narrow-range pullback holding above the spring low — possible absorption test."})
    # keep only recent 12 months of flags, newest last
    cutoff = d.index[-1] - pd.Timedelta(days=365)
    return [f for f in flags if f["date"] >= cutoff][-12:]
