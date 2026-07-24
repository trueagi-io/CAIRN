"""Read-only data layer for the CAIRN dashboard.

Discovers eval runs under output/ and parses their CSV/JSON artifacts
defensively, since metrics.csv may be mid-flush from a live run. No
Streamlit imports here, so this module can be exercised directly against
real output files without launching the app.
"""

from __future__ import annotations

import io
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

_FUNDS_PATTERN = re.compile(r'updateAttentionParam\s+(FUNDS_STI|FUNDS_LTI)\s+([\d.eE+-]+)')
_ENTRYPOINTS = ('demo.metta', 'mve.metta', 'assignment.metta')

STALE_THRESHOLD_SECONDS = 30 * 60  # was 90; agent/topo gaps >> that

CSV_FIELDS = [
    'cip_index', 'timestamp', 'af_size',
    'af_size_ratio', 'sti_concentration', 'link_density',
    'effectiveness', 'local_effectiveness', 'metric_delta', 'resource_cost',

    'attention_coherence', 'context_retention',
    'distributed_importance', 'selective_modulation', 'connection_ratio',
    'preallocation_space',
    'triangles', 'betti_0', 'betti_1', 'betti_2'
]

_csv_cache: dict[str, pd.DataFrame] = {}
_json_cache: dict[str, dict] = {}
_trends_cache: dict[str, pd.DataFrame] = {}


@dataclass
class RunInfo:
    directory: Path
    prefix: str
    metrics_path: Path
    trends_path: Path
    summary_path: Path
    label: str
    state: str  # "live" | "complete" | "stale"
    last_modified: float
    row_count: int


def summary_is_current(metrics_path: Path, summary_path: Path) -> bool:
    """A summary.json only counts as belonging to the current run if it's at
    least as new as metrics.csv -- otherwise it's a stale leftover from a
    previous run into the same output dir/prefix (e.g. a restarted demo.metta)."""
    return summary_path.exists() and summary_path.stat().st_mtime >= metrics_path.stat().st_mtime


def discover_runs(output_root: Path) -> list[RunInfo]:
    """Find every run under output_root, identified by a *metrics.csv file."""
    if not output_root.exists():
        return []

    runs = []
    for metrics_path in output_root.rglob('*metrics.csv'):
        directory = metrics_path.parent
        prefix = metrics_path.name[:-len('metrics.csv')]
        trends_path = directory / f'{prefix}trends.csv'
        summary_path = directory / f'{prefix}summary.json'

        rel_dir = directory.relative_to(output_root)
        dir_label = str(rel_dir) if str(rel_dir) != '.' else '(root)'
        label = f'{dir_label} [{prefix.rstrip("-")}]' if prefix else dir_label

        mtime = metrics_path.stat().st_mtime
        row_count = _quick_row_count(metrics_path)

        if summary_is_current(metrics_path, summary_path):
            state = 'complete'
        elif (time.time() - mtime) < STALE_THRESHOLD_SECONDS:
            state = 'live'
        else:
            state = 'stale'

        runs.append(RunInfo(
            directory=directory,
            prefix=prefix,
            metrics_path=metrics_path,
            trends_path=trends_path,
            summary_path=summary_path,
            label=label,
            state=state,
            last_modified=mtime,
            row_count=row_count,
        ))

    runs.sort(key=lambda r: r.last_modified, reverse=True)
    return runs


def _quick_row_count(path: Path) -> int:
    try:
        with open(path, 'r') as f:
            return max(sum(1 for _ in f) - 1, 0)  # minus header
    except OSError:
        return 0


def read_metrics_csv(path: Path) -> pd.DataFrame:
    """Defensively parse metrics.csv, tolerating a mid-flush torn last line."""
    key = str(path)
    try:
        with open(path, 'r', newline='') as f:
            lines = f.readlines()
        if not lines:
            return _csv_cache.get(key, pd.DataFrame(columns=CSV_FIELDS))

        header = lines[0].rstrip('\n').split(',')
        expected_fields = len(header)
        good_lines = [lines[0]]
        for line in lines[1:]:
            if len(line.rstrip('\n').split(',')) == expected_fields:
                good_lines.append(line)

        df = pd.read_csv(io.StringIO(''.join(good_lines)), na_values=['N/A'])
        _csv_cache[key] = df
        return df
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return _csv_cache.get(key, pd.DataFrame(columns=CSV_FIELDS))


def read_summary_json(path: Path) -> dict | None:
    key = str(path)
    try:
        with open(path, 'r') as f:
            report = json.load(f)
        _json_cache[key] = report
        return report
    except (OSError, json.JSONDecodeError):
        return _json_cache.get(key)


def parse_initial_funds(cairn_root: Path) -> dict:
    """FUNDS_STI/FUNDS_LTI are set once as a literal near the top of each
    entrypoint .metta file, never computed -- read the actual value instead
    of hardcoding it. Returns None for a key if the entrypoints disagree or
    none could be read."""
    values = {}
    for entrypoint in _ENTRYPOINTS:
        try:
            text = (cairn_root / entrypoint).read_text()
        except OSError:
            continue
        for key, value in _FUNDS_PATTERN.findall(text):
            values.setdefault(key, set()).add(float(value))
    return {key: (vals.pop() if len(vals) == 1 else None) for key, vals in values.items()}


def read_trends_csv(path: Path) -> pd.DataFrame:
    key = str(path)
    try:
        df = pd.read_csv(path)
        _trends_cache[key] = df
        return df
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return _trends_cache.get(key, pd.DataFrame(columns=['atom', 'trend', 'volatility']))
