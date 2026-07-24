"""Finished-run panel: summary.json / trends.csv / full static time series."""

from pathlib import Path

import streamlit as st

import chart_grid
import charts
import data

CAIRN_ROOT = Path(__file__).resolve().parent.parent


@st.cache_data
def _cached_initial_funds():
    return data.parse_initial_funds(CAIRN_ROOT)


def render(run: "data.RunInfo"):
    st.subheader(f"Completed · {run.label}")

    summary = data.read_summary_json(run.summary_path)
    metrics_df = data.read_metrics_csv(run.metrics_path)
    trends_df = data.read_trends_csv(run.trends_path)

    tab_summary, tab_series, tab_trends = st.tabs(['Summary', 'Time Series', 'Atom Trends'])

    with tab_summary:
        _render_summary(summary)
    with tab_series:
        _render_full_series(metrics_df, run)
    with tab_trends:
        _render_trends(trends_df, run)


def _render_summary(summary):
    if not summary:
        st.warning('summary.json could not be read.')
        return

    duration = _duration(summary.get('run_timestamp'), summary.get('completed_at'))
    cols = st.columns(4)
    cols[0].metric(charts.label('effectiveness'), _fmt(summary.get('effectiveness')))
    cols[1].metric('Run Duration', duration or '—')
    resource = summary.get('resource_metrics', {}) or {}
    cols[2].metric(charts.label('af_size_ratio'), _fmt(resource.get('af_size_ratio')))
    cols[3].metric(charts.label('link_density'), _fmt(resource.get('link_density')))

    topology = summary.get('topology', {}) or {}
    if topology:
        st.markdown('**Topology**')
        t_cols = st.columns(len(topology))
        for c, (k, v) in zip(t_cols, topology.items()):
            c.metric(charts.label(k), v)

    af_trend = summary.get('af_trend_summary', {}) or {}
    if af_trend:
        st.markdown('**Average Attentional Focus**')
        a_cols = st.columns(len(af_trend))
        for c, (k, v) in zip(a_cols, af_trend.items()):
            c.metric(charts.label(k), _fmt(v))

    probe = summary.get('probe_metrics')
    if probe:
        st.markdown('**Test Probing**')
        p_cols = st.columns(len(probe))
        for c, (k, v) in zip(p_cols, probe.items()):
            c.metric(charts.label(k), _fmt(v))

    benchmark = summary.get('benchmark_comparison')
    if benchmark:
        st.markdown('**Benchmark comparison** (vs. mve baseline)')
        b_cols = st.columns(len(benchmark))
        for c, (k, v) in zip(b_cols, benchmark.items()):
            c.metric(charts.label(k), _fmt(v))

    params = summary.get('parameters')
    if params:
        st.markdown('**Parameters**')
        initial_funds = _cached_initial_funds()
        table = {}
        for k, v in params.items():
            table[charts.label(k)] = v
            if k in initial_funds and initial_funds[k] is not None:
                table[f'Initial {charts.label(k)}'] = str(initial_funds[k])
        st.table(table)


def _render_full_series(df, run):
    if df.empty:
        st.warning('metrics.csv is empty or unreadable.')
        return

    @st.fragment
    def _inner():
        x_col = st.radio('Index', ['cip_index', 'timestamp'], horizontal=True,
                          format_func=charts.label, key=f'completed_xcol_{run.label}')
        plot_df = df
        if x_col == 'timestamp':
            import pandas as pd
            plot_df = df.copy()
            plot_df['timestamp'] = pd.to_datetime(plot_df['timestamp'], errors='coerce')

        chart_grid.render(plot_df, x_col, key_prefix=f'completed_{run.label}')

    _inner()


def _render_trends(trends_df, run):
    if trends_df.empty:
        st.warning('trends.csv is empty or unreadable.')
        return

    @st.fragment
    def _inner():
        trend_filter = st.multiselect('Filter by trend', options=sorted(trends_df['trend'].unique()),
                                       default=list(sorted(trends_df['trend'].unique())),
                                       key=f'completed_trend_filter_{run.label}')
        search = st.text_input('Search by name', key=f'completed_search_{run.label}')

        filtered = trends_df[trends_df['trend'].isin(trend_filter)]
        if search:
            filtered = filtered[filtered['atom'].str.contains(search, case=False, na=False)]
        st.dataframe(filtered, width='stretch')

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(charts.trend_category_bar(trends_df), use_container_width=True, config=charts.PLOTLY_CONFIG)
        with c2:
            st.plotly_chart(charts.volatility_histogram(trends_df), use_container_width=True, config=charts.PLOTLY_CONFIG)

    _inner()


def _duration(start, end):
    if not start or not end:
        return None
    try:
        from datetime import datetime
        d = datetime.fromisoformat(end) - datetime.fromisoformat(start)
        return str(d)
    except ValueError:
        return None


def _fmt(v):
    if v is None:
        return '—'
    if isinstance(v, int):
        return str(v)
    try:
        return f'{float(v):.3f}'
    except (TypeError, ValueError):
        return str(v)
