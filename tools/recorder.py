"""CAIRN evaluation recorder — CSV time-series + JSON summary."""

import csv
import json
import os
from datetime import datetime

_csv_file = None
_csv_writer = None
_output_dir = None
_run_timestamp = None
_prefix = ''

DASHBOARD_PORT = 8501  # streamlit's own default; keep explicit so manual `streamlit run` matches


def _ensure_dashboard_running():
    """Opt-in (set CAIRN_WATCH=1), best-effort: start the dashboard if nothing
    is answering its health endpoint, and open a browser tab only on that cold
    start. Never raises -- a dashboard hiccup must not break the eval run."""
    if not os.environ.get('CAIRN_WATCH'):
        return

    import subprocess, sys, time, urllib.request, urllib.error, webbrowser
    from pathlib import Path

    url = f'http://localhost:{DASHBOARD_PORT}'
    health = f'{url}/_stcore/health'

    try:
        with urllib.request.urlopen(health, timeout=0.3) as resp:
            if resp.status == 200:
                return  # a real Streamlit instance is already up; don't reopen a tab
    except (urllib.error.URLError, OSError):
        pass  # nothing there (or not Streamlit) -- fall through to start one

    try:
        cairn_root = Path(__file__).resolve().parent.parent
        dashboard_app = cairn_root / 'dashboard' / 'app.py'
        # sys.executable is unreliable here: recorder.py runs inside Janus's
        # in-process embedded Python, where sys.executable resolves to the
        # swipl binary, not a real python interpreter. Use the venv directly.
        venv_python = cairn_root / 'venv' / 'bin' / 'python'
        python_bin = str(venv_python) if venv_python.exists() else sys.executable

        subprocess.Popen(
            [python_bin, '-m', 'streamlit', 'run', str(dashboard_app),
             '--server.port', str(DASHBOARD_PORT), '--server.headless', 'true'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
        for _ in range(30):  # ~15s cold-boot budget
            try:
                with urllib.request.urlopen(health, timeout=0.3) as resp:
                    if resp.status == 200:
                        break
            except (urllib.error.URLError, OSError):
                time.sleep(0.5)
        webbrowser.open(url)
    except Exception as e:
        print(f'[recorder] could not auto-start dashboard: {e}', file=sys.stderr)


CSV_FIELDS = [
    'cip_index', 'timestamp', 'af_size',
    'af_size_ratio', 'sti_concentration', 'link_density',
    'effectiveness', 'partial_effectiveness', 'metric_delta', 'resource_cost',
    'attention_coherence', 'context_retention',
    'distributed_importance', 'selective_modulation', 'connection_ratio',
    'preallocation_space',
    'triangles', 'betti_0', 'betti_1', 'betti_2'
]


def init_recorder(output_dir='output', prefix=''):
    global _csv_file, _csv_writer, _output_dir, _run_timestamp, _prefix
    _ensure_dashboard_running()
    _output_dir = str(output_dir)
    _prefix = (str(prefix) + '-') if prefix else ''
    _run_timestamp = datetime.now().isoformat()
    os.makedirs(_output_dir, exist_ok=True)
    path = os.path.join(_output_dir, f'{_prefix}metrics.csv')
    _csv_file = open(path, 'w', newline='')
    _csv_writer = csv.DictWriter(_csv_file, fieldnames=CSV_FIELDS)
    _csv_writer.writeheader()
    _csv_file.flush()
    return 'initialized'


def record_cip(cip_index, af_size,
               af_size_ratio, sti_concentration, link_density,
               effectiveness='N/A', partial_effectiveness='N/A',
               metric_delta='N/A', resource_cost='N/A',
               attention_coherence=0.0, context_retention='N/A',
               distributed_importance=0.0, selective_modulation=0.0,
               connection_ratio=0.0, preallocation_space=0.0,
               triangles=0, betti_0=0, betti_1=0, betti_2=0):
    """effectiveness = total (baseline→curr); partial_effectiveness = prev→curr."""
    global _csv_writer, _csv_file
    if _csv_writer is None:
        return 'no_recorder'
    row = {
        'cip_index': int(cip_index),
        'timestamp': datetime.now().isoformat(),
        'af_size': int(af_size),
        'af_size_ratio': float(af_size_ratio),
        'sti_concentration': float(sti_concentration),
        'link_density': float(link_density),
        'effectiveness': _float_or_na(effectiveness),
        'partial_effectiveness': _float_or_na(partial_effectiveness),
        'metric_delta': _float_or_na(metric_delta),
        'resource_cost': _float_or_na(resource_cost),
        'attention_coherence': _safe_float(attention_coherence),
        'context_retention': _float_or_na(context_retention),
        'distributed_importance': _safe_float(distributed_importance),
        'selective_modulation': _safe_float(selective_modulation),
        'connection_ratio': _safe_float(connection_ratio),
        'preallocation_space': _safe_float(preallocation_space),
        'triangles': _int_or_na(triangles),
        'betti_0': _int_or_na(betti_0),
        'betti_1': _int_or_na(betti_1),
        'betti_2': _int_or_na(betti_2)
    }
    _csv_writer.writerow(row)
    _csv_file.flush()
    return 'wrote'


def write_summary(params, resource, topology, effectiveness_val, atom_trends):
    global _output_dir, _run_timestamp
    if _output_dir is None:
        return 'no_recorder'

    params_dict = _pairs_to_dict(params)
    resource_dict = _pairs_to_dict(resource, numeric=True)

    topology_dict = {}
    if topology:
        keys = ['triangles', 'betti_0', 'betti_1', 'betti_2', 'hebbian_links']
        vals = list(topology) if not isinstance(topology, list) else topology
        for k, v in zip(keys, vals):
            topology_dict[k] = _to_number(v)

    trends_list = []
    if atom_trends:
        for entry in atom_trends:
            e = list(entry) if not isinstance(entry, list) else entry
            # Skip constructor prefix (TrendEntry) if present
            if len(e) >= 4 and str(e[0]) == 'TrendEntry':
                e = e[1:]
            if len(e) >= 3:
                trends_list.append({
                    'atom': str(e[0]),
                    'trend': str(e[1]),
                    'volatility': float(e[2])
                })

    # Derived aggregate metrics from the per-atom trend data
    if trends_list:
        total   = len(trends_list)
        stable  = sum(1 for e in trends_list if e['trend'] == 'stable')
        rising  = sum(1 for e in trends_list if e['trend'] == 'rising')
        falling = sum(1 for e in trends_list if e['trend'] == 'falling')
        vols    = [e['volatility'] for e in trends_list]
        af_trend_summary = {
            'af_stability_ratio':   stable / total,
            'mean_af_volatility':   sum(vols) / total,
            'attention_trajectory': rising - falling,
        }
    else:
        af_trend_summary = {}

    # trends.csv — flat per-atom rows for direct visualization
    trends_csv_path = os.path.join(_output_dir, f'{_prefix}trends.csv')
    with open(trends_csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['atom', 'trend', 'volatility'])
        writer.writeheader()
        writer.writerows(trends_list)

    report = {
        'run_timestamp': _run_timestamp,
        'completed_at': datetime.now().isoformat(),
        'parameters': params_dict,
        'resource_metrics': resource_dict,
        'topology': topology_dict,
        'effectiveness': float(effectiveness_val) if effectiveness_val is not None else None,
        'af_trend_summary': af_trend_summary,
    }

    path = os.path.join(_output_dir, f'{_prefix}summary.json')
    with open(path, 'w') as f:
        json.dump(report, f, indent=2)
    return 'wrote'


def append_probe_metrics(maintenance, glocal):
    """Add cognitive_maintenance and glocal_coordination to the existing summary.json."""
    if _output_dir is None:
        return 'no_recorder'
    path = os.path.join(_output_dir, f'{_prefix}summary.json')
    try:
        with open(path) as f:
            report = json.load(f)
    except FileNotFoundError:
        return 'no_summary'
    report['probe_metrics'] = {
        'cognitive_maintenance': _safe_float(maintenance),
        'glocal_coordination': _safe_float(glocal)
    }
    with open(path, 'w') as f:
        json.dump(report, f, indent=2)
    return 'wrote'


def append_benchmark_comparison(baseline_eff, optimized_eff, gained_efficiency):
    """Add a comparison-vs-baseline block to the existing summary.json.

    baseline_eff/optimized_eff are each run's mean recorded effectiveness
    across its full CIP history (see tools/utils.py's read_avg_effectiveness);
    gained_efficiency is measure-gained-efficiency-from-eff's result.
    """
    if _output_dir is None:
        return 'no_recorder'
    path = os.path.join(_output_dir, f'{_prefix}summary.json')
    try:
        with open(path) as f:
            report = json.load(f)
    except FileNotFoundError:
        return 'no_summary'
    report['benchmark_comparison'] = {
        'baseline_mean_effectiveness': _safe_float(baseline_eff),
        'optimized_mean_effectiveness': _safe_float(optimized_eff),
        'gained_efficiency': _safe_float(gained_efficiency)
    }
    with open(path, 'w') as f:
        json.dump(report, f, indent=2)
    return 'wrote'


def close_recorder():
    global _csv_file, _csv_writer
    if _csv_file:
        _csv_file.flush()
        _csv_file.close()
        _csv_file = None
        _csv_writer = None
    return 'closed'


def _pairs_to_dict(pairs, numeric=False):
    result = {}
    if not pairs:
        return result
    for pair in pairs:
        p = list(pair) if not isinstance(pair, list) else pair
        if len(p) >= 2:
            k, v = str(p[0]), p[1]
            result[k] = float(v) if numeric else str(v)
    return result


def _float_or_na(val):
    """String marker (e.g. 'N/A') -> literal 'N/A'; otherwise a real float, possibly negative."""
    if isinstance(val, str):
        return 'N/A'
    return float(val)


def _int_or_na(val):
    """String marker (e.g. 'N/A') -> literal 'N/A'; otherwise a real int."""
    if isinstance(val, str):
        return 'N/A'
    return int(val)


def _safe_float(val, default=0.0):
    """Convert MeTTa value to float. Handles empty-list results from car-atom(collapse(...))."""
    if isinstance(val, (list, tuple)):
        return float(val[0]) if len(val) == 1 else default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _to_number(val):
    try:
        v = float(val)
        return int(v) if v == int(v) else v
    except (ValueError, TypeError):
        return str(val)
