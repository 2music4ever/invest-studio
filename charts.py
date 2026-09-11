"""Plotly chart builders."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def price_chart(df: pd.DataFrame) -> go.Figure:
    d = df  # caller controls the visible window via the range pills
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25],
                        vertical_spacing=0.03)
    fig.add_trace(go.Scatter(x=d.index, y=d["Close"], name="Price",
                             line=dict(color="#4C8DFF", width=1.6)), row=1, col=1)
    for col, color, dash in (("MA50", "#FFB020", "solid"), ("MA200", "#B14CFF", "solid"),
                             ("WMA50", "#2DD4A7", "dash"), ("WMA200", "#FF5C5C", "dash")):
        if col in d and d[col].notna().any():
            fig.add_trace(go.Scatter(x=d.index, y=d[col], name=col,
                                     line=dict(color=color, width=1.1, dash=dash),
                                     opacity=0.9), row=1, col=1)
    colors = np.where(d["Close"] >= d["Open"], "#2DD4A7", "#FF5C5C")
    fig.add_trace(go.Bar(x=d.index, y=d["Volume"], name="Volume",
                         marker_color=colors, opacity=0.45), row=2, col=1)
    fig.update_layout(height=560, margin=dict(l=10, r=10, t=30, b=10),
                      legend=dict(orientation="h", y=1.02),
                      template="plotly_dark")
    fig.update_xaxes(rangeslider_visible=False)
    return fig


def valuation_bands(pe: pd.DataFrame, forward_pe: float | None = None) -> go.Figure | None:
    if pe.empty or len(pe) < 10:
        return None
    p = pe.copy()
    for q, name in ((0.1, "p10"), (0.25, "p25"), (0.5, "p50"), (0.75, "p75"), (0.9, "p90")):
        p[name] = p["pe"].expanding().quantile(q)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=p.index, y=p["pe"], name="P/E (TTM)",
                             line=dict(color="#4C8DFF", width=1.6)))
    fig.add_trace(go.Scatter(x=p.index, y=p["p90"], name="90th %ile",
                             line=dict(color="#FF5C5C", dash="dash", width=1)))
    fig.add_trace(go.Scatter(x=p.index, y=p["p50"], name="Median",
                             line=dict(color="#9AA4B2", dash="dot", width=1)))
    fig.add_trace(go.Scatter(x=p.index, y=p["p10"], name="10th %ile",
                             line=dict(color="#2DD4A7", dash="dash", width=1)))
    fig.add_trace(go.Scatter(x=p.index, y=p["p10"], fill="tonexty",
                             fillcolor="rgba(45,212,167,0.10)",
                             line=dict(width=0), showlegend=False, hoverinfo="skip"))
    if forward_pe:
        fig.add_hline(y=forward_pe, line_dash="dash", line_color="#FFB020", line_width=1.4,
                      annotation_text=f"Forward P/E {forward_pe:.1f} (current)",
                      annotation_font_color="#FFB020")
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10),
                      title="Historical P/E with percentile bands — dips under the 10th percentile are the valuation zone",
                      template="plotly_dark", legend=dict(orientation="h", y=1.02))
    return fig


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
    fig.add_trace(go.Bar(x=df["label"], y=ya, name=la, marker_color="#4C8DFF",
                         opacity=0.8, yaxis="y"))
    layout = dict(height=400, margin=dict(l=10, r=10, t=40, b=10), template="plotly_dark",
                  legend=dict(orientation="h", y=1.02),
                  yaxis=dict(title=ytitle, tickformat=yfmt))
    if b:
        yb, ybfmt, ybtitle, lb = scaled(b)
        fig.add_trace(go.Scatter(x=df["label"], y=yb, name=lb, mode="lines+markers",
                                 line=dict(color="#FFB020", width=2.5), yaxis="y2"))
        layout["yaxis2"] = dict(title=ybtitle, tickformat=ybfmt, overlaying="y",
                                side="right", showgrid=False)
        layout["title"] = f"{la} vs {lb} — fiscal periods"
    else:
        layout["title"] = f"{la} — fiscal periods"
    fig.update_layout(**layout)
    return fig


def vpvr_chart(prof: pd.DataFrame, price_now: float) -> go.Figure:
    fig = go.Figure()
    colors = ["#FFB020" if abs(p - prof["poc"].iloc[0]) < (prof["price"].max() - prof["price"].min()) / 72
              else "#4C8DFF" for p in prof["price"]]
    fig.add_trace(go.Bar(y=prof["price"], x=prof["volume"], orientation="h",
                         marker_color=colors, opacity=0.75, name="Volume at price"))
    fig.add_hline(y=prof["poc"].iloc[0], line_dash="dash", line_color="#FFB020",
                  annotation_text=f"POC {prof['poc'].iloc[0]:.2f}")
    fig.add_hline(y=price_now, line_color="#FF5C5C",
                  annotation_text=f"Now {price_now:.2f}")
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10),
                      title="Volume profile (VPVR) — tallest bars are institutional support zones",
                      template="plotly_dark", xaxis_title="Volume", yaxis_title="Price")
    return fig


def flow_chart(df: pd.DataFrame) -> go.Figure:
    d = df.iloc[-750:]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.5, 0.5],
                        vertical_spacing=0.06)
    fig.add_trace(go.Scatter(x=d.index, y=d["AD"], name="A/D line",
                             line=dict(color="#B14CFF", width=1.4)), row=1, col=1)
    for col, color in (("CMF20", "#4C8DFF"), ("CMF60", "#2DD4A7")):
        if col in d:
            fig.add_trace(go.Scatter(x=d.index, y=d[col], name=col,
                                     line=dict(color=color, width=1.2)), row=2, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="#9AA4B2", row=2, col=1)
    fig.update_layout(height=460, margin=dict(l=10, r=10, t=30, b=10),
                      title="Accumulation/Distribution + Chaikin Money Flow (smoothed)",
                      template="plotly_dark", legend=dict(orientation="h", y=1.08))
    return fig


def rs_chart(rs_stock: pd.Series, rs_sector: pd.Series | None) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rs_stock.index, y=rs_stock, name="vs S&P 500",
                             line=dict(color="#4C8DFF", width=1.6)))
    if rs_sector is not None and not rs_sector.empty:
        fig.add_trace(go.Scatter(x=rs_sector.index, y=rs_sector, name="vs sector",
                                 line=dict(color="#FFB020", width=1.4)))
    fig.add_hline(y=100, line_dash="dot", line_color="#9AA4B2")
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10),
                      title="Relative strength (rebased to 100) — rising = hidden demand",
                      template="plotly_dark", legend=dict(orientation="h", y=1.02))
    return fig


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
                                 marker=dict(size=15, color="#4C8DFF",
                                             line=dict(color="black", width=1))))
        fig.add_annotation(x=x, y=0, text=f"<b>{name}</b><br>${x:,.0f}",
                           showarrow=False, yshift=-42,
                           font=dict(size=13, color="white"), align="center")
    if price:
        fig.add_vline(x=price, line_dash="dash", line_color="white", opacity=0.85)
        fig.add_annotation(x=price, y=0, text=f"<b>Now</b><br>${price:,.0f}",
                           showarrow=False, yshift=44,
                           font=dict(size=13, color="white"),
                           bgcolor="rgba(0,0,0,0.65)", borderpad=4, align="center")
    fig.update_xaxes(range=[lo - pad, hi + pad])
    fig.update_yaxes(range=[-1.2, 1.2], showticklabels=False, zeroline=False)
    fig.update_layout(height=260, margin=dict(t=36, b=44, l=10, r=10),
                      title="Analyst price-target range (12-mo)", font_color="white",
                      template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def mos_gauge(mos: float | None, iv: float, price: float) -> go.Figure:
    val = max(-0.6, min(0.6, mos if mos is not None else 0))
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val * 100,
        number={"suffix": "%", "font": {"size": 34}},
        title={"text": f"Margin of safety<br><span style='font-size:13px'>IV ${iv:,.2f} vs price ${price:,.2f}</span>"},
        gauge={"axis": {"range": [-60, 60]},
               "bar": {"color": "#4C8DFF"},
               "steps": [{"range": [-60, -10], "color": "rgba(255,92,92,0.25)"},
                         {"range": [-10, 15], "color": "rgba(154,164,178,0.20)"},
                         {"range": [15, 60], "color": "rgba(45,212,167,0.25)"}],
               "threshold": {"line": {"color": "#FFB020", "width": 3}, "value": 0}}))
    fig.update_layout(height=320, margin=dict(l=20, r=20, t=60, b=10),
                      template="plotly_dark")
    return fig


def scenario_bars(scenarios: pd.DataFrame, price: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=scenarios["Scenario"], y=scenarios["IV"],
                         marker_color=["#FF5C5C", "#4C8DFF", "#2DD4A7"],
                         text=[f"${v:,.0f}" for v in scenarios["IV"]],
                         textposition="outside", name="Intrinsic value"))
    fig.add_hline(y=price, line_dash="dash", line_color="#FFB020",
                  annotation_text=f"Current ${price:,.2f}")
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10),
                      title="Bear / base / bull intrinsic values vs current price",
                      template="plotly_dark", yaxis_title="Per-share value ($)")
    return fig
