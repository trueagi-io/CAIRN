"""Dashboard panel for ECAN–PLN cognitive synergy (not CIP time series).

Surfaces B1–B4 products: tabulated/end cells, B2 ablations grid, mid-run /
live probe series (open vs closed), and single-cell detail.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
import pandas as pd

import charts
import data


# ─── surface entry ───────────────────────────────────────────────────────────

_CS_PAGES = (
    "Overview",
    "B2 grid",
    "B3 / B4 trajectories",
    "Single cell",
)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_inventory(output_root_str: str) -> dict:
    """Disk inventory; paths stored as strings for cache stability."""
    inv = data.battery_inventory(Path(output_root_str))
    return _inv_to_cacheable(inv)


@st.cache_data(ttl=30, show_spinner=False)
def _cached_cs_runs(output_root_str: str):
    """Cell runs for Single-cell panel (own cache; no import from app)."""
    return data.discover_cs_runs(Path(output_root_str))


def _inv_to_cacheable(inv: dict) -> dict:
    def pstr(p):
        return str(p) if p is not None else None

    return {
        "cell_counts": inv.get("cell_counts") or {},
        "ablations": [pstr(p) for p in (inv.get("ablations") or [])],
        "probes": [pstr(p) for p in (inv.get("probes") or [])],
        "probe_offline": pstr(inv.get("probe_offline")),
        "probe_open": pstr(inv.get("probe_open")),
        "probe_closed": pstr(inv.get("probe_closed")),
        "end_snapshot": pstr(inv.get("end_snapshot")),
        "wage_n": inv.get("wage_n") or 0,
    }


def _inv_from_cacheable(raw: dict) -> dict:
    def p(s):
        return Path(s) if s else None

    return {
        "cell_counts": raw.get("cell_counts") or {},
        "ablations": [Path(s) for s in (raw.get("ablations") or [])],
        "probes": [Path(s) for s in (raw.get("probes") or [])],
        "probe_offline": p(raw.get("probe_offline")),
        "probe_open": p(raw.get("probe_open")),
        "probe_closed": p(raw.get("probe_closed")),
        "end_snapshot": p(raw.get("end_snapshot")),
        "wage_n": raw.get("wage_n") or 0,
    }


def render_surface(output_root: Path, runs: list["data.RunInfo"]):
    """Top-level CS surface.

    Uses exclusive page radio (only one panel runs) + ``@st.fragment`` so
    selectboxes inside a panel do not re-execute the whole app shell.
    """
    inv = _inv_from_cacheable(_cached_inventory(str(output_root)))

    # Exclusive nav — st.tabs still execute *all* tab bodies every run.
    page = st.radio(
        "Page",
        list(_CS_PAGES),
        horizontal=True,
        label_visibility="collapsed",
        key="cs_page",
    )

    root_s = str(output_root)
    if page == "Overview":
        render_overview(output_root, runs, inv)
    elif page == "B2 grid":
        _b2_panel(root_s)
    elif page == "B3 / B4 trajectories":
        _traj_panel(root_s)
    else:
        _cell_panel(root_s)


@st.fragment
def _b2_panel(output_root_str: str):
    """Fragment: only this panel re-runs when the report selectbox changes."""
    inv = _inv_from_cacheable(_cached_inventory(output_root_str))
    reports = inv.get("ablations") or []
    if not reports:
        st.info(
            "No B2 ablations table yet. "
            "Run `python bridge/mve_bridge.py --offline-grid …`."
        )
        return
    labels = [p.parent.name for p in reports]
    pick = st.selectbox(
        "Ablations report",
        range(len(reports)),
        format_func=lambda i: labels[i],
        key="cs_ablations_pick",
    )
    render_rates_report(reports[pick])


@st.fragment
def _traj_panel(output_root_str: str):
    inv = _inv_from_cacheable(_cached_inventory(output_root_str))
    render_trajectory_hub(None, inv)


@st.fragment
def _cell_panel(output_root_str: str):
    render_cell_browser(_cached_cs_runs(output_root_str))


def render_overview(
    output_root: Path,
    runs: list["data.RunInfo"],
    inv: dict | None = None,
):
    st.subheader("Cognitive synergy · battery overview")
    st.caption(
        "ECAN–PLN bridge: **weighted** / **influenced** / **distracted** under fixed budget B. "
        "Separate from structural CIP effectiveness metrics."
    )

    inv = inv or data.battery_inventory(output_root)
    counts = inv.get("cell_counts") or {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("B1 cells", counts.get("B1", 0), help="roman / slice / feedback_slice")
    c2.metric("B2 cells", counts.get("B2", 0), help="from_mve_* end-of-run + feedback")
    c3.metric("B3 cells", counts.get("B3", 0), help="from_mve_cip* offline mid-run cells")
    c4.metric("Series dirs", len(inv.get("probes") or []), help="protocol_probes.csv roots")

    st.markdown("##### Artifacts")
    a1, a2, a3, a4 = st.columns(4)
    snap = inv.get("end_snapshot")
    a1.markdown(
        f"**End snapshot**  \n"
        + (
            f"`{snap.relative_to(output_root)}`"
            if snap
            else "_missing — `mve_bridge --export-only`_"
        )
    )
    abl = inv.get("ablations") or []
    a2.markdown(
        f"**B2 ablations**  \n"
        + (f"{len(abl)} report(s)" if abl else "_none_")
    )
    off = inv.get("probe_offline")
    a3.markdown(
        f"**B3 offline series**  \n"
        + (f"`{off.parent.name}/`" if off else "_none_")
    )
    op, cl = inv.get("probe_open"), inv.get("probe_closed")
    wage_n = inv.get("wage_n") or 0
    a4.markdown(
        f"**B4 live**  \n"
        f"open={'✓' if op else '—'} · closed={'✓' if cl else '—'}  \n"
        f"wage files: **{wage_n}**"
    )

    # Rate cards from series summaries if present
    st.markdown("##### Headline rates (series summaries)")
    cols = st.columns(3)
    for col, path, title in (
        (cols[0], inv.get("probe_offline"), "B3 offline"),
        (cols[1], inv.get("probe_open"), "B4 open"),
        (cols[2], inv.get("probe_closed"), "B4 closed"),
    ):
        with col:
            st.markdown(f"**{title}**")
            if not path:
                st.caption("—")
                continue
            summary = data.read_summary_json(path.parent / "summary.json")
            rates = (summary or {}).get("rates") or {}
            if not rates:
                st.caption("no rates in summary.json")
                continue
            for k in (
                "influenced_solve",
                "weighted_solve",
                "distracted_solve",
                "influenced_beats_distracted",
            ):
                if k in rates:
                    st.metric(charts.label(k), _fmt_rate(rates[k]))

    st.caption(f"{len(runs)} cell runs discovered under `output/cognitive_synergy/`.")


def render_trajectory_hub(output_root: Path, inv: dict | None = None):
    """B3 offline + B4 open/closed protocol series (tables + rates, no bool charts)."""
    inv = inv or data.battery_inventory(output_root)
    series = inv.get("probes") or data.list_probe_series(output_root)
    if not series:
        st.info(
            "No `protocol_probes.csv` yet. "
            "B3: `mve_pln_probe.py --export-only` then `--offline-grid`. "
            "B4: live open + `--closed-loop` with separate `--out`."
        )
        return

    labels = [_series_label(p) for p in series]
    pick = st.selectbox(
        "Series",
        options=list(range(len(series))),
        format_func=lambda i: labels[i],
        key="cs_series_pick",
    )
    path = series[pick]
    render_probe_series(path, embedded=False)

    # Side-by-side rate strip when open+closed both exist
    op, cl = inv.get("probe_open"), inv.get("probe_closed")
    if op and cl:
        st.markdown("##### B4 open vs closed (rates)")
        rows = []
        for pth, name in ((op, "open"), (cl, "closed")):
            s = data.read_summary_json(pth.parent / "summary.json") or {}
            rates = s.get("rates") or {}
            rows.append(
                {
                    "run": name,
                    "W": _fmt_rate(rates.get("weighted_solve")),
                    "I": _fmt_rate(rates.get("influenced_solve")),
                    "D": _fmt_rate(rates.get("distracted_solve")),
                    "I beats D": _fmt_rate(rates.get("influenced_beats_distracted")),
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        wage_n = inv.get("wage_n") or 0
        st.caption(f"Closed-loop wage artifacts: **{wage_n}** file(s) under `output/mve/wage/`.")


def render_cell_browser(runs: list["data.RunInfo"]):
    """Filterable single-cell detail."""
    if not runs:
        st.info("No cell runs with metrics.csv.")
        return

    batteries = sorted(
        {(r.extras or {}).get("battery") or "other" for r in runs},
        key=lambda b: {"B1": 0, "B2": 1, "B3": 2, "B4": 3}.get(b, 9),
    )
    fams = sorted({(r.extras or {}).get("family") or "other" for r in runs})

    f1, f2 = st.columns(2)
    with f1:
        bat_sel = st.multiselect(
            "Battery",
            batteries,
            default=[b for b in batteries if b in ("B1", "B2")],
            key="cs_cell_battery",
        )
    with f2:
        fam_sel = st.multiselect(
            "Family",
            fams,
            default=fams,
            key="cs_cell_family",
        )

    filtered = [
        r
        for r in runs
        if ((r.extras or {}).get("battery") or "other") in (bat_sel or batteries)
        and ((r.extras or {}).get("family") or "other") in (fam_sel or fams)
    ]
    # Prefer not flooding with all B3 mid cells unless user picks B3
    if not filtered:
        st.warning("No cells match filters.")
        return

    by_key = {str(r.directory): r for r in filtered}
    keys = list(by_key.keys())
    selected_key = st.selectbox(
        "Cell",
        keys,
        format_func=lambda k: _format_cell_label(by_key[k]),
        key="cs_cell_select",
    )
    render(by_key[selected_key])


# ─── single cell ─────────────────────────────────────────────────────────────


def render(run: "data.RunInfo"):
    meta = run.extras or {}
    bat = meta.get("battery") or ""
    short = meta.get("short") or run.label
    st.subheader(short)
    st.caption(
        f"`{run.label}` · {bat or '—'} · "
        "arms: weighted / influenced / distracted · **not** CIP effectiveness"
    )

    summary = data.read_summary_json(run.summary_path)
    metrics_df = _read_bridge_metrics(run.metrics_path)

    # Exclusive sub-view (tabs would still build both panes every interaction)
    detail = st.radio(
        "Detail",
        ["Summary", "Metrics"],
        horizontal=True,
        label_visibility="collapsed",
        key=f"cs_cell_detail_{run.label}",
    )
    if detail == "Summary":
        _render_summary(summary)
    else:
        _render_metrics(metrics_df, summary, run)


def render_rates_report(path: Path):
    """B2 ablations / grid report (ablations/from_mve/*)."""
    st.subheader("B2 · Coupled end-of-run grid")
    st.caption(_rel_display(path))

    report = data.read_summary_json(path)
    if not report:
        st.warning("Could not read grid report.")
        return

    n_ok = report.get("n_ok")
    n_cells = report.get("n_cells")
    m1, m2, m3 = st.columns(3)
    m1.metric("Cells", n_cells if n_cells is not None else "—")
    m2.metric("OK", n_ok if n_ok is not None else "—")
    m3.metric(
        "k × B",
        f"{report.get('focus_caps')} × {report.get('budgets')}",
    )

    # Prefer CSV for charts (merged table)
    csv_sib = path.with_name("ablations.csv")
    df = None
    if csv_sib.is_file():
        try:
            df = pd.read_csv(csv_sib)
        except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
            df = None
    if df is None or df.empty:
        cells = report.get("cells") or []
        if cells:
            df = pd.DataFrame(cells)

    if df is not None and not df.empty:
        _render_ablations_summary(df)
        st.markdown("**Grid**")
        st.dataframe(
            _compact_ablations_table(df),
            use_container_width=True,
            hide_index=True,
        )

    readout = report.get("readout") or {}
    if readout:
        st.markdown("**Readout**")
        for k, v in readout.items():
            st.markdown(f"- **{charts.label(k)}:** {v}")

    for name in ("ablations.csv", "rates_multiseed.csv"):
        sib = path.with_name(name) if path.suffix == ".json" else path.parent / name
        if sib.is_file():
            st.download_button(
                f"Download {name}",
                data=sib.read_bytes(),
                file_name=name,
                mime="text/csv",
                key=f"dl_abl_{name}_{path.parent.name}",
            )


def render_probe_series(path: Path, embedded: bool = False):
    """B3/B4 trajectory: rates + compact table (no bool charts)."""
    if not embedded:
        st.subheader(_series_label(path))
        st.caption(_rel_display(path))
    try:
        df = pd.read_csv(path)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
        st.warning("Could not read protocol_probes.csv")
        return
    if df.empty:
        st.warning("No probe rows.")
        return

    summary = data.read_summary_json(path.parent / "summary.json")
    rates = (summary or {}).get("rates") or {}
    if rates and not embedded:
        cols = st.columns(min(4, len(rates)))
        for c, (k, v) in zip(cols, rates.items()):
            c.metric(charts.label(k), _fmt_rate(v))

    if "wage_applied" in df.columns and not embedded:
        n_w = int(df["wage_applied"].map(_as_bool_float).sum())
        st.caption(f"Wage applied on **{n_w}/{len(df)}** rows")

    # Budget filter when multi-B
    view = df
    if "budget" in df.columns:
        budgets = sorted(df["budget"].dropna().unique().tolist())
        if len(budgets) > 1:
            b_pick = st.selectbox(
                "Budget",
                ["all"] + budgets,
                key=f"probe_b_{path.parent.name}",
            )
            if b_pick != "all":
                view = df[df["budget"] == b_pick]

    st.dataframe(
        _compact_probe_table(view),
        use_container_width=True,
        hide_index=True,
    )

    if not embedded:
        st.download_button(
            "Download protocol_probes.csv",
            data=path.read_bytes(),
            file_name=f"{path.parent.name}_protocol_probes.csv",
            mime="text/csv",
            key=f"dl_probe_{path.parent.name}",
        )


# ─── ablations / probe tables ─────────────────────────────────────────────────


def _render_ablations_summary(df: pd.DataFrame):
    """Rate metrics only — booleans stay in the table."""
    i_col = _col(df, "influenced_solve", "influenced_solved")
    d_col = _col(df, "distracted_solve", "distracted_solved")
    w_col = _col(df, "weighted_solve", "weighted_solved")
    if not i_col:
        return
    rates = {
        "weighted": df[w_col].map(_as_bool_float).mean() if w_col else None,
        "influenced": df[i_col].map(_as_bool_float).mean(),
        "distracted": df[d_col].map(_as_bool_float).mean() if d_col else None,
    }
    rcols = st.columns(3)
    for c, (name, v) in zip(rcols, rates.items()):
        if v is not None:
            c.metric(f"{name} solve rate", f"{v:.0%}")


def _compact_ablations_table(df: pd.DataFrame) -> pd.DataFrame:
    """Readable grid: solve as T/F, rounded ms, drop noisy cols."""
    out = df.copy()
    for a, b in (
        ("influenced_solve", "influenced_solved"),
        ("distracted_solve", "distracted_solved"),
        ("weighted_solve", "weighted_solved"),
        ("influenced_beats_distracted", None),
    ):
        col = a if a in out.columns else b
        if col and col in out.columns:
            out[col] = out[col].map(_bool_letter)

    keep = [
        c
        for c in (
            "mode",
            "focus_cap",
            "budget",
            "scenario",
            "status",
            "query",
            "weighted_solve",
            "influenced_solve",
            "distracted_solve",
            "weighted_solved",
            "influenced_solved",
            "distracted_solved",
            "influenced_beats_distracted",
            "weighted_premises",
            "influenced_premises",
            "distracted_premises",
            "weighted_wall_ms",
            "influenced_wall_ms",
            "distracted_wall_ms",
            "focus_size",
            "query_af_overlap",
        )
        if c in out.columns
    ]
    out = out[keep]
    for c in out.columns:
        if c.endswith("_ms") or c == "query_af_overlap":
            out[c] = pd.to_numeric(out[c], errors="coerce").round(1)
    return out


def _compact_probe_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for a, b in (
        ("influenced_solved", "af_solved"),
        ("distracted_solved", "random_solved"),
        ("weighted_solved", "full_solved"),
        ("influenced_beats_distracted", None),
        ("wage_applied", None),
    ):
        col = a if a in out.columns else b
        if col and col in out.columns:
            out[col] = out[col].map(_bool_letter)

    if "query" in out.columns:
        out["query"] = out["query"].astype(str).str.replace(
            "Inheritance ", "", regex=False
        )

    keep = [
        c
        for c in (
            "cip_index",
            "budget",
            "focus_cap",
            "query",
            "weighted_solved",
            "influenced_solved",
            "distracted_solved",
            "influenced_beats_distracted",
            "weighted_n_premises",
            "influenced_n_premises",
            "distracted_n_premises",
            "weighted_wall_ms",
            "influenced_wall_ms",
            "distracted_wall_ms",
            "n_waged",
            "wage_applied",
            "wage_method",
            "query_af_overlap",
        )
        if c in out.columns
    ]
    out = out[keep]
    for c in out.columns:
        if c.endswith("_ms") or c == "query_af_overlap":
            out[c] = pd.to_numeric(out[c], errors="coerce").round(1)
    return out


# ─── summary / metrics (cell) ────────────────────────────────────────────────


def _read_bridge_metrics(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def _render_summary(summary: dict | None):
    if not summary:
        st.warning("summary.json could not be read.")
        return

    params = summary.get("parameters") or {}
    protocol = params.get("protocol") or summary.get("protocol") or "—"

    c0, c1, c2, c3 = st.columns(4)
    c0.metric("Protocol", str(protocol))
    c1.metric("Scenario", str(params.get("scenario") or params.get("fixture") or "—"))
    c2.metric("Budget B", _fmt(params.get("budget")))
    c3.metric("Seed", _fmt(params.get("random_seed") if params.get("random_seed") is not None else params.get("seed")))

    rates = summary.get("rates")
    if rates:
        st.markdown("**Rates**")
        rcols = st.columns(min(4, len(rates)))
        for c, (k, v) in zip(rcols, rates.items()):
            c.metric(charts.label(k), _fmt_rate(v) if _is_rate_key(k) else _fmt(v))

    contrast = summary.get("contrast")
    if contrast and not rates:
        st.markdown("**Contrast**")
        # Prefer key flags first
        prefer = [
            "influenced_beats_distracted",
            "influenced_premises",
            "distracted_premises",
            "weighted_premises",
            "query_af_overlap",
        ]
        keys = [k for k in prefer if k in contrast] + [
            k for k in contrast if k not in prefer
        ]
        ccols = st.columns(min(4, len(keys)))
        for c, k in zip(ccols, keys[:4]):
            v = contrast[k]
            c.metric(charts.label(k), _fmt(v) if not isinstance(v, bool) else str(v))

    arms = summary.get("arms")
    if arms:
        st.markdown("**Arms**")
        st.dataframe(_arms_table(arms), hide_index=True, use_container_width=True)

    fb = summary.get("feedback")
    pln = summary.get("pln")
    if fb or pln:
        st.markdown("**Feedback**")
        if pln:
            st.write(
                f"PLN solved={pln.get('solved')}  conf={_fmt(pln.get('confidence'))}  "
                f"stamps={pln.get('stamps')}"
            )
        if fb:
            fcols = st.columns(4)
            fcols[0].metric("Proof retained in AF", str(fb.get("proof_retained_in_af")))
            fcols[1].metric("STI gain sum", _fmt(fb.get("sti_gain_sum")))
            fcols[2].metric("|proof|", len(fb.get("proof_objects") or []))
            fcols[3].metric("|newly focused|", len(fb.get("newly_focused") or []))
            if fb.get("sti_gain"):
                with st.expander("STI gain by atom"):
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {"atom": k, "ΔSTI": v}
                                for k, v in fb["sti_gain"].items()
                            ]
                        ),
                        hide_index=True,
                        use_container_width=True,
                    )
            with st.expander("Focus before / after"):
                st.write("focus0:", fb.get("focus0"))
                st.write("focus1:", fb.get("focus1"))

    att = summary.get("attention") or {}
    if att.get("focus") or att.get("focus_seed") or att.get("distracted_S"):
        st.markdown("**Attention**")
        if att.get("query_af_overlap") is not None:
            st.metric("query_af_overlap", _fmt(att.get("query_af_overlap")))
        with st.expander("Focus sets", expanded=False):
            st.write("focus_seed:", att.get("focus_seed"))
            st.write("focus:", att.get("focus"))
            st.write("distracted_S:", att.get("distracted_S"))
            st.write("query_objects:", att.get("query_objects"))

    if params:
        with st.expander("Parameters", expanded=False):
            st.table({charts.label(k): str(v) for k, v in params.items()})

    duration = _duration(summary.get("run_timestamp"), summary.get("completed_at"))
    if duration:
        st.caption(f"Run duration: {duration}")


def _arms_table(arms: dict) -> pd.DataFrame:
    rows = []
    for name in ("weighted", "influenced", "distracted"):
        arm = arms.get(name) or arms.get(
            {"weighted": "full", "influenced": "af", "distracted": "random"}[name]
        ) or {}
        if not arm:
            continue
        rows.append(
            {
                "arm": name,
                "solved": _bool_letter(arm.get("solved")),
                "confidence": _fmt(arm.get("confidence")),
                "n_premises": arm.get("n_premises"),
                "wall_ms": _fmt(arm.get("wall_ms")),
            }
        )
    return pd.DataFrame(rows)


def _render_metrics(df: pd.DataFrame, summary: dict | None, run: "data.RunInfo"):
    if df.empty:
        st.warning("metrics.csv empty or unreadable.")
        return
    # Prefer compact bool display when arm columns present
    view = df.copy()
    for a, b in (
        ("influenced_solved", "af_solved"),
        ("distracted_solved", "random_solved"),
        ("weighted_solved", "full_solved"),
    ):
        col = a if a in view.columns else b
        if col and col in view.columns:
            view[col] = view[col].map(_bool_letter)
    st.dataframe(view, use_container_width=True, hide_index=True)


# ─── helpers ─────────────────────────────────────────────────────────────────


def _col(df: pd.DataFrame, new: str, old: str) -> str | None:
    if new in df.columns:
        return new
    if old in df.columns:
        return old
    return None


def _series_label(path: Path) -> str:
    name = path.parent.name
    meta = data.classify_cs_label(name)
    return meta.get("short") or name


def _rel_display(path: Path) -> str:
    """Path relative to CAIRN (or its output/) for UI — never the full machine path."""
    p = Path(path).resolve()
    cairn = Path(__file__).resolve().parent.parent  # …/CAIRN
    for base in (cairn, cairn / "output"):
        try:
            return str(p.relative_to(base.resolve()))
        except ValueError:
            continue
    # last resort: output/… fragment if present
    parts = p.parts
    if "output" in parts:
        i = parts.index("output")
        return "/".join(parts[i:])
    return p.name


def _format_cell_label(run: "data.RunInfo") -> str:
    badge = {"complete": "✅", "live": "🟢", "stale": "⚪"}.get(run.state, "")
    short = (run.extras or {}).get("short") or run.label
    return f"{badge} {short}"


def _as_bool_float(v):
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, str):
        return 1.0 if v.lower() in ("true", "1", "yes") else 0.0
    try:
        return 1.0 if float(v) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _bool_letter(v):
    """Compact T/F/— for tables (no charts)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    if isinstance(v, bool):
        return "T" if v else "F"
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "1", "yes", "t"):
            return "T"
        if s in ("false", "0", "no", "f"):
            return "F"
        return v
    try:
        return "T" if float(v) else "F"
    except (TypeError, ValueError):
        return str(v)


def _is_rate_key(k: str) -> bool:
    return "solve" in k or "beat" in k or "faster" in k or k.endswith("_rate")


def _fmt_rate(v):
    try:
        f = float(v)
        if 0.0 <= f <= 1.0:
            return f"{f:.0%}"
        return f"{f:.3f}"
    except (TypeError, ValueError):
        return str(v)


def _duration(start, end):
    if not start or not end:
        return None
    try:
        from datetime import datetime

        return str(datetime.fromisoformat(end) - datetime.fromisoformat(start))
    except ValueError:
        return None


def _fmt(v):
    if v is None or v == "":
        return "—"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    try:
        return f"{float(v):.3f}"
    except (TypeError, ValueError):
        return str(v)
