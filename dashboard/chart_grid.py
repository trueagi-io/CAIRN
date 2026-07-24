"""Shared 3-section chart layout, used by both live_view.py and
completed_view.py so they can never visually drift apart. charts.py stays
Streamlit-free (pure, testable); this module owns layout/composition."""

import streamlit as st

import charts


def _section(title):
    container = st.container(border=True)
    with container:
        st.markdown(f'<div class="cairn-section-title">{title}</div>', unsafe_allow_html=True)
    return container


def render(df, x_col, key_prefix):
    """The 3-section, 7-chart grid shared by the live and completed views."""
    with _section('Resource & Effectiveness'):
        st.plotly_chart(charts.resource_ratios_chart(df, x_col=x_col), use_container_width=True, config=charts.PLOTLY_CONFIG)
        st.plotly_chart(charts.effectiveness_chart(df, x_col=x_col), use_container_width=True, config=charts.PLOTLY_CONFIG)

    with _section('Coherence & Importance'):
        st.plotly_chart(charts.coherence_retention_chart(df, x_col=x_col), use_container_width=True, config=charts.PLOTLY_CONFIG)
        st.plotly_chart(charts.modulation_chart(df, x_col=x_col), use_container_width=True, config=charts.PLOTLY_CONFIG)

    with _section('Attention & Topology'):
        st.plotly_chart(charts.af_size_chart(df, x_col=x_col), use_container_width=True, config=charts.PLOTLY_CONFIG)
        log_toggle = st.checkbox('Log scale', key=f'{key_prefix}_triangles_log')
        st.plotly_chart(charts.triangles_chart(df, x_col=x_col, log_scale=log_toggle), use_container_width=True, config=charts.PLOTLY_CONFIG)
        st.plotly_chart(charts.betti_subplots_chart(df, x_col=x_col), use_container_width=True, config=charts.PLOTLY_CONFIG)
