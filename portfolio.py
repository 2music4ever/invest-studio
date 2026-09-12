"""Portfolio optimization: mean-variance, max Sortino, min max-drawdown.

All inputs are daily total-return series (dividend/split adjusted). Optimizers
are long-only by default; weights sum to 1.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize

TRADING_DAYS = 252


def get_returns(tickers, period="5y"):
    """Aligned daily simple returns for tickers. Returns (rets, dropped)."""
    import data as D

    closes = {}
    dropped = []
    for t in tickers:
        try:
            h = D.get_history(t, period)
        except Exception:
            h = pd.DataFrame()
        if h is None or h.empty or "Close" not in h:
            dropped.append(t)
            continue
        closes[t] = h["Close"]
    if len(closes) < 2:
        return pd.DataFrame(), tickers
    px = pd.DataFrame(closes).dropna()
    rets = px.pct_change().dropna()
    return rets, dropped


def annualized(rets):
    mu = rets.mean() * TRADING_DAYS
    sigma = rets.cov() * TRADING_DAYS
    return mu, sigma


def _starts(n, rng):
    s = [np.full(n, 1.0 / n)]
    for _ in range(4):
        x = rng.random(n)
        s.append(x / x.sum())
    return s


def _bounds(n, max_w, long_only):
    lo = 0.0 if long_only else -max_w
    return [(lo, max_w)] * n


def _sum_to_one(n):
    return {"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}


def max_sharpe(mu, sigma, max_w=0.5, long_only=True):
    n = len(mu)
    mu_v = np.asarray(mu, dtype=float)
    cov = np.asarray(sigma, dtype=float)

    def neg_sharpe(w):
        vol = float(np.sqrt(max(w @ cov @ w, 1e-12)))
        return -float(mu_v @ w) / vol

    rng = np.random.default_rng(7)
    best, best_val = None, np.inf
    for x0 in _starts(n, rng):
        r = minimize(neg_sharpe, x0, method="SLSQP",
                     bounds=_bounds(n, max_w, long_only),
                     constraints=[_sum_to_one(n)],
                     options={"maxiter": 500, "ftol": 1e-9})
        if r.success and r.fun < best_val:
            best, best_val = r.x, r.fun
    return _clean(best, n)


def efficient_frontier(mu, sigma, max_w=0.5, long_only=True, points=40):
    n = len(mu)
    mu_v = np.asarray(mu, dtype=float)
    cov = np.asarray(sigma, dtype=float)
    lo, hi = float(mu_v.min()), float(mu_v.max())
    if hi - lo < 1e-6:
        hi = lo + 0.01
    targets = np.linspace(lo, hi, points)
    out = []
    for t in targets:
        cons = [_sum_to_one(n),
                {"type": "eq", "fun": lambda w, t=t: float(mu_v @ w - t)}]
        r = minimize(lambda w: float(w @ cov @ w), np.full(n, 1.0 / n),
                     method="SLSQP", bounds=_bounds(n, max_w, long_only),
                     constraints=cons, options={"maxiter": 500, "ftol": 1e-9})
        if r.success:
            out.append((float(np.sqrt(max(r.fun, 0))), float(t)))
    return pd.DataFrame(out, columns=["vol", "ret"])


def max_sortino(rets, mar=0.0, max_w=0.5, long_only=True):
    n = rets.shape[1]
    R = rets.to_numpy(dtype=float)
    mar_d = mar / TRADING_DAYS

    def neg_sortino(w):
        rp = R @ w
        ann_ret = float(rp.mean() * TRADING_DAYS)
        dd = float(np.sqrt(np.mean(np.minimum(0.0, rp - mar_d) ** 2)) * np.sqrt(TRADING_DAYS))
        return -(ann_ret - mar) / (dd + 1e-12)

    rng = np.random.default_rng(11)
    best, best_val = None, np.inf
    for x0 in _starts(n, rng):
        r = minimize(neg_sortino, x0, method="SLSQP",
                     bounds=_bounds(n, max_w, long_only),
                     constraints=[_sum_to_one(n)],
                     options={"maxiter": 500, "ftol": 1e-9})
        if r.fun < best_val:
            best, best_val = r.x, r.fun
    return _clean(best, n)


def min_max_drawdown(rets, min_ann_ret=None, max_w=0.5, long_only=True):
    n = rets.shape[1]
    R = rets.to_numpy(dtype=float)

    def max_dd(w):
        cum = np.cumprod(1.0 + R @ w)
        dd = cum / np.maximum.accumulate(cum) - 1.0
        return float(-dd.min())

    cons = [_sum_to_one(n)]
    if min_ann_ret is not None:
        cons.append({"type": "ineq",
                     "fun": lambda w: float((R @ w).mean() * TRADING_DAYS - min_ann_ret)})
    rng = np.random.default_rng(13)
    best, best_val = None, np.inf
    for x0 in _starts(n, rng):
        r = minimize(max_dd, x0, method="SLSQP",
                     bounds=_bounds(n, max_w, long_only),
                     constraints=cons, options={"maxiter": 1000, "ftol": 1e-9})
        if r.fun < best_val:
            best, best_val = r.x, r.fun
    return _clean(best, n)


def _clean(w, n):
    if w is None:
        return np.full(n, 1.0 / n)
    w = np.asarray(w, dtype=float)
    w[np.abs(w) < 1e-4] = 0.0
    s = w.sum()
    return w / s if s > 1e-9 else np.full(n, 1.0 / n)


def stats(w, rets, mar=0.0):
    R = rets.to_numpy(dtype=float)
    rp = R @ w
    ann_ret = float(rp.mean() * TRADING_DAYS)
    ann_vol = float(rp.std(ddof=1) * np.sqrt(TRADING_DAYS))
    sharpe = ann_ret / ann_vol if ann_vol > 1e-9 else 0.0
    mar_d = mar / TRADING_DAYS
    dd_dev = float(np.sqrt(np.mean(np.minimum(0.0, rp - mar_d) ** 2)) * np.sqrt(TRADING_DAYS))
    sortino = (ann_ret - mar) / dd_dev if dd_dev > 1e-9 else 0.0
    cum = np.cumprod(1.0 + rp)
    mdd = float((cum / np.maximum.accumulate(cum) - 1.0).min())
    return {"ann_ret": ann_ret, "ann_vol": ann_vol, "sharpe": sharpe,
            "sortino": sortino, "max_dd": mdd}


def growth(w, rets, start=10000.0):
    rp = rets.to_numpy(dtype=float) @ np.asarray(w, dtype=float)
    return pd.Series(start * np.cumprod(1.0 + rp), index=rets.index)
