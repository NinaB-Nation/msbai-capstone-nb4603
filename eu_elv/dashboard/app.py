"""
EU End-of-Life Vehicle Recycling Dashboard.

Reads the baked-in extract (data/elv_country_year.csv) built by
build_extract.py from elv_gold.elv_country_year -- no BigQuery access at
runtime, same reasoning as the rest of this capstone's dashboards: the data
is tiny (543 rows), so baking it in removes network/auth latency from every
cold start and lets Cloud Run run with zero BigQuery IAM at all.
"""
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "elv_country_year.csv")

RECYCLING_TARGET = 85.0
RECOVERY_TARGET = 95.0

# Status palette -- fixed, never themed (see dataviz skill: status colors are
# reserved and always paired with an icon + label, never color alone).
COLOR_PASS = "#0ca30c"       # good
COLOR_FAIL = "#d03b3b"       # critical
COLOR_DOCUMENTED = "#fab219"  # warning -- known, explained anomaly
COLOR_UNDIAGNOSED = "#ec835a"  # serious -- noticed, not investigated

INK = "#0b0b0b"
MUTED = "#898781"
GRIDLINE = "#e1e0d9"

STATUS_LABELS = {
    "pass": "Meets 85% target",
    "fail": "Below 85% target",
    "documented": "Documented anomaly",
    "undiagnosed": "Flagged, undiagnosed",
}
STATUS_COLORS = {
    "pass": COLOR_PASS,
    "fail": COLOR_FAIL,
    "documented": COLOR_DOCUMENTED,
    "undiagnosed": COLOR_UNDIAGNOSED,
}


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH)
    df["anomaly_type"] = df["anomaly_type"].fillna("none")

    def status(row):
        if row["anomaly_type"] == "documented":
            return "documented"
        if row["anomaly_type"] == "flagged_undiagnosed":
            return "undiagnosed"
        if pd.isna(row["target_met_recycling"]):
            return None
        return "pass" if row["target_met_recycling"] else "fail"

    df["status"] = df.apply(status, axis=1)
    return df


def apply_chart_theme(fig, legend=True):
    fig.update_layout(
        font=dict(color=INK),
        plot_bgcolor="#fcfcfb",
        paper_bgcolor="#fcfcfb",
        title_font=dict(color=INK, size=18),
        legend=dict(font=dict(color=INK)) if legend else dict(),
        showlegend=legend,
        margin=dict(t=60, r=20, b=40, l=50),
    )
    fig.update_xaxes(color=INK, gridcolor=GRIDLINE, title_font=dict(color=INK), tickfont=dict(color=INK))
    fig.update_yaxes(color=INK, gridcolor=GRIDLINE, title_font=dict(color=INK), tickfont=dict(color=INK))
    return fig


def round_pct(x):
    if pd.isna(x):
        return "n/a"
    return f"{x:.1f}%"


st.set_page_config(page_title="EU ELV Recycling Dashboard", layout="wide")

df = load_data()
countries = df[df["is_aggregate"] == False].copy()
eu_agg = df[df["is_aggregate"] == True].copy()

st.title("EU End-of-Life Vehicle Recycling Dashboard")
st.caption(
    "Reuse, recycling and recovery performance for end-of-life vehicles across the EU, "
    "sourced from Eurostat (env_waselvt / env_waselv)."
)

tab_country, tab_trend, tab_anomalies, tab_methodology = st.tabs(
    ["Country Performance", "EU Trend", "Flagged Anomalies", "How to Read This"]
)

# ---------------------------------------------------------------------------
with tab_country:
    years_available = sorted(countries["year"].dropna().unique().astype(int), reverse=True)
    selected_year = st.selectbox("Year", years_available, index=0)

    year_df = countries[countries["year"] == selected_year].dropna(subset=["reuse_recycling_rate"]).copy()
    year_df = year_df.sort_values("reuse_recycling_rate", ascending=True)

    n_pass = (year_df["status"] == "pass").sum()
    n_total = len(year_df)
    st.markdown(
        f"**{n_pass} of {n_total}** reporting countries met the 85% reuse+recycling target in {selected_year}."
    )

    bar_view, map_view = st.tabs(["Bar chart", "Map"])

    with bar_view:
        fig = go.Figure()
        for status_key, label in STATUS_LABELS.items():
            sub = year_df[year_df["status"] == status_key]
            if sub.empty:
                continue
            fig.add_trace(go.Bar(
                x=sub["reuse_recycling_rate"],
                y=sub["country_name"],
                orientation="h",
                name=label,
                marker_color=STATUS_COLORS[status_key],
                hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
            ))
        fig.add_vline(x=RECYCLING_TARGET, line_dash="dash", line_color=MUTED,
                       annotation_text="85% target", annotation_font_color=INK)
        fig.update_layout(
            title=f"Reuse + recycling rate by country, {selected_year}",
            barmode="overlay",
            height=max(400, 22 * n_total),
            xaxis_title="Reuse + recycling rate (%)",
            yaxis_title=None,
            legend_title_text="Status",
        )
        apply_chart_theme(fig)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Bars colored by status: green meets the 85% reuse+recycling target, red falls short, "
            "amber/orange are years with a known reporting anomaly (see the Flagged Anomalies tab)."
        )

    with map_view:
        # Plotly's ISO-3 locationmode needs 3-letter codes, but Silver only
        # carries ISO alpha-2 (matching Eurostat's own `geo` dimension) --
        # matching on country name instead avoids adding an alpha-3 mapping
        # just for this one chart.
        fig = go.Figure(data=go.Choropleth(
            locations=year_df["country_name"],
            locationmode="country names",
            z=year_df["reuse_recycling_rate"],
            text=year_df["country_name"],
            colorscale=[[0, "#cde2fb"], [0.5, "#3987e5"], [1, "#0d366b"]],
            marker_line_color=GRIDLINE,
            colorbar=dict(title="Rate (%)"),
            hovertemplate="%{text}: %{z:.1f}%<extra></extra>",
        ))
        fig.update_geos(scope="europe", showcountries=True, countrycolor=GRIDLINE, bgcolor="#fcfcfb")
        fig.update_layout(title=f"Reuse + recycling rate by country, {selected_year}", height=550)
        apply_chart_theme(fig, legend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Map shows reuse+recycling rate magnitude (sequential blue), not pass/fail status -- "
            "use the bar chart for the 85%-target color coding."
        )

# ---------------------------------------------------------------------------
with tab_trend:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=eu_agg["year"], y=eu_agg["reuse_recycling_rate"],
        mode="lines+markers", name="Reuse + recycling rate",
        line=dict(color="#2a78d6", width=2), marker=dict(size=8),
    ))
    fig.add_trace(go.Scatter(
        x=eu_agg["year"], y=eu_agg["reuse_recovery_rate"],
        mode="lines+markers", name="Reuse + recovery rate",
        line=dict(color="#eb6834", width=2), marker=dict(size=8),
    ))
    fig.add_hline(y=RECYCLING_TARGET, line_dash="dash", line_color="#2a78d6",
                   annotation_text="85% recycling target", annotation_font_color=INK)
    fig.add_hline(y=RECOVERY_TARGET, line_dash="dash", line_color="#eb6834",
                   annotation_text="95% recovery target", annotation_font_color=INK)
    fig.update_layout(
        title="EU-27 aggregate rate over time",
        xaxis_title="Year", yaxis_title="Rate (%)",
        height=500,
    )
    apply_chart_theme(fig)
    st.plotly_chart(fig, use_container_width=True)

    latest = eu_agg.sort_values("year").iloc[-1]
    st.markdown(
        f"**In {int(latest['year'])}, the EU-27 aggregate reuse+recycling rate was "
        f"{round_pct(latest['reuse_recycling_rate'])}** and the reuse+recovery rate was "
        f"{round_pct(latest['reuse_recovery_rate'])}, against targets of 85% and 95% respectively."
    )
    st.caption(
        "EU27_2020 is Eurostat's own aggregate across 27 member states, not a per-country figure "
        "and not the average of the country bars on the other tab."
    )

# ---------------------------------------------------------------------------
with tab_anomalies:
    st.subheader("Documented anomalies")
    st.caption(
        "Rates in these country-years look extreme (a sharp drop, or a rate above 100%) but have a "
        "verified, sourced explanation -- disclosed here rather than silently smoothed over or dropped."
    )
    documented = countries[countries["anomaly_type"] == "documented"].sort_values(["country_name", "year"])
    for _, row in documented.iterrows():
        st.markdown(
            f"**{row['country_name']} {int(row['year'])}** -- recycling "
            f"{round_pct(row['reuse_recycling_rate'])}, recovery {round_pct(row['reuse_recovery_rate'])}"
        )
        st.markdown(f"> {row['anomaly_note']}")

    st.divider()
    st.subheader("Flagged, undiagnosed")
    st.caption(
        "These country-years also show a rate above 100% or a large year-over-year swing, but no "
        "verified external cause has been found for them -- flagged for visibility rather than "
        "presented at face value or silently dropped."
    )
    undiagnosed = countries[countries["anomaly_type"] == "flagged_undiagnosed"].sort_values(["country_name", "year"])
    # st.dataframe()/st.table() serialize through pyarrow, which segfaults
    # reproducibly in this environment (confirmed via dmesg: libarrow.so,
    # same failure class as the pyarrow-based parquet crash documented
    # elsewhere in this project) -- a markdown table sidesteps it entirely.
    table_lines = ["| Country | Year | Recycling rate (%) | Recovery rate (%) |", "|---|---|---|---|"]
    for _, row in undiagnosed.iterrows():
        table_lines.append(
            f"| {row['country_name']} | {int(row['year'])} | "
            f"{round_pct(row['reuse_recycling_rate'])} | {round_pct(row['reuse_recovery_rate'])} |"
        )
    st.markdown("\n".join(table_lines))

# ---------------------------------------------------------------------------
with tab_methodology:
    st.subheader("How to read this")
    st.markdown("""
**What's being measured.** The EU End-of-Life Vehicle (ELV) Directive sets two
targets for each member state: at least **85%** of an end-of-life vehicle's
weight must be reused or recycled, and at least **95%** must be reused or
recovered (recycling plus other recovery methods such as energy recovery).
Rates above 100% are possible in the source data -- they mean a country
processed more tonnage in a year than it newly generated, typically by
clearing a backlog of previously stockpiled vehicles.

**Data source.** Eurostat's `env_waselvt` (totals: count, weight, rates by
country and year) and `env_waselv` (detailed breakdown by waste-management
operation, including exported vehicles). Eurostat's own API was not reachable
from the environment this pipeline was built in, so the source files were
exported manually from Eurostat's databrowser and loaded as-is into the
Bronze layer.

**Country codes.** Eurostat's `geo` codes match ISO 3166-1 alpha-2 for every
country here except Greece (Eurostat: `EL`, ISO: `GR`), reconciled in the
Silver layer. `EU27_2020` is Eurostat's own 27-member aggregate, not a
country -- shown only on the EU Trend tab, excluded from the country bar
chart and map. Iceland, Liechtenstein and Norway are EEA/EFTA members bound
by the ELV Directive via the EEA Agreement, not EU members; they're included
in the country views but tagged separately in the underlying data.

**Estimated vs. reported values.** Eurostat flags some values as estimated,
imputed, or low-reliability rather than directly reported. Those flags are
preserved through the pipeline (visible in the underlying Gold table) rather
than being treated the same as a directly reported figure.

**Anomaly confidence.** Two tiers, shown separately on the Flagged Anomalies
tab: **documented** anomalies have a verified, sourced cause; **flagged,
undiagnosed** anomalies were noticed (rate over 100%, or a swing of more than
15 percentage points year-over-year) but have no verified cause on record.

**Architecture.** Bronze (raw Eurostat exports, unmodified) → Silver (typed,
country-code-reconciled, flags preserved) → Gold (`elv_country_year`: one row
per country per year, targets evaluated, anomalies flagged) in BigQuery. This
dashboard reads a CSV extract of Gold, rebuilt each time the pipeline runs --
it does not query BigQuery live.
""")
