"""CAIRN evaluation dashboard — structural CIP + cognitive synergy (separate).

Run: streamlit run dashboard/app.py --server.port 8501
(from CAIRN/, venv active)

Surfaces never share chart series:
  structural        — demo / mve / assignment CIP time series
  cognitive_synergy — bridge steering/feedback protocol results
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

import charts
import cognitive_synergy_view
import completed_view
import data
import live_view

OUTPUT_ROOT = Path(__file__).resolve().parent.parent / 'output'

_STATE_BADGE = {'live': '🟢', 'complete': '✅', 'stale': '⚪'}

st.set_page_config(page_title='CAIRN', layout='wide')


def _inject_css():
    st.markdown(f"""
    <style>
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {charts.SURFACE};
        border-radius: 12px;
        border: 1px solid {charts.GRIDLINE};
        box-shadow: 0 0 24px rgba(139,92,246,0.12), 0 1px 2px rgba(0,0,0,0.4);
        padding: 8px 4px 4px 4px;
        margin-bottom: 12px;
    }}
    .cairn-section-title {{
        font-size: 15px;
        font-weight: 600;
        color: {charts.INK_PRIMARY};
        font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
        padding: 4px 8px 8px 8px;
    }}
    [data-testid="stMetricValue"] {{
        font-family: ui-monospace, "SF Mono", "Cascadia Code", "Roboto Mono", monospace;
    }}
    .js-plotly-plot .scatterlayer {{
        filter: drop-shadow(0 0 6px rgba(139,92,246,0.35));
    }}
    </style>
    """, unsafe_allow_html=True)


@st.cache_data(ttl=30, show_spinner=False)
def _cached_all_runs(output_root_str: str):
    return data.discover_all_runs(Path(output_root_str))


def _format_run_label(run: data.RunInfo) -> str:
    badge = _STATE_BADGE.get(run.state, '')
    if run.state == 'complete':
        if run.summary_path.exists():
            finished = _relative_time(_age_seconds(run.summary_path.stat().st_mtime))
        else:
            finished = _relative_time(_age_seconds(run.last_modified))
        return f'{badge} {run.label} · complete · finished {finished}'
    if run.state == 'live':
        updated = _relative_time(_age_seconds(run.last_modified))
        return f'{badge} {run.label} · live · updated {updated}'
    halted = _relative_time(_age_seconds(run.last_modified))
    return f'{badge} {run.label} · stale · halted {halted}'


def _age_seconds(mtime):
    return max(time.time() - mtime, 0)


def _relative_time(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f'{seconds}s ago'
    if seconds < 3600:
        return f'{seconds // 60}m ago'
    if seconds < 86400:
        return f'{seconds // 3600}h ago'
    return f'{seconds // 86400}d ago'


def _pick_default_key(runs: list[data.RunInfo], keys: list[str]) -> str:
    if not keys:
        return ''
    for r in runs:
        if r.state == 'live':
            return str(r.directory)
    return keys[0]


def main():
    _inject_css()
    st.title('Evaluation Dashboard')

    all_runs = _cached_all_runs(str(OUTPUT_ROOT))
    structural = all_runs.get('structural') or []
    cs_runs = all_runs.get('cognitive_synergy') or []

    if st.sidebar.button('Scan output dir', key='scan_output'):
        _cached_all_runs.clear()
        try:
            cognitive_synergy_view._cached_inventory.clear()
            cognitive_synergy_view._cached_cs_runs.clear()
        except Exception:
            pass
        st.rerun()
    surface = st.sidebar.radio(
        'Surface',
        ['structural', 'cognitive_synergy'],
        format_func=lambda s: (
            'Structural CIP (demo/mve/assignment)'
            if s == 'structural'
            else 'Cognitive synergy (bridge)'
        ),
        key='surface_kind',
    )

    if surface == 'structural':
        runs = structural
        empty_msg = f'No CIP runs under {OUTPUT_ROOT}/{{demo,mve,benchmark}}'
    else:
        runs = cs_runs
        empty_msg = (
            f'No bridge runs under {OUTPUT_ROOT}/cognitive_synergy/\n\n'
            'Run `python bridge/mve_bridge.py` or `python bridge/run_bridge.py suite`.'
        )

    st.sidebar.caption(
        f'{len(structural)} structural · {len(cs_runs)} cognitive synergy'
    )

    # Cognitive synergy: tabbed battery hub (does not require a selected CIP-style run)
    if surface == 'cognitive_synergy':
        if not runs:
            inv = data.battery_inventory(OUTPUT_ROOT)
            has_product = bool(
                inv.get('ablations') or inv.get('probes') or inv.get('end_snapshot')
            )
            if not has_product:
                st.warning(empty_msg)
                st.stop()
            st.info(
                'No per-cell metrics.csv yet, but battery products were found — '
                'showing overview / grids / series.'
            )
        cognitive_synergy_view.render_surface(OUTPUT_ROOT, runs)
        return

    if not runs:
        st.warning(empty_msg)
        st.stop()

    by_key = {str(r.directory): r for r in runs}
    keys = list(by_key.keys())
    sess_key = f'selected_run_dir_{surface}'
    default_key = _pick_default_key(runs, keys)

    if sess_key not in st.session_state or st.session_state[sess_key] not in by_key:
        st.session_state[sess_key] = default_key

    selected_key = st.sidebar.selectbox(
        'Runs',
        keys,
        format_func=lambda k: _format_run_label(by_key[k]),
        key=sess_key,
    )
    selected = by_key[selected_key]

    # Structural CIP views
    if selected.state == 'stale':
        t = data.STALE_THRESHOLD_SECONDS
        label = f'{t // 60}m' if t >= 60 else f'{t}s'
        st.warning(
            f'No summary.json and no CIP activity in over {label} '
            '— this run may have crashed or been abandoned.'
        )
        live_view.render(selected)
    elif selected.state == 'live':
        live_view.render(selected)
    else:
        completed_view.render(selected)


if __name__ == '__main__':
    main()
