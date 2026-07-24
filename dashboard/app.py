"""CAIRN live evaluation dashboard.

Run with: streamlit run dashboard/app.py --server.port 8501
(from the CAIRN/ directory, with venv activated)

Also auto-launched by tools/recorder.py's init_recorder() at the start of any
eval run (demo.metta, mve.metta, assignment.metta) if it isn't already up.
"""

import sys
from pathlib import Path

# Ensure sibling modules (data.py, charts.py, live_view.py, completed_view.py)
# import cleanly regardless of whether the runner puts this script's own
# directory on sys.path (streamlit's CLI and its AppTest harness differ here).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

import charts
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


@st.cache_data(ttl=3)
def _cached_discover_runs(output_root_str: str):
    return data.discover_runs(Path(output_root_str))


def _format_run_label(run):
    badge = _STATE_BADGE.get(run.state, '')
    if run.state == 'complete':
        finished = _relative_time(_age_seconds(run.summary_path.stat().st_mtime))
        return f'{badge} {run.label} · complete · finished {finished}'
    if run.state == 'live':
        updated = _relative_time(_age_seconds(run.last_modified))
        return f'{badge} {run.label} · live · updated {updated}'
    halted = _relative_time(_age_seconds(run.last_modified))
    return f'{badge} {run.label} · stale · halted {halted}'


def _age_seconds(mtime):
    import time
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


def main():
    _inject_css()
    st.title('Evaluation Dashboard')

    runs = _cached_discover_runs(str(OUTPUT_ROOT))
    if not runs:
        st.warning(f'No *metrics.csv files found under {OUTPUT_ROOT}')
        st.stop()

    st.sidebar.button('Scan output dir', on_click=_cached_discover_runs.clear)
    selected = st.sidebar.selectbox('Runs', runs, format_func=_format_run_label, index=0)

    if selected.state == 'stale':
        t = data.STALE_THRESHOLD_SECONDS
        label = f'{t // 60}m' if t >= 60 else f'{t}s'
        st.warning(f'No summary.json and no metrics.csv update in over {label} '
                   '— this run may have crashed or been abandoned.')
        live_view.render(selected)
    elif selected.state == 'live':
        live_view.render(selected)
    else:
        completed_view.render(selected)


if __name__ == '__main__':
    main()
