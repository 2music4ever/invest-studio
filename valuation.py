"""Valuation math: DCF builder, scenarios, reverse DCF, margin of safety."""
import numpy as np
import pandas as pd


def dcf(revenue0: float, g_early: float, g_late: float, fcf_margin: float,
        discount: float, terminal_g: float, net_debt: float, shares: float,
        yrs_early: int = 5, yrs_late: int = 5,
        fcf_margin_norm: float | None = None, norm_years: int = 5):
    """Two-stage DCF on revenue -> FCF. Returns (per_share, enterprise_value, schedule).

    fcf_margin_norm: optional mid-cycle FCF margin. When set, the yearly FCF margin
    converges linearly from `fcf_margin` toward `fcf_margin_norm` over `norm_years`,
    then stays flat — so a peak-capex year doesn't anchor the whole decade, and the
    terminal value reflects normalized earning power.
    """
    if discount <= terminal_g:
        raise ValueError("Discount rate must exceed terminal growth.")

    def margin_at(t: int) -> float:
        if fcf_margin_norm is None or norm_years <= 0:
            return fcf_margin
        w = min(t, norm_years) / norm_years
        return fcf_margin + (fcf_margin_norm - fcf_margin) * w

    revs, fcfs, margins = [], [], []
    rev = revenue0
    for t in range(1, yrs_early + yrs_late + 1):
        rev *= 1 + (g_early if t <= yrs_early else g_late)
        m = margin_at(t)
        revs.append(rev)
        margins.append(m)
        fcfs.append(rev * m)
    n = yrs_early + yrs_late
    pv = sum(f / (1 + discount) ** i for i, f in enumerate(fcfs, 1))
    term = fcfs[-1] * (1 + terminal_g) / (discount - terminal_g)
    ev = pv + term / (1 + discount) ** n
    per_share = (ev - net_debt) / shares
    sched = pd.DataFrame({
        "Year": range(1, n + 1),
        "Revenue": revs,
        "FCF margin": margins,
        "FCF": fcfs,
        "PV of FCF": [f / (1 + discount) ** i for i, f in enumerate(fcfs, 1)],
    })
    return per_share, ev, sched


def reverse_dcf(price: float, revenue0: float, fcf_margin: float,
                discount: float, terminal_g: float, net_debt: float,
                shares: float, lo: float = -0.05, hi: float = 0.40,
                fcf_margin_norm: float | None = None, norm_years: int = 5):
    """Uniform 10-yr growth rate the current price implies. None if unsolvable."""
    def value_at(g):
        try:
            v, _, _ = dcf(revenue0, g, g, fcf_margin, discount,
                          terminal_g, net_debt, shares,
                          fcf_margin_norm=fcf_margin_norm, norm_years=norm_years)
            return v
        except ValueError:
            return np.nan
    vlo, vhi = value_at(lo), value_at(hi)
    if not (np.isfinite(vlo) and np.isfinite(vhi)) or not (vlo <= price <= vhi):
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if value_at(mid) < price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def margin_of_safety(iv: float, price: float) -> float | None:
    if not iv or iv <= 0 or not price:
        return None
    return (iv - price) / iv


def mos_label(mos: float | None) -> str:
    if mos is None:
        return "n/a"
    if mos >= 0.30:
        return "Deep value zone"
    if mos >= 0.15:
        return "Margin of safety"
    if mos >= -0.10:
        return "Fairly valued"
    return "Priced for perfection"
