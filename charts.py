"""Plotly chart builders — professional dark theme for Invest Studio."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ---- Professional palette ----
GOLD = "#D4A94B"    # brand accent / primary price line
BLUE = "#5B8DEF"    # primary data series
VIOLET = "#9D7BEA"  # secondary series
TEAL = "#2FBF71"    # up / positive
RED = "#E5544A"     # down / negative
AMBER = "#E8A33D"   # highlights (POC, thresholds)
GRAY = "#9AA4B2"    # neutral
INK = "#E9ECF3"     # primary text
GRID = "rgba(255,255,255,0.07)"

_FONT = dict(family="Inter, -apple-system, 'Segoe UI', sans-serif", color=INK)


def _apply(fig: go.Figure) -> go.Figure:
    """Shared professional styling: transparent surfaces, Inter type, subtle grid."""
    fig.update_layout(
        font=_FONT,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor=GRID, zeroline=False),
        yaxis=dict(gridcolor=GRID, zeroline=False),
    )
    return fig


def sensitivity_heatmap(grid: pd.DataFrame, price: float) -> go.Figure:
    """VC sensitivity grid as a styled heatmap, centered on the current price."""
    z = grid.to_numpy(dtype=float)
    fig = go.Figure(go.Heatmap(
        z=z,
        x=list(grid.columns),
        y=list(grid.index),
        colorscale=[[0.0, "#5C2320"], [0.5, "#1A1F2B"], [1.0, "#1D5C3A"]],
        zmid=price,
        texttemplate="$%{z:,.0f}",
        textfont=dict(size=12, color=INK),
        hovertemplate="Growth %{y}<br>Exit %{x}<br>Value $%{z:,.0f}<extra></extra>",
        colorbar=dict(title="Value / share"),
    ))
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=16, b=10),
                      yaxis=dict(autorange="reversed"))
    return _apply(fig)


def price_chart(df: pd.DataFrame) -> go.Figure:
    d = df  # caller controls the visible window via the range pills
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25],
                        vertical_spacing=0.03)
    fig.add_trace(go.Scatter(x=d.index, y=d["Close"], name="Price",
                             line=dict(color=GOLD, width=1.6)), row=1, col=1)
    for col, color, dash in (("MA50", BLUE, "solid"), ("MA200", VIOLET, "solid"),
                             ("WMA50", TEAL, "dash"), ("WMA200", RED, "dash")):
        if col in d and d[col].notna().any():
            fig.add_trace(go.Scatter(x=d.index, y=d[col], name=col,
                                     line=dict(color=color, width=1.1, dash=dash),
                                     opacity=0.9), row=1, col=1)
    colors = np.where(d["Close"] >= d["Open"], TEAL, RED)
    fig.add_trace(go.Bar(x=d.index, y=d["Volume"], name="Volume",
                         marker_color=colors, opacity=0.45), row=2, col=1)
    fig.update_layout(height=560, margin=dict(l=10, r=10, t=30, b=10),
                      legend=dict(orientation="h", y=1.02),
                      template="plotly_dark")
    fig.update_xaxes(rangeslider_visible=False)
    return _apply(fig)


def valuation_bands(pe: pd.DataFrame) -> go.Figure | None:
    if pe.empty or len(pe) < 10:
        return None
    p = pe.copy()
    for q, name in ((0.1, "p10"), (0.25, "p25"), (0.5, "p50"), (0.75, "p75"), (0.9, "p90")):
        p[name] = p["pe"].expanding().quantile(q)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=p.index, y=p["pe"], name="P/E (TTM)",
                             line=dict(color=GOLD, width=1.6)))
    fig.add_trace(go.Scatter(x=p.index, y=p["p90"], name="90th %ile",
                             line=dict(color=RED, dash="dash", width=1)))
    fig.add_trace(go.Scatter(x=p.index, y=p["p50"], name="Median",
                             line=dict(color=GRAY, dash="dot", width=1)))
    fig.add_trace(go.Scatter(x=p.index, y=p["p10"], name="10th %ile",
                             line=dict(color=TEAL, dash="dash", width=1)))
    fig.add_trace(go.Scatter(x=p.index, y=p["p10"], fill="tonexty",
                             fillcolor="rgba(47,191,113,0.10)",
                             line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10),
                      template="plotly_dark", legend=dict(orientation="h", y=1.02))
    return _apply(fig)


def fundamentals_chart(df: pd.DataFrame, a: str, b: str | None, meta: dict) -> go.Figure:
    """Dual-axis fundamental chart: `a` as bars (left axis), optional `b` as a
    line (right axis). meta[key] = (label, unit) with unit in {'$B', '$', '%'}."""
    def scaled(key):
        label, unit = meta[key]
        s = df[key] / 1e9 if unit == "$B" else df[key]
        fmt = ".0%" if unit == "%" else (".1f" if unit == "$B" else ",.0f")
        title = label if unit == "%" else f"{label} ({unit})"
        return s, fmt, title, label

    ya, yfmt, ytitle, la = scaled(a)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["label"], y=ya, name=la, marker_color=BLUE,
                         opacity=0.8, yaxis="y"))
    layout = dict(height=400, margin=dict(l=10, r=10, t=40, b=10), template="plotly_dark",
                  legend=dict(orientation="h", y=1.02),
                  yaxis=dict(title=ytitle, tickformat=yfmt))
    if b:
        yb, ybfmt, ybtitle, lb = scaled(b)
        fig.add_trace(go.Scatter(x=df["label"], y=yb, name=lb, mode="lines+markers",
                                 line=dict(color=GOLD, width=2.5), yaxis="y2"))
        layout["yaxis2"] = dict(title=ybtitle, tickformat=ybfmt, overlaying="y",
                                side="right", showgrid=False)
    fig.update_layout(**layout)
    return _apply(fig)


def vpvr_chart(prof: pd.DataFrame, price_now: float) -> go.Figure:
    fig = go.Figure()
    colors = [AMBER if abs(p - prof["poc"].iloc[0]) < (prof["price"].max() - prof["price"].min()) / 72
              else BLUE for p in prof["price"]]
    fig.add_trace(go.Bar(y=prof["price"], x=prof["volume"], orientation="h",
                         marker_color=colors, opacity=0.75, name="Volume at price"))
    fig.add_hline(y=prof["poc"].iloc[0], line_dash="dash", line_color=AMBER,
                  annotation_text=f"POC {prof['poc'].iloc[0]:.2f}")
    fig.add_hline(y=price_now, line_color=RED,
                  annotation_text=f"Now {price_now:.2f}")
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10),
                      template="plotly_dark", xaxis_title="Volume", yaxis_title="Price")
    return _apply(fig)


def flow_chart(df: pd.DataFrame) -> go.Figure:
    d = df.iloc[-750:]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.5, 0.5],
                        vertical_spacing=0.06)
    fig.add_trace(go.Scatter(x=d.index, y=d["AD"], name="A/D line",
                             line=dict(color=VIOLET, width=1.4)), row=1, col=1)
    for col, color in (("CMF20", BLUE), ("CMF60", TEAL)):
        if col in d:
            fig.add_trace(go.Scatter(x=d.index, y=d[col], name=col,
                                     line=dict(color=color, width=1.2)), row=2, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color=GRAY, row=2, col=1)
    fig.update_layout(height=460, margin=dict(l=10, r=10, t=40, b=10),
                      template="plotly_dark", legend=dict(orientation="h", y=1.08))
    return _apply(fig)


def rs_chart(rs_stock: pd.Series, rs_sector: pd.Series | None) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rs_stock.index, y=rs_stock, name="vs S&P 500",
                             line=dict(color=GOLD, width=1.6)))
    if rs_sector is not None and not rs_sector.empty:
        fig.add_trace(go.Scatter(x=rs_sector.index, y=rs_sector, name="vs sector",
                                 line=dict(color=BLUE, width=1.4)))
    fig.add_hline(y=100, line_dash="dot", line_color=GRAY)
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10),
                      template="plotly_dark", legend=dict(orientation="h", y=1.02))
    return _apply(fig)


def target_range(lo, mean, hi, price=None):
    """Horizontal analyst target-range bar with labeled Low/Mean/High markers."""
    fig = go.Figure()
    span = max(hi - lo, lo * 0.02)
    pad = span * 0.22
    fig.add_shape(type="line", x0=lo, x1=hi, y0=0, y1=0,
                  line=dict(color="rgba(150,150,150,0.9)", width=12))
    for x, name in ((lo, "Low"), (mean, "Mean"), (hi, "High")):
        fig.add_trace(go.Scatter(x=[x], y=[0], mode="markers", showlegend=False,
                                 hovertemplate=f"{name}: $%{{x:,.0f}}<extra></extra>",
                                 marker=dict(size=15, color=GOLD,
                                             line=dict(color="black", width=1))))
        fig.add_annotation(x=x, y=0, text=f"<b>{name}</b><br>${x:,.0f}",
                           showarrow=False, yshift=-42,
                           font=dict(size=13, color=INK), align="center")
    if price:
        fig.add_vline(x=price, line_dash="dash", line_color=INK, opacity=0.85)
        fig.add_annotation(x=price, y=0, text=f"<b>Now</b><br>${price:,.0f}",
                           showarrow=False, yshift=44,
                           font=dict(size=13, color=INK),
                           bgcolor="rgba(0,0,0,0.65)", borderpad=4, align="center")
    fig.update_xaxes(range=[lo - pad, hi + pad])
    fig.update_yaxes(range=[-1.2, 1.2], showticklabels=False, zeroline=False)
    fig.update_layout(height=260, margin=dict(t=36, b=44, l=10, r=10),
                      font_color=INK,
                      template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return _apply(fig)


def mos_gauge(mos: float | None, iv: float, price: float) -> go.Figure:
    val = max(-0.6, min(0.6, mos if mos is not None else 0))
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val * 100,
        number={"suffix": "%", "font": {"size": 34}},
        title={"text": f"Margin of safety<br><span style='font-size:13px'>IV ${iv:,.2f} vs price ${price:,.2f}</span>"},
        gauge={"axis": {"range": [-60, 60]},
               "bar": {"color": GOLD},
               "steps": [{"range": [-60, -10], "color": "rgba(229,84,74,0.22)"},
                         {"range": [-10, 15], "color": "rgba(154,164,178,0.18)"},
                         {"range": [15, 60], "color": "rgba(47,191,113,0.22)"}],
               "threshold": {"line": {"color": AMBER, "width": 3}, "value": 0}}))
    fig.update_layout(height=320, margin=dict(l=20, r=20, t=60, b=10),
                      template="plotly_dark")
    return _apply(fig)


def scenario_bars(scenarios: pd.DataFrame, price: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=scenarios["Scenario"], y=scenarios["IV"],
                         marker_color=[RED, BLUE, TEAL],
                         text=[f"${v:,.0f}" for v in scenarios["IV"]],
                         textposition="outside", name="Intrinsic value"))
    fig.add_hline(y=price, line_dash="dash", line_color=AMBER,
                  annotation_text=f"Current ${price:,.2f}")
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10),
                      template="plotly_dark", yaxis_title="Per-share value ($)")
    return _apply(fig)


def bridge_chart(items: list[tuple[str, float]], total: float) -> go.Figure:
    """Waterfall of expected-return components (fractions) summing to the total."""
    fig = go.Figure(go.Waterfall(
        x=[k for k, _ in items] + ["Expected return"],
        y=[v * 100 for _, v in items] + [total * 100],
        measure=["relative"] * len(items) + ["total"],
        connector={"line": {"color": GRAY}},
        increasing=dict(marker=dict(color=TEAL)),
        decreasing=dict(marker=dict(color=RED)),
        totals=dict(marker=dict(color=GOLD)),
    ))
    fig.update_layout(template="plotly_dark",
                      height=380, margin=dict(l=10, r=10, t=24, b=10),
                      yaxis_title="% per year")
    return _apply(fig)


def roic_chart(df: pd.DataFrame) -> go.Figure:
    """Annual ROIC bars."""
    fig = go.Figure(go.Bar(x=df["Year"], y=df["ROIC"] * 100, name="ROIC",
                           marker_color=TEAL, opacity=0.85))
    fig.update_layout(template="plotly_dark", height=320,
                      margin=dict(l=10, r=10, t=24, b=10), yaxis_title="%")
    return _apply(fig)
