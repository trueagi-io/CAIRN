"""Live (in-progress) run panel. Auto-refreshes only its own contents via
st.fragment(run_every=...), so the sidebar run-selector never resets."""

import streamlit as st

import chart_grid
import charts
import data


def render(run: "data.RunInfo"):
    st.subheader(f"Live · {run.label}")

    col_a, col_b = st.columns([1, 3])
    with col_a:
        interval = st.slider('Refresh (s)', 1, 60, 15, key=f'refresh_{run.label}')
    with col_b:
        x_col = st.radio('Index', ['cip_index', 'timestamp'], horizontal=True,
                          format_func=charts.label, key=f'xcol_{run.label}')

    _live_fragment(run, interval, x_col)


def _live_fragment(run, interval, x_col):
    @st.fragment(run_every=interval)
    def _inner():
        df = data.read_metrics_csv(run.metrics_path)
        if df.empty:
            st.info('Waiting for the first recorded row...')
            return

        x = x_col if x_col in df.columns else 'cip_index'
        if x == 'timestamp':
            df = df.copy()
            df['timestamp'] = _to_datetime(df['timestamp'])

        _render_kpis(df)

        chart_grid.render(df, x, key_prefix=f'live_{run.label}')

        if data.summary_is_current(run.metrics_path, run.summary_path):
            st.rerun()  # promotes this run from live -> completed on the next top-level render

    _inner()


def _render_kpis(df):
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else None

    def _delta(col):
        if prev is None or col not in df.columns:
            return None
        try:
            return float(latest[col]) - float(prev[col])
        except (TypeError, ValueError):
            return None

    cols = st.columns(4)
    cols[0].metric(charts.label('cip_index'), int(latest['cip_index']))
    cols[1].metric(charts.label('af_size'), int(latest['af_size']) if not _isnan(latest['af_size']) else 'N/A',
                    delta=_delta('af_size'))
    cols[2].metric(charts.label('effectiveness'), _fmt(latest.get('effectiveness')), delta=_delta('effectiveness'))
    cols[3].metric(charts.label('resource_cost'), _fmt(latest.get('resource_cost')), delta=_delta('resource_cost'))


def _isnan(v):
    try:
        return v != v  # NaN != NaN
    except TypeError:
        return False


def _fmt(v):
    if v is None or _isnan(v):
        return 'N/A'
    return f'{float(v):.3f}'


def _to_datetime(series):
    import pandas as pd
    return pd.to_datetime(series, errors='coerce')
