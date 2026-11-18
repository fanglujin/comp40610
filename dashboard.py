"""
Did pay keep up with prices in Ireland, 2015-2025?
COMP40610 Information Visualisation - interactive visualisation assignment.

Builds the dashboard as a Vega-Lite specification with Altair, from the files written by
prepare_data.py (monthly.csv, quarterly.csv).

Views
  1  See when pay kept up with prices   two panels on one time axis: annual inflation (monthly)
                                         and real pay (quarterly). Drag across either panel to
                                         choose a period.
  2  Compare which prices rose         price change of each spending category in the period,
                                         against the change in pay. Click a category to add its
                                         inflation rate and real pay to view 1.
  3  See whose pay kept up             pay change of each sector in the period, against the
                                         change in prices. Click a sector to add its real pay to view 1.
  Double-click any view to clear the selections.

Outputs
  dashboard.json  the Vega-Lite specification, data included (the submission)
  dashboard.html  the same specification in a self-contained web page

Usage:  python dashboard.py
"""
import json
from pathlib import Path

import altair as alt
import pandas as pd
import vl_convert as vlc

HERE = Path(__file__).resolve().parent
alt.data_transformers.consolidate_datasets = False   # keep the two named datasets as the only data

# ================================================================== data
monthly = pd.read_csv(HERE / "monthly.csv", parse_dates=["t"])
quarterly = pd.read_csv(HERE / "quarterly.csv", parse_dates=["t"])

ALL_ITEMS, ALL_SECTORS = "All items", "All sectors"
MONTHLY = alt.NamedData(name="monthly", format=alt.DataFormat(parse={"t": "date"}))
QUARTERLY = alt.NamedData(name="quarterly", format=alt.DataFormat(parse={"t": "date"}))

# ------------------------------------------------------------------ the story, from the data
avg = quarterly[(quarterly.group == "category") & (quarterly.name == ALL_ITEMS)].set_index("t")
infl = monthly[monthly.name == ALL_ITEMS].set_index("t").annual_rate
first, last = avg.index.min(), avg.index.max()
peak = avg.real.idxmax()                              # real pay's highest quarter ...
low = avg.real[avg.index > peak].idxmin()             # ... and its lowest quarter after that
infl_peaks = infl[infl == infl.max()].index           # every month at the highest rate (they can tie)
COMPOSITION = pd.Timestamp("2020-04-01")              # quarter where the composition effect shows


def pct(series, a, b):
    """% change of `series` from date a to date b."""
    return (series.loc[b] / series.loc[a] - 1) * 100


def quarter(t):
    return f"Q{t.quarter} {t.year}"


def months(dates):
    """'Jun 2022', or 'Jun–Jul 2022' for consecutive months of one year."""
    a, b = dates[0], dates[-1]
    assert len(dates) == (b.year - a.year) * 12 + b.month - a.month + 1 and a.year == b.year
    return f"{a:%b %Y}" if a == b else f"{a:%b}–{b:%b %Y}"


sector_pay = (quarterly[(quarterly.group == "sector") & (quarterly.name != ALL_SECTORS)]
              .pivot(index="t", columns="name", values="pay_idx"))
housing = quarterly[quarterly.name == "Housing & energy"].set_index("t").price_idx
kept_up = int((pct(sector_pay, peak, low) >= pct(avg.price_idx, peak, low)).sum())

FINDINGS = [
    f"•  From {first.year} to {last.year} pay rose {pct(avg.pay_idx, first, last):.0f}% and prices "
    f"{pct(avg.price_idx, first, last):.0f}%: a week's pay buys {pct(avg.real, first, last):.0f}% more.",
    f"•  From {quarter(peak)} to {quarter(low)} inflation cut real pay by {-pct(avg.real, peak, low):.0f}%; "
    f"the pay of only {kept_up} of {sector_pay.shape[1]} sectors kept up with prices.",
    f"•  Housing & energy prices rose {pct(housing, first, last):.0f}%, far faster than pay.",
]

# ================================================================== style
FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"
INK, BODY, MUTED, FAINT, GRID = "#1a1a1a", "#3d3d3d", "#6b6b6b", "#b0b0b0", "#dcdcdc"
# Line colours in view 1; the clicked bar takes the same colour. Every pair of colours that can
# appear together was checked in protan, deutan and tritan simulations (CAM02-UCS distance > 15).
LINE = {"average": INK, "category": "#7b3294", "sector": "#00837a"}
WORSE, BETTER, AVERAGE = "#d0622f", "#86aee0", "#a3a3a3"   # orange = worse for households, in 2 and 3
BAND, BAND_TEXT = "#f5efe6", "#8a6d47"                     # the squeeze period and its label
TITLE, HEAD, TEXT, SMALL = 26, 17, 12.5, 11                # the four type sizes

# Layout. Every view reaches AXIS_W to the left of its origin (view 1 with its y axis labels, views
# 2 and 3 with their name column), so titles, axes and names share one left edge. The bars start
# LABEL_W after that edge, and view 1's plot ends where view 3's bars can end.
LABEL_W, BAR_W, BAR_H, BAR_GAP = 200, 285, 460, 60
AXIS_W = 44
W = 2 * (LABEL_W + BAR_W) + BAR_GAP - AXIS_W
H_INFL, H_REAL = 150, 210
T_DOMAIN = ["2015-01-01", "2025-12-31"]

# ================================================================== selections
# All selections are declared once at the top level of the dashboard, each with the named views
# it is bound to (see `dashboard` below). Altair's add_params is not used: the way it hoists a
# selection shared by two views differs between Altair versions.
#
# The brush draws nothing itself: `selected_quarters` shades the whole quarters it covers,
# so what is shaded is exactly the period views 2 and 3 use.
brush = alt.selection_interval(name="brush", encodings=["x"], zoom=False,
                               mark=alt.BrushConfig(fillOpacity=0, strokeOpacity=0))
# The average bars ignore clicks: their line is the black line already in view 1.
pick_category = alt.selection_point(name="pickCategory", fields=["name"], clear="dblclick",
                                    on=f"click[item() && item().datum && item().datum.name !== '{ALL_ITEMS}']")
pick_sector = alt.selection_point(name="pickSector", fields=["name"], clear="dblclick",
                                  on=f"click[item() && item().datum && item().datum.name !== '{ALL_SECTORS}']")

hover = {panel: alt.selection_point(name=f"hover_{panel}", on="pointerover", nearest=True,
                                    fields=["t"], empty=False, clear="pointerout")
         for panel in ("inflation", "real_pay")}

# Vega expressions. `<selection>_store` is the dataset in which Vega-Lite keeps a selection.
BRUSHED = "length(data('brush_store')) > 0"
PICKED_CATEGORY = "length(data('pickCategory_store')) > 0"
PICKED_ANY = f"{PICKED_CATEGORY} || length(data('pickSector_store')) > 0"
# A quarter is in the period when its midpoint (first day + 45 days) is inside the brush.
IN_BRUSH = "vlSelectionTest('brush_store', {t: toDate(time(datum.t) + 45 * 864e5)}) ? 1 : 0"
QUARTER_LABEL = "'Q' + quarter(datum.t) + ' ' + year(datum.t)"
SIGNED_PCT = "(datum.value > 0 ? '+' : '') + datum.label + '%'"

LINE_COLOR = alt.Color("line:N", legend=None, scale=alt.Scale(domain=list(LINE), range=list(LINE.values())))


# ================================================================== helpers
def bind(selection, *views):
    """The selection as a top-level parameter bound to the named views."""
    return alt.TopLevelSelectionParameter(**selection.param.to_dict(), views=list(views))


def hidden_when(expr):
    """Opacity 0 while the Vega expression `expr` is true."""
    return alt.condition(expr, alt.value(0), alt.value(1))


def date(t):
    return alt.DateTime(year=t.year, month=t.month, date=t.day)


def note(t, v, text, hide_when, **style):
    """Annotation at a date and value; '|' breaks lines."""
    return (alt.Chart().mark_text(**{"fontSize": SMALL, "color": INK, "align": "left", "lineBreak": "|",
                                     "text": text, **style})
            .encode(x=alt.datum(date(t)), y=alt.datum(v), opacity=hidden_when(hide_when)))


def markers(points, hide_when):
    """Hollow circles at key points: they stand out on the line without another colour."""
    return [alt.Chart().mark_point(filled=True, fill="white", stroke=INK, strokeWidth=1.6, size=55)
            .encode(x=alt.datum(date(t)), y=alt.datum(v), opacity=hidden_when(hide_when)) for t, v in points]


def label(text, x, y, **style):
    """Fixed text placed in pixels."""
    return alt.Chart().mark_text(**{"fontSize": SMALL, "color": MUTED, "align": "left", "text": text, **style}
                                 ).encode(x=alt.value(x), y=alt.value(y))


def rule(value, channel="y"):
    """Thin grey reference line."""
    return alt.Chart().mark_rule(color=FAINT).encode(**{channel: alt.datum(value)})


def squeeze_band():
    """Real pay falling from its peak to its low. Hidden while a period is selected."""
    return (alt.Chart().mark_rect(color=BAND)
            .encode(x=alt.datum(date(peak)), x2=alt.datum(date(low)), opacity=hidden_when(BRUSHED)))


def haloed(chart, **style):
    """Text over a white outline of itself, readable where it crosses lines."""
    return [chart.mark_text(stroke="white", strokeWidth=4, strokeJoin="round", **style), chart.mark_text(**style)]


def over_period(group):
    """One row per category or sector of `group`, with its first and last quarter in the brushed
    period. No brush, or a brush covering fewer than two quarters, means the whole period."""
    return (alt.Chart(QUARTERLY)
            .transform_filter(f"datum.group == '{group}'")
            .transform_calculate(ql=QUARTER_LABEL, inb=IN_BRUSH)
            .transform_joinaggregate(n_in="sum(inb)", groupby=["name"])
            .transform_filter("datum.n_in < 2 || datum.inb")
            .transform_aggregate(first="argmin(t)", last="argmax(t)", n_in="max(n_in)", groupby=["name"])
            .transform_calculate(span="datum.first.ql + ' – ' + datum.last.ql"))


def change(field):
    """% change of `field` from the first to the last quarter of the period."""
    return f"(datum.last.{field} / datum.first.{field} - 1) * 100"


# ================================================================== view 1: when did pay keep up?
def time_panel(name, source, y, y_unit, height, shown, tooltip, show_years):
    """Lines of `source` (which provides `line` and `label` fields): the average in black, picked
    ones in colour, with a nearest-point tooltip and values at the right end.
    The lines view (`<name>_lines`) carries the brush and the points view (`<name>_points`) the
    hover selection. Returns the layers as a list, to share one alt.layer with the annotations."""
    x = alt.X("t:T", title=None, scale=alt.Scale(domain=T_DOMAIN),
              axis=alt.Axis(format="%Y", tickCount="year", grid=True, labelFlush=False,
                            labels=show_years, ticks=show_years, domain=show_years))
    base = (source.transform_filter(shown)
            .encode(x=x, y=alt.Y(f"{y}:Q", title=None, scale=alt.Scale(zero=False),
                                 axis=alt.Axis(tickCount=5, minExtent=AXIS_W, labelExpr=f"datum.label + '{y_unit}'"))))

    lines = (base.mark_line(strokeWidth=2.2).encode(color=LINE_COLOR, detail="name:N")
             .properties(name=f"{name}_lines"))
    guide = (base.mark_rule(color="#c4c4c4").encode(y=alt.value(0), y2=alt.value(height))
             .transform_filter(hover[name]))
    points = (base.mark_point(filled=True, size=50)
              .encode(color=LINE_COLOR, opacity=alt.condition(hover[name], alt.value(1), alt.value(0)),
                      tooltip=tooltip)
              .properties(name=f"{name}_points"))

    # Value at the right end of each line. When two lines end within about one label height
    # (12 % of the y range), the upper label moves up to keep them apart.
    ends = (base.transform_joinaggregate(t_end="max(t)", lo=f"min({y})", hi=f"max({y})")
            .transform_filter("datum.t == datum.t_end")
            .transform_window(below=f"lag({y})", sort=[{"field": y}])
            .transform_calculate(
                gap="0.12 * (datum.hi - datum.lo)",
                y_label=f"isValid(datum.below) && datum.{y} - datum.below < datum.gap"
                        f" ? datum.below + datum.gap : datum.{y}",
                text=f"datum.label + ' ' + format(datum.{y}, '.1f') + '{y_unit}'")
            .mark_text(align="left", dx=7, fontSize=TEXT, fontWeight="bold")
            .encode(y="y_label:Q", text="text:N", color=LINE_COLOR))
    return [guide, lines, points, ends]


period = over_period("category").transform_filter(f"datum.name == '{ALL_ITEMS}'")
VALID_PERIOD = f"{BRUSHED} && datum.n_in >= 2"
period_caption = (period.transform_calculate(
                      text=f"({VALID_PERIOD} ? 'Selected: ' : 'Whole period: ') + datum.span"
                           f" + ({BRUSHED} && datum.n_in < 2 ? '   (select at least two quarters)' : '')")
                  .mark_text(align="right", baseline="bottom", dy=-26, fontSize=TEXT, fontWeight="bold", color=BODY)
                  .encode(x=alt.value(W), y=alt.value(0), text="text:N"))
# The quarters views 2 and 3 use: from the start of the first to the end of the last.
selected_quarters = (period.transform_calculate(
                         start="datum.first.t", end="datetime(year(datum.last.t), month(datum.last.t) + 3, 1)")
                     .mark_rect(color=INK)
                     .encode(x="start:T", x2="end:T", opacity=alt.condition(VALID_PERIOD, alt.value(0.07), alt.value(0))))
panel_title = dict(baseline="bottom", dy=-10, fontSize=TEXT, fontWeight="bold", color=BODY)

inflation_panel = alt.layer(
    squeeze_band(),
    selected_quarters,
    rule(0),
    *time_panel(
        "inflation",
        alt.Chart(MONTHLY).transform_calculate(
            line=f"datum.name == '{ALL_ITEMS}' ? 'average' : 'category'", label="datum.name"),
        "annual_rate", "%", H_INFL,
        shown=f"datum.name == '{ALL_ITEMS}' || vlSelectionTest('pickCategory_store', datum)",
        tooltip=[alt.Tooltip("name:N", title="Prices"),
                 alt.Tooltip("t:T", title="Month", format="%b %Y"),
                 alt.Tooltip("annual_rate:Q", title="Annual inflation (%)", format=".1f")],
        show_years=False),
    *markers([(t, infl[t]) for t in infl_peaks], PICKED_CATEGORY),
    note(infl_peaks[0], infl.max(), f"Peak {infl.max():.1f}% ({months(infl_peaks)})", PICKED_CATEGORY,
         align="right", dx=-10),
    label("Annual inflation: % change on a year earlier", -AXIS_W, 0, **panel_title),
    period_caption,
    label("Drag across either panel to choose a period", W, 0, align="right", baseline="bottom", dy=-10),
).properties(width=W, height=H_INFL)

real_pay_panel = alt.layer(
    squeeze_band(),
    selected_quarters,
    rule(100),
    *time_panel(
        "real_pay",
        alt.Chart(QUARTERLY).transform_calculate(
            line=f"datum.name == '{ALL_ITEMS}' ? 'average' : datum.group",
            ql=QUARTER_LABEL,
            label=f"datum.name == '{ALL_ITEMS}' ? 'Real pay' : datum.name",
            pay="format(datum.pay_idx, '.1f') + (datum.group == 'sector' ? ' (' + datum.name + ')' : ' (all sectors)')",
            prices="format(datum.price_idx, '.1f') + (datum.group == 'category' ? ' (' + datum.name + ')' : ' (all items)')",
        ),
        "real", "", H_REAL,
        shown=f"(datum.group == 'category' && (datum.name == '{ALL_ITEMS}' || vlSelectionTest('pickCategory_store', datum)))"
              " || (datum.group == 'sector' && vlSelectionTest('pickSector_store', datum))",
        tooltip=[alt.Tooltip("label:N", title="Line"),
                 alt.Tooltip("ql:N", title="Quarter"),
                 alt.Tooltip("real:Q", title="Real pay (2015 Q1 = 100)", format=".1f"),
                 alt.Tooltip("pay:N", title="Pay index"),
                 alt.Tooltip("prices:N", title="Price index")],
        show_years=True),
    *markers([(peak, avg.real[peak]), (low, avg.real[low])], PICKED_ANY),
    note(peak, avg.real[peak], f"Peak {quarter(peak)}: {avg.real[peak]:.1f}", PICKED_ANY, align="right", dx=-10),
    note(low, avg.real[low], f"Low {quarter(low)}: {avg.real[low]:.1f}", PICKED_ANY, align="center", dy=16),
    note(COMPOSITION, avg.real[COMPOSITION], "*", PICKED_ANY, align="center", dy=-10,   # explained in the notes
         fontSize=TEXT, fontWeight="bold", color=MUTED),
    note(low, avg.real[peak], "Squeezed|by inflation", f"{PICKED_ANY} || {BRUSHED}",   # top right of the band,
         align="right", baseline="top", dx=-8, dy=4,                                    # where the line is low
         fontSize=TEXT, fontWeight="bold", color=BAND_TEXT),
    label("Real pay: what a week's pay buys (2015 Q1 = 100)", -AXIS_W, 0, **panel_title),
).properties(width=W, height=H_REAL)

view1 = alt.vconcat(inflation_panel, real_pay_panel, spacing=44).properties(
    title=alt.Title("1   See when pay kept up with prices, and when it didn't",
                    subtitle="Annual inflation rate and real average weekly pay, Ireland, January 2015 to December 2025"),
    description="Line charts of the annual inflation rate and of real pay, 2015 to 2025, on one time axis.",
)


# ================================================================== views 2 and 3: the selected period
def ranked_bars(rows, average, pick, pick_color, reference, reference_name, legend_labels, hint, tooltip):
    """Bars of each row's % change, largest first, with the names in a column on the left, a
    dashed reference line and a legend above. The names are text marks, not axis labels, so the
    view reaches no further left than view 1. A clicked bar takes its line colour from view 1
    and the others fade; the average bar is not clickable."""
    y = alt.Y("name:N", title=None, axis=None, sort=alt.EncodingSortField("change", op="max", order="descending"))
    x = alt.X("change:Q", title=None, scale=alt.Scale(range=[LABEL_W - AXIS_W, LABEL_W - AXIS_W + BAR_W],
                                     padding=44, nice=False),
              axis=alt.Axis(tickCount=5, labelExpr=SIGNED_PCT, labelFlush=True))
    status = alt.Color("status:N", scale=alt.Scale(domain=["worse", "better", "average"],
                                                   range=[WORSE, BETTER, AVERAGE]),
                       legend=alt.Legend(title=None, orient="none", legendX=-AXIS_W, legendY=-48,
                                         direction="horizontal", symbolType="square", columnPadding=16,
                                         labelExpr=f"{json.dumps(legend_labels)}[datum.value]"))
    is_average = f"datum.name == '{average}'"
    bars = (rows.mark_bar(height=14, cornerRadiusEnd=2,
                          cursor=alt.ExprRef(f"{is_average} ? 'default' : 'pointer'"))
            .encode(y=y, x=x,
                    color=alt.condition(pick, alt.value(pick_color), status, empty=False),
                    opacity=alt.condition(pick, alt.value(1), alt.value(0.4)),
                    tooltip=tooltip)
            .properties(name=f"{pick.name}_bars"))
    # Values at the end of each bar; for a negative bar, just right of the zero line.
    values = (rows.transform_calculate(x_text="max(datum.change, 0)", text="format(datum.change, '+.1f') + '%'")
              .encode(y=y, x="x_text:Q", text="text:N"))
    names = (rows.mark_text(align="left", fontSize=TEXT, color=INK, limit=LABEL_W - 8,
                            fontWeight=alt.ExprRef(f"{is_average} ? 'bold' : 'normal'"))
             .encode(y=y, x=alt.value(-AXIS_W), text="name:N"))
    reference_row = rows.transform_filter(is_average)

    return alt.layer(
        names,
        rule(0, "x"),
        reference_row.mark_rule(strokeDash=[4, 3], color=INK, strokeWidth=1.5).encode(x=f"{reference}:Q"),
        bars,
        *haloed(values, align="left", dx=5, fontSize=SMALL, color=MUTED),
        reference_row.transform_calculate(text=f"'{reference_name} ' + format(datum.{reference}, '+.1f') + '%'")
                     .mark_text(baseline="bottom", dy=-12, fontSize=TEXT, fontWeight="bold", color=INK)
                     .encode(x=f"{reference}:Q", y=alt.value(0), text="text:N"),
        label(hint, -AXIS_W, BAR_H, baseline="top", dy=30, lineBreak="|"),
    ).properties(width=LABEL_W - AXIS_W + BAR_W, height=BAR_H)


category_rows = over_period("category").transform_calculate(
    change=change("price_idx"), pay=change("pay_idx"),
    status=f"datum.name == '{ALL_ITEMS}' ? 'average' : datum.change > datum.pay ? 'worse' : 'better'")
view2 = ranked_bars(
    category_rows, ALL_ITEMS, pick_category, LINE["category"], "pay", "Pay",
    {"worse": "Rose more than pay", "better": "Rose less than pay", "average": ALL_ITEMS},
    "Click a category to add its inflation rate, and what a week's pay|buys of it, to view 1",
    [alt.Tooltip("name:N", title="Category"), alt.Tooltip("span:N", title="Period"),
     alt.Tooltip("change:Q", title="Price change (%)", format="+.1f"),
     alt.Tooltip("pay:Q", title="Pay change, all sectors (%)", format="+.1f")],
).properties(
    title=alt.Title("2   Compare which prices rose faster than pay",
                    subtitle=["Price change by spending category, and change in average weekly pay,",
                              "Ireland, selected period"]),
    description="Bar chart of the price change of each spending category in the selected period, "
                "against the change in pay.",
)

sector_rows = over_period("sector").transform_calculate(
    change=change("pay_idx"), prices=change("price_idx"), weekly_pay="datum.last.weekly_pay",
    status=f"datum.name == '{ALL_SECTORS}' ? 'average' : datum.change < datum.prices ? 'worse' : 'better'")
view3 = ranked_bars(
    sector_rows, ALL_SECTORS, pick_sector, LINE["sector"], "prices", "Prices",
    {"worse": "Pay fell behind prices", "better": "Pay kept up with prices", "average": ALL_SECTORS},
    "Click a sector to add its real pay to view 1",
    [alt.Tooltip("name:N", title="Sector"), alt.Tooltip("span:N", title="Period"),
     alt.Tooltip("change:Q", title="Pay change (%)", format="+.1f"),
     alt.Tooltip("prices:Q", title="Price change, all items (%)", format="+.1f"),
     alt.Tooltip("weekly_pay:Q", title="Weekly pay, last quarter (€)", format=",.0f")],
).properties(
    title=alt.Title("3   See whose pay kept up with prices",
                    subtitle=["Change in average weekly pay by sector, and change in prices,",
                              "Ireland, selected period"]),
    description="Bar chart of the pay change of each sector in the selected period, against the change in prices.",
)

# ================================================================== page
NOTES = [
    "CSO CPM23 – HICP by COICOP 2018 commodity group (High Value Dataset): annual rate of change; "
    "12-month moving-average index at each quarter's last month.",
    "CSO EHQ03 – average weekly earnings excluding irregular earnings, all employees, all sectors and "
    "17 NACE sectors; 4-quarter moving average (not seasonally adjusted).",
    "All indices rebased to 2015 Q1 = 100. HICP excludes owner-occupied housing costs.",
    "* 2020: the jump in average pay may not mean pay rose; many low-paid workers may have lost their jobs "
    "or been temporarily laid off, dropping out of the average and lifting it (a composition effect).",
]
notes = alt.layer(
    label("Sources and notes", -AXIS_W, 0, baseline="top", fontWeight="bold", color=BODY),
    label("\n".join(NOTES), -AXIS_W, 18, baseline="top", lineBreak="\n", lineHeight=17),
).properties(width=W, height=18 + 17 * len(NOTES))

# A one-column concat with align "none": each row keeps its own left edge, so titles, axes and
# name columns line up, instead of the plot areas being pushed into line.
dashboard = alt.concat(
    view1,
    alt.hconcat(view2, view3, spacing=BAR_GAP).resolve_scale(color="independent"),   # a legend each
    notes,
    columns=1, spacing=64,
).resolve_scale(color="independent").properties(
    align="none",
    title=alt.Title("Did pay keep up with prices in Ireland, 2015–2025?",
                    subtitle=[*FINDINGS, "", "Double-click any view to reset."],
                    fontSize=TITLE, subtitleFontSize=TEXT, subtitleColor=BODY, subtitleLineHeight=21,
                    subtitlePadding=12, offset=30),
    description="Interactive dashboard comparing Irish consumer prices (CSO CPM23) with average weekly pay "
                "(CSO EHQ03), 2015 to 2025.",
    padding=40,
    autosize=alt.AutoSizeParams(type="pad", resize=True),   # re-measure when longer end labels appear
    usermeta={"embedOptions": {"actions": False}},          # no export menu when embedded
    params=[bind(brush, "inflation_lines", "real_pay_lines"),
            bind(hover["inflation"], "inflation_points"),
            bind(hover["real_pay"], "real_pay_points"),
            bind(pick_category, "pickCategory_bars"),
            bind(pick_sector, "pickSector_bars")],
).configure(font=FONT, background="white").configure_view(stroke=None).configure_axis(
    domainColor="#c8c8c8", tickColor="#c8c8c8", gridColor=GRID, gridDash=[2, 3],
    labelColor=BODY, labelFontSize=SMALL,
).configure_axisY(domain=False, ticks=False, labelPadding=6).configure_title(
    anchor="start", frame="bounds", color=INK, fontSize=HEAD,
    subtitleColor=MUTED, subtitleFontSize=TEXT, subtitlePadding=6, offset=22,
).configure_legend(labelColor=BODY, labelFontSize=SMALL, symbolSize=120)


# ================================================================== output
def records(df):
    """Rows for the spec: dates as ISO strings, missing values as null."""
    out = df.assign(t=df.t.dt.strftime("%Y-%m-%d")).astype(object)
    return out.where(out.notna(), None).to_dict("records")


def write_json(spec, path):
    """The specification indented for reading, with each data row on one line."""
    datasets = spec.pop("datasets")
    spec["datasets"] = "DATASETS"
    data = ",\n".join(
        f'    "{name}": [\n' + ",\n".join(f"      {json.dumps(row, ensure_ascii=False)}" for row in rows) + "\n    ]"
        for name, rows in datasets.items())
    text = json.dumps(spec, indent=2, ensure_ascii=False).replace('"DATASETS"', "{\n" + data + "\n  }")
    path.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    spec = dashboard.properties(datasets={"monthly": records(monthly), "quarterly": records(quarterly)}).to_dict()
    write_json(spec, HERE / "dashboard.json")
    vl_version = spec["$schema"].split("/v")[-1].rsplit(".", 2)[0]       # e.g. "6.1", as in the JSON
    page = vlc.vegalite_to_html(json.loads((HERE / "dashboard.json").read_text()), vl_version=vl_version, bundle=True)
    (HERE / "dashboard.html").write_text(page, encoding="utf-8")
    print("wrote dashboard.json and dashboard.html")
