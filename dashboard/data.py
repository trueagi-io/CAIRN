"""Read-only data layer for the CAIRN dashboard.

Two surfaces (never mixed in charts):
  structural — output/{demo,mve,benchmark}/  (CIP insect/poison)
  cognitive_synergy — output/cognitive_synergy/<fixture>/  (bridge protocols)
"""

from __future__ import annotations

import io
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

_FUNDS_PATTERN = re.compile(r'updateAttentionParam\s+(FUNDS_STI|FUNDS_LTI)\s+([\d.eE+-]+)')
_ENTRYPOINTS = ('demo.metta', 'mve.metta', 'assignment.metta')

# Only these subdirs under output/ are structural CIP runners.
_STRUCTURAL_RUN_DIRS = frozenset({'demo', 'mve', 'benchmark'})
_CS_ROOT_NAME = 'cognitive_synergy'

# Live = last CIP row still arriving (short window so killed runs drop quickly).
LIVE_THRESHOLD_SECONDS = 90
STALE_THRESHOLD_SECONDS = 30 * 60

CSV_FIELDS = [
    'cip_index', 'timestamp', 'af_size',
    'af_size_ratio', 'sti_concentration', 'link_density',
    'effectiveness', 'partial_effectiveness', 'metric_delta', 'resource_cost',

    'attention_coherence', 'context_retention',
    'distributed_importance', 'selective_modulation', 'connection_ratio',
    'preallocation_space',
    'triangles', 'betti_0', 'betti_1', 'betti_2'
]

_BRIDGE_CSV_MARKERS = frozenset({
    'protocol',
    'weighted_solved', 'influenced_solved', 'distracted_solved',
    # legacy arm columns (pre-rename runs)
    'full_solved', 'af_solved', 'random_solved',
    'query_af_overlap', 'sti_gain_sum',
})

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
    kind: str = "structural"  # "structural" | "cognitive_synergy"
    extras: dict = field(default_factory=dict)


def summary_is_current(metrics_path: Path, summary_path: Path) -> bool:
    """A summary.json only counts as belonging to the current run if it's at
    least as new as metrics.csv -- otherwise it's a stale leftover from a
    previous run into the same output dir/prefix (e.g. a restarted demo.metta)."""
    return summary_path.exists() and summary_path.stat().st_mtime >= metrics_path.stat().st_mtime


def _is_bridge_metrics(metrics_path: Path, directory: Path) -> bool:
    """True if this metrics.csv is the ECAN–PLN bridge (standalone), not CIP."""
    parts = {p.lower() for p in directory.parts}
    if "cognitive_synergy" in parts or "synergy" in parts:
        return True
    try:
        with open(metrics_path, "r", encoding="utf-8") as f:
            header = {c.strip() for c in f.readline().strip().split(",")}
        if header & _BRIDGE_CSV_MARKERS:
            return True
    except OSError:
        pass
    return False


def _last_cip_activity_unix(metrics_path: Path) -> float:
    """Unix time of last CIP row (timestamp column), else metrics.csv mtime."""
    try:
        with open(metrics_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) < 2:
            return metrics_path.stat().st_mtime
        header = [h.strip() for h in lines[0].rstrip("\n").split(",")]
        if "timestamp" not in header:
            return metrics_path.stat().st_mtime
        ti = header.index("timestamp")
        # walk last non-empty data lines
        for line in reversed(lines[1:]):
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split(",")
            if ti >= len(parts):
                continue
            ts = parts[ti].strip()
            try:
                from datetime import datetime
                return datetime.fromisoformat(ts).timestamp()
            except ValueError:
                continue
        return metrics_path.stat().st_mtime
    except OSError:
        return 0.0


def _summary_completed_unix(summary_path: Path) -> float | None:
    if not summary_path.exists():
        return None
    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        ts = report.get("completed_at") or report.get("run_timestamp")
        if ts:
            from datetime import datetime
            return datetime.fromisoformat(str(ts)).timestamp()
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    try:
        return summary_path.stat().st_mtime
    except OSError:
        return None


def _run_state(metrics_path: Path, summary_path: Path) -> str:
    """live only if CIPs are actively arriving for a run that is not finished."""
    if summary_is_current(metrics_path, summary_path):
        return "complete"

    activity = _last_cip_activity_unix(metrics_path)
    age = time.time() - activity
    done_at = _summary_completed_unix(summary_path)

    # New CIPs after a previous summary → in-progress only if still fresh.
    post_summary = done_at is None or activity > (done_at + 1.0)
    if post_summary and age < LIVE_THRESHOLD_SECONDS:
        return "live"

    if summary_path.exists():
        return "complete"
    if age < STALE_THRESHOLD_SECONDS:
        return "stale"
    return "stale"


def discover_structural_runs(output_root: Path) -> list[RunInfo]:
    """CIP runs under output/{demo,mve,benchmark}/ only."""
    if not output_root.exists():
        return []

    runs = []
    for metrics_path in output_root.rglob('*metrics.csv'):
        if metrics_path.parent.name == "runs":
            continue
        directory = metrics_path.parent
        if _is_bridge_metrics(metrics_path, directory):
            continue

        try:
            rel_dir = directory.relative_to(output_root)
        except ValueError:
            continue
        if str(rel_dir) == '.':
            continue
        top = rel_dir.parts[0] if rel_dir.parts else None
        if top not in _STRUCTURAL_RUN_DIRS:
            continue

        prefix = metrics_path.name[:-len('metrics.csv')]
        trends_path = directory / f'{prefix}trends.csv'
        summary_path = directory / f'{prefix}summary.json'
        label = str(rel_dir) if not prefix else f'{rel_dir} [{prefix.rstrip("-")}]'

        mtime = metrics_path.stat().st_mtime
        row_count = _quick_row_count(metrics_path)
        state = _run_state(metrics_path, summary_path)

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
            kind="structural",
        ))

    return _sort_runs(runs)


def classify_cs_label(label: str) -> dict:
    """Tag a cognitive_synergy fixture path for UI grouping / labels.

    Returns keys: battery, family, short, sort_key.
    battery ∈ {B1, B2, B3, B4, other}
    family  ∈ {tabulated, feedback, end_cell, mid_cell, series, other}
    """
    name = (label or "").replace("\\", "/").split("/")[-1]
    low = name.lower()

    # Live / offline probe series dirs (protocol_probes.csv parents)
    if low.startswith("mve_pln_probe"):
        if "closed" in low:
            return {
                "battery": "B4",
                "family": "series",
                "short": "B4 closed (live wage)",
                "sort_key": (4, 1, name),
            }
        if "open" in low:
            return {
                "battery": "B4",
                "family": "series",
                "short": "B4 open (live control)",
                "sort_key": (4, 0, name),
            }
        return {
            "battery": "B3",
            "family": "series",
            "short": "B3 offline probes",
            "sort_key": (3, 0, name),
        }

    if low.startswith("feedback_from_mve") or (
        low.startswith("feedback_") and "slice" not in low and "roman" not in low
    ):
        return {
            "battery": "B2",
            "family": "feedback",
            "short": f"B2 feedback · {name}",
            "sort_key": (2, 2, name),
        }
    if low.startswith("feedback_"):
        return {
            "battery": "B1",
            "family": "feedback",
            "short": f"B1 feedback · {name}",
            "sort_key": (1, 2, name),
        }

    if low.startswith("from_mve_cip"):
        return {
            "battery": "B3",
            "family": "mid_cell",
            "short": f"B3 cell · {name}",
            "sort_key": (3, 2, name),
        }
    if low.startswith("from_mve_"):
        return {
            "battery": "B2",
            "family": "end_cell",
            "short": f"B2 cell · {name}",
            "sort_key": (2, 1, name),
        }

    if low.startswith("roman") or low.startswith("slice"):
        return {
            "battery": "B1",
            "family": "tabulated",
            "short": f"B1 · {name}",
            "sort_key": (1, 0, name),
        }

    return {
        "battery": "other",
        "family": "other",
        "short": name,
        "sort_key": (9, 0, name),
    }


def discover_cs_runs(output_root: Path) -> list[RunInfo]:
    """Bridge protocol runs under output/cognitive_synergy/<fixture>/."""
    cs_root = output_root / _CS_ROOT_NAME
    if not cs_root.is_dir():
        return []

    runs = []
    for metrics_path in cs_root.rglob('metrics.csv'):
        if metrics_path.parent.name == "runs":
            continue
        directory = metrics_path.parent
        # only direct fixture dirs (or one level under ablations if they ever get metrics)
        try:
            rel = directory.relative_to(cs_root)
        except ValueError:
            continue
        # Skip nested cell dumps under series dirs (e.g. mve_pln_probe/cells/…)
        if "cells" in rel.parts:
            continue
        if not _is_bridge_metrics(metrics_path, directory):
            continue

        summary_path = directory / 'summary.json'
        mtime = metrics_path.stat().st_mtime
        if summary_path.exists():
            mtime = max(mtime, summary_path.stat().st_mtime)
        row_count = _quick_row_count(metrics_path)
        state = "complete" if summary_is_current(metrics_path, summary_path) else (
            "complete" if summary_path.exists() else "stale"
        )
        label = str(rel).replace("\\", "/")
        protocol = None
        summary = read_summary_json(summary_path) if summary_path.exists() else None
        if summary:
            protocol = (summary.get("parameters") or {}).get("protocol")
            if not protocol and (summary.get("parameters") or {}).get("mode") == "offline_grid":
                protocol = "cip_probe"
            if not protocol and summary.get("arms"):
                protocol = "steering"

        meta = classify_cs_label(label)
        extras = {
            "protocol": protocol,
            "battery": meta["battery"],
            "family": meta["family"],
            "short": meta["short"],
            "sort_key": meta["sort_key"],
        }

        runs.append(RunInfo(
            directory=directory,
            prefix='',
            metrics_path=metrics_path,
            trends_path=directory / 'trends.csv',  # unused for CS
            summary_path=summary_path,
            label=label,
            state=state,
            last_modified=mtime,
            row_count=row_count,
            kind="cognitive_synergy",
            extras=extras,
        ))

    return _sort_cs_runs(runs)


def _sort_cs_runs(runs: list[RunInfo]) -> list[RunInfo]:
    """Battery order then recency within family."""
    def key(r: RunInfo):
        sk = (r.extras or {}).get("sort_key") or (9, 0, r.label)
        return (sk[0], sk[1], -r.last_modified, sk[2] if len(sk) > 2 else r.label)

    return sorted(runs, key=key)


def discover_runs(output_root: Path) -> list[RunInfo]:
    """Structural CIP runs only (back-compat for callers that expect CIP list)."""
    return discover_structural_runs(output_root)


def discover_all_runs(output_root: Path) -> dict[str, list[RunInfo]]:
    return {
        "structural": discover_structural_runs(output_root),
        "cognitive_synergy": discover_cs_runs(output_root),
    }


def list_ablations_reports(output_root: Path) -> list[Path]:
    """All B2 ablations index.json paths, newest first."""
    root = output_root / _CS_ROOT_NAME / "ablations"
    if not root.is_dir():
        return []
    found: list[tuple[float, Path]] = []
    for p in root.glob("*/index.json"):
        try:
            found.append((p.stat().st_mtime, p))
        except OSError:
            continue
    found.sort(key=lambda t: -t[0])
    return [p for _m, p in found]


def find_ablations_report(output_root: Path) -> Path | None:
    """B2 coupled grid table (ablations/from_*/index.json), if present."""
    reports = list_ablations_reports(output_root)
    if reports:
        return reports[0]
    # Legacy multi-seed rates filename (pre-cleanup)
    legacy = output_root / _CS_ROOT_NAME / "ablations" / "from_mve" / "rates_multiseed.json"
    return legacy if legacy.is_file() else None


# Back-compat name used by older callers
find_rates_report = find_ablations_report


def list_probe_series(output_root: Path) -> list[Path]:
    """All protocol_probes.csv under cognitive_synergy (B3 offline + B4 open/closed).

    Newest first. Skips nested copies under cells/.
    """
    cs_root = output_root / _CS_ROOT_NAME
    if not cs_root.is_dir():
        return []
    found: list[tuple[float, Path]] = []
    for p in cs_root.glob("*/protocol_probes.csv"):
        if "cells" in p.parts:
            continue
        try:
            found.append((p.stat().st_mtime, p))
        except OSError:
            continue
    found.sort(key=lambda t: -t[0])
    return [p for _m, p in found]


def find_probe_series(output_root: Path) -> Path | None:
    """Preferred single probe series: offline B3, else newest protocol_probes.csv."""
    series = list_probe_series(output_root)
    if not series:
        return None
    for p in series:
        if p.parent.name == "mve_pln_probe":
            return p
    return series[0]


def battery_inventory(output_root: Path) -> dict:
    """Quick presence map for Overview cards (B1–B4 artifacts)."""
    cs = output_root / _CS_ROOT_NAME
    runs = discover_cs_runs(output_root) if cs.is_dir() else []
    by_bat = {"B1": 0, "B2": 0, "B3": 0, "B4": 0, "other": 0}
    for r in runs:
        b = (r.extras or {}).get("battery") or "other"
        by_bat[b] = by_bat.get(b, 0) + 1
    probes = list_probe_series(output_root)
    open_p = next((p for p in probes if "open" in p.parent.name), None)
    closed_p = next((p for p in probes if "closed" in p.parent.name), None)
    offline_p = next((p for p in probes if p.parent.name == "mve_pln_probe"), None)
    snap = output_root / "mve" / "bridge_snapshot.json"
    wage_dir = output_root / "mve" / "wage"
    wage_n = len(list(wage_dir.glob("cip_*_wage.json"))) if wage_dir.is_dir() else 0
    return {
        "cell_counts": by_bat,
        "ablations": list_ablations_reports(output_root),
        "probes": probes,
        "probe_offline": offline_p,
        "probe_open": open_p,
        "probe_closed": closed_p,
        "end_snapshot": snap if snap.is_file() else None,
        "wage_n": wage_n,
    }


def write_output_index(output_root: Path) -> Path:
    """Write output/index.json listing structural + cognitive_synergy runs."""
    structural = discover_structural_runs(output_root)
    cs = discover_cs_runs(output_root)
    ablations = find_ablations_report(output_root)
    probes = list_probe_series(output_root)

    def _entry(r: RunInfo) -> dict:
        try:
            directory_rel = str(r.directory.relative_to(output_root))
        except ValueError:
            directory_rel = str(r.directory)
        return {
            "kind": r.kind,
            "label": r.label,
            "directory": directory_rel,
            "state": r.state,
            "battery": (r.extras or {}).get("battery"),
            "family": (r.extras or {}).get("family"),
            "metrics": r.metrics_path.name,
            "summary": r.summary_path.name if r.summary_path.exists() else None,
            "row_count": r.row_count,
            "last_modified": r.last_modified,
            **(r.extras or {}),
        }

    index = {
        "surfaces": {
            "structural": [_entry(r) for r in structural],
            "cognitive_synergy": [_entry(r) for r in cs],
        },
        "ablations": str(ablations.relative_to(output_root)) if ablations else None,
        "protocol_probes": [
            str(p.relative_to(output_root)) for p in probes
        ],
        "n_structural": len(structural),
        "n_cognitive_synergy": len(cs),
    }
    path = output_root / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
        f.write("\n")
    return path


def _sort_runs(runs: list[RunInfo]) -> list[RunInfo]:
    _state_rank = {"live": 0, "complete": 1, "stale": 2}
    runs.sort(key=lambda r: (_state_rank.get(r.state, 9), -r.last_modified))
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
        # Upstream logger name → CAIRN distributed importance (same STI/LTI Pearson)
        if 'cognitive_synergy' in df.columns and 'distributed_importance' not in df.columns:
            df = df.rename(columns={'cognitive_synergy': 'distributed_importance'})
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
