# Invest Studio

Long-term investing workbench — valuation modeling, accumulation footprints,
and entry planning. Built for 1/3/5-year holds, not trading.

## Tabs

- **Chart & Trend** — price with 20/50/200-day and 50/200-week MAs, trend-regime
  badge, historical P/E percentile bands, key stats.
- **Valuation Lab** — DCF builder with your assumptions (revenue growth, FCF
  margin, discount rate, terminal growth), margin-of-safety gauge, bear/base/bull
  scenarios, reverse DCF (growth the price implies), year-by-year schedule.
- **Accumulation** — volume profile (VPVR) with point of control, A/D line,
  Chaikin Money Flow, heuristic Wyckoff-structure flags.
- **Dislocation** — consensus price targets, EPS estimate trends and revision
  breadth, analyst ratings, estimate-vs-price divergence verdict, relative
  strength vs S&P 500 and sector.
- **Entry Planner** — tranche planner (current price / 200-week MA / volume POC /
  52-week low) with blended cost and upside, drawdown & pain-threshold simulator
  (max drawdown, recovery, worst 1/3/5-yr holds), downloadable research note.

## Data

Yahoo Finance via `yfinance` (free, no key). P/E history blends annual EPS with
recent TTM EPS — an approximation, shown as percentile bands.

## Run locally

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

For education and research only — not investment advice.
