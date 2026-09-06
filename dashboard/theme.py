"""
Dark Plotly theme, registered once and applied to every figure via
template="dark". Colors and data-viz rules taken from the project's visual
identity guide: Slate background, Hairline grid on the value axis only,
Paper Muted mono text, a single accent leading each chart (Signal Blue by
default).

FONTS. The theme used to declare system fonts to keep a self-contained file.
Measured 2026-08-31: rendered on a machine without Arial Black, titles lose
their accents: the HTML does contain \\u00c9, the display shows "DEMANDEES".
The identity's three font families are now embedded in base64 (see
prepare_fonts.py); this module only declares their names, with a system
fallback in case the CSS doesn't load.
"""

import plotly.graph_objects as go
import plotly.io as pio

# Exact palette from the project's visual identity guide
VOID = "#0B0C0F"
SLATE = "#15171C"
SLATE_RAISED = "#1E2128"
HAIRLINE = "#2A2E37"
HAIRLINE_BRIGHT = "#3A404C"
PAPER = "#F2F3F5"
PAPER_MUTED = "#9BA1AC"

BLUE = "#4C8DFF"      # primary accent, single series by default
AMBER = "#FFC24B"     # second series (mandated pair: Blue + Amber)
VERMILION = "#FF6B5A" # negative delta only
GREEN = "#4ADE80"     # positive delta only
# Violet deliberately absent: reserved for CTAs, never for charts (skill rule)

TITLE_FONT = "'Archivo Black', 'Arial Black', sans-serif"
BODY_FONT = "'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif"
MONO_FONT = "'JetBrains Mono', 'SF Mono', 'Consolas', monospace"

_template = go.layout.Template()

_template.layout = go.Layout(
    paper_bgcolor=SLATE,
    plot_bgcolor=SLATE,
    font=dict(family=MONO_FONT, color=PAPER_MUTED, size=11),
    # NO TITLE IN THE FIGURE. Measured 2026-08-31: Plotly sizes its title box
    # on the height of capital letters, and accents that rise above it get
    # clipped -- "CATEGORIE" displayed without its accent even though the DOM
    # did contain É and the embedded font has the glyph (verified by
    # isolating HTML and SVG side by side). Titles now live in the HTML card,
    # where nothing clips them. It's also more consistent: in this system,
    # the card carries the label.
    title=dict(text=None),
    colorway=[BLUE, AMBER, VERMILION, GREEN],
    xaxis=dict(
        showgrid=False,
        showline=True,
        linecolor=HAIRLINE,
        tickfont=dict(family=MONO_FONT, color=PAPER_MUTED, size=10),
        ticks="",
        automargin=True,
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor=HAIRLINE,
        gridwidth=1,
        showline=False,
        tickfont=dict(family=MONO_FONT, color=PAPER_MUTED, size=10),
        ticks="",
        automargin=True,
    ),
    margin=dict(l=20, r=24, t=16, b=40, autoexpand=True),
    legend=dict(
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="left", x=0,
        font=dict(family=MONO_FONT, color=PAPER_MUTED, size=10),
        bgcolor="rgba(0,0,0,0)",
    ),
    hoverlabel=dict(
        bgcolor=SLATE_RAISED,
        bordercolor=HAIRLINE_BRIGHT,
        font=dict(family=MONO_FONT, color=PAPER, size=11),
    ),
    autosize=True,
)

pio.templates["dark"] = _template

_LABEL_FONT = dict(family=MONO_FONT, size=10, color=PAPER)


def horizontal_bar_chart(rows, cat_col, val_col, title, suffix="",
                         color=BLUE, height=None, note=None,
                         labels=None):
    """Horizontal bars: the default format as soon as labels get long.

    Vertical bars forced labels to tilt at 45 degrees; on the twelve domain
    clusters, they overlapped and overflowed the card. Horizontally, a label
    reads without rotation regardless of its length, and descending order
    becomes a natural top-to-bottom read.

    Plotly draws the first category at the bottom: we therefore sort
    ascending so the largest value ends up on top.
    """
    data = sorted(rows, key=lambda l: l[val_col])
    cats = [l[cat_col] for l in data]
    vals = [l[val_col] for l in data]

    if labels:
        texts = [labels[l[cat_col]] for l in data]
    else:
        texts = [f"{v:,.0f}{suffix}".replace(",", " ") for v in vals]

    fig = go.Figure(go.Bar(
        x=vals, y=cats,
        orientation="h",
        text=texts,
        textposition="outside",
        textfont=_LABEL_FONT,
        marker_color=color,
        cliponaxis=False,  # otherwise the longest bar's label gets clipped
        # Reuses `text` (already formatted with the suffix) rather than
        # reformatting %{x}: a single source of truth for the displayed
        # value, on the bar and in the tooltip. <extra></extra> removes the
        # "trace 0" box Plotly adds next to the tooltip by default.
        hovertemplate="<b>%{y}</b><br>%{text}<extra></extra>",
    ))
    fig.update_layout(
        template="dark",
        meta=dict(title=title, note=note),
        height=height or max(240, 42 * len(cats) + 60),
        xaxis=dict(showgrid=True, gridcolor=HAIRLINE, showline=False,
                   showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showline=False,
                   tickfont=dict(family=MONO_FONT, color=PAPER_MUTED, size=11)),
        # Margins computed from label length rather than fixed, on both left
        # and right. The right one already existed (value labels sticking
        # out past the bars); the left one was missing, and a category name
        # like "Databricks" (10 characters) got truncated by a fixed 20px
        # margin calibrated for short acronyms (measured 2026-09-04, see
        # session report). JetBrains Mono is monospaced: a label's width is
        # exactly proportional to its character count.
        margin=dict(l=24 + 7 * max(len(str(c)) for c in cats),
                    r=30 + 7 * max(len(t) for t in texts),
                    t=16, b=16, autoexpand=True),
    )
    return fig


def column_chart(rows, cat_col, val_col, title, y_title="", suffix="",
                 color=BLUE, height=340, note=None, labels=None):
    """Vertical columns: reserved for a small number of short categories.

    A single hue, direct labels above the bars (skill rule: "Direct labels.
    Label the data, not a legend").
    """
    cats = [l[cat_col] for l in rows]
    vals = [l[val_col] for l in rows]

    fig = go.Figure(go.Bar(
        x=cats, y=vals,
        text=([labels[l[cat_col]] for l in rows] if labels
              else [f"{v:,.0f}{suffix}".replace(",", " ") for v in vals]),
        textposition="outside",
        textfont=_LABEL_FONT,
        marker_color=color,
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>",
    ))
    fig.update_layout(template="dark", meta=dict(title=title, note=note),
                      yaxis_title=y_title, height=height)
    return fig


def grouped_bar_chart(rows, cat_col, series, title, height=340):
    """Two compared series: Blue + Amber, the pair mandated by the identity.

    `series`: list of (column, label). Capped at two -- beyond that, the
    identity requires grouping the tail rather than adding a hue.
    """
    assert len(series) <= 2, "Two series maximum (identity rule)"
    cats = [l[cat_col] for l in rows]
    fig = go.Figure()
    for (col, label), color in zip(series, [BLUE, AMBER]):
        vals = [l[col] for l in rows]
        fig.add_trace(go.Bar(
            x=cats, y=vals, name=label,
            text=vals, textposition="outside", textfont=_LABEL_FONT,
            marker_color=color, cliponaxis=False,
            hovertemplate=f"<b>%{{x}}</b><br>{label}: %{{text}}<extra></extra>",
        ))
    fig.update_layout(template="dark", meta=dict(title=title, note=None),
                      barmode="group", height=height)
    return fig


def line_chart(rows, x_col, y_col, title, suffix="", color=BLUE, height=340):
    """Trend: straight segments, no smoothing.

    Smoothing would invent values between two measurements. On four points,
    that would be particularly dishonest. Ringed circle markers on Void to
    stay legible when two points overlap (skill rule).
    """
    xs = [l[x_col] for l in rows]
    ys = [l[y_col] for l in rows]

    fig = go.Figure(go.Scatter(
        x=xs, y=ys,
        mode="lines+markers+text",
        line=dict(color=color, width=2, shape="linear"),
        marker=dict(size=8, color=color, line=dict(color=VOID, width=1.5)),
        text=[f"{v}{suffix}" for v in ys],
        textposition="top center",
        textfont=_LABEL_FONT,
        hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>",
    ))
    fig.update_layout(template="dark", meta=dict(title=title, note=None), height=height)
    return fig


def empty_figure(message: str) -> go.Figure:
    """"Section unavailable" state rather than a broken chart or an exception.

    Used when the source query depends on stg_extraction__skills and
    CI_WITHOUT_EXTRACTION=true returned 0 rows (schema present, data
    absent). Documents the absence instead of hiding it, consistent with the
    project principle: never a silent correction.
    """
    fig = go.Figure()
    fig.update_layout(
        template="dark",
        meta=dict(title="", note=None),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        height=200,
        annotations=[dict(
            text=message, xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False,
            font=dict(family=MONO_FONT, color=PAPER_MUTED, size=12),
        )],
    )
    return fig
