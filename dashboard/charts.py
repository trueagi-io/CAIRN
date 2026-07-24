"""Pure chart-building functions: DataFrame -> plotly Figure. No Streamlit imports."""

import plotly.graph_objects as go
from plotly.subplots import make_subplots

_CATEGORICAL = [
    '#8b5cf6', '#0891b2', '#db2777', '#d97706',
    '#3b82f6', '#0d9488', '#ea580c', '#6366f1',
]

_COLUMN_ORDER = [
    'af_size_ratio', 'sti_concentration', 'link_density',
    'effectiveness', 'local_effectiveness', 'metric_delta', 'resource_cost',

    'attention_coherence', 'context_retention',
    'connection_ratio', 'distributed_importance',
    'selective_modulation', 'preallocation_space',
    'af_size', 'triangles',
    'betti_0', 'betti_1', 'betti_2',
]
COLORS = {col: _CATEGORICAL[i % len(_CATEGORICAL)] for i, col in enumerate(_COLUMN_ORDER)}

SEQUENTIAL_CYAN = ['#164e63', '#155e75', '#0e7490', '#0891b2', '#22d3ee']

INTEGER_METRICS = frozenset({
    'cip_index', 'af_size', 'triangles', 'betti_0', 'betti_1', 'betti_2',
    'hebbian_links', 'attention_trajectory',
})


def _integer_dtick(series):
    span = series.max() - series.min()
    return max(1, round((span or 1) / 6))

STATUS_GOOD = '#4ade80'
STATUS_CRITICAL = '#f87171'
STATUS_NEUTRAL = '#9ca3af'

SURFACE = '#151822'
GRIDLINE = '#252838'
AXIS = '#3a3f52'
INK_PRIMARY = '#e5e7eb'
INK_MUTED = '#8b8fa3'

LABELS = {
    'cip_index': 'CIP', 'af_size': 'AF Size', 'af_size_ratio': 'AF Ratio',
    'sti_concentration': 'STI Concentration', 'link_density': 'Link Density',
    'effectiveness': 'Effectiveness (global)', 'local_effectiveness': 'Effectiveness (local)',
    'metric_delta': 'Metric Delta', 'resource_cost': 'Resources Cost',

    'attention_coherence': 'Coherence', 'context_retention': 'Context Retention',
    'distributed_importance': 'Distributed Importance', 'selective_modulation': 'Selective Modulation',
    'connection_ratio': 'Connection Ratio', 'preallocation_space': 'Preallocated Space',
    'triangles': 'Triangles', 'betti_0': 'Betti₀', 'betti_1': 'Betti₁', 'betti_2': 'Betti₂',
    'timestamp': 'Timestamp', 'hebbian_links': 'Hebbian Links',
    'af_stability_ratio': 'AF Stable Ratio', 'mean_af_volatility': 'Mean AF Volatility',
    'attention_trajectory': 'Attention Trajectory', 'cognitive_maintenance': 'Cognitive Maintenance',
    'glocal_coordination': 'Glocal Coordination',
    'baseline_mean_effectiveness': 'Baseline Mean Effectiveness',
    'optimized_mean_effectiveness': 'Optimized Mean Effectiveness', 'gained_efficiency': 'Gained Efficiency',
    'volatility': 'Volatility', 'trend': 'Trend', 'atom': 'Atom',
    'MAX_AF_SIZE': 'Max AF Size', 'TARGET_STI': 'Target STI', 'TARGET_LTI': 'Target LTI',
    'FUNDS_STI': 'Funds STI', 'FUNDS_LTI': 'Funds LTI', 'TOPK': 'Top K', 'batch_size': 'Batch Size',
}


def label(key):
    return LABELS.get(key, key.replace('_', ' ').title())


def _rgba(hex_color, alpha):
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f'rgba({r},{g},{b},{alpha})'


PLOTLY_CONFIG = {'displayModeBar': False}

_LAYOUT_DEFAULTS = dict(
    plot_bgcolor=SURFACE,
    paper_bgcolor=SURFACE,
    font=dict(color=INK_PRIMARY, family='system-ui, -apple-system, "Segoe UI", sans-serif'),
    margin=dict(l=40, r=20, t=36, b=70),
    hovermode='x unified',
    hoverlabel=dict(bgcolor=SURFACE, bordercolor=AXIS,
                     font=dict(color=INK_PRIMARY, family='system-ui, -apple-system, "Segoe UI", sans-serif')),
    legend=dict(orientation='h', yanchor='top', y=-0.25, xanchor='left', x=0),
)

_AXIS_DEFAULTS = dict(
    gridcolor=GRIDLINE,
    linecolor=AXIS,
    tickfont=dict(color=INK_MUTED),
)

CHART_HEIGHT = 340


def _x_values(df, x_col):
    """CIP as plain ints; timestamps left as-is (caller may have parsed them)."""
    if x_col not in df.columns:
        return df.index
    s = df[x_col]
    if x_col == 'cip_index':
        try:
            return s.astype('int64')
        except (TypeError, ValueError):
            return s
    return s


def _x_axis_kwargs(x_col, x_series=None):
    """CIP: integer ticks. Timestamp: clock. No axis title — Index toggle owns that."""
    kwargs = dict(title=None, **_AXIS_DEFAULTS)
    if x_col == 'cip_index':
        kwargs['tickformat'] = 'd'
        kwargs['tickmode'] = 'linear'
        kwargs['dtick'] = 1
        if x_series is not None and len(x_series):
            try:
                lo = int(min(x_series))
                hi = int(max(x_series))
                kwargs['tick0'] = lo
                span = hi - lo
                if span > 24:
                    kwargs['dtick'] = max(1, span // 12)
            except (TypeError, ValueError):
                pass
    elif x_col == 'timestamp':
        kwargs['tickformat'] = '%H:%M:%S'
        kwargs['tickangle'] = -30
    return kwargs


def _apply_layout(fig, title, x_col='cip_index', y_range=None, y_title=None, integer_y=None, x_series=None):
    fig.update_layout(title=dict(text=title, font=dict(size=14, color=INK_PRIMARY)),
                       height=CHART_HEIGHT, **_LAYOUT_DEFAULTS)
    fig.update_xaxes(**_x_axis_kwargs(x_col, x_series))
    y_kwargs = dict(title=y_title, range=y_range, **_AXIS_DEFAULTS)
    if integer_y is not None:
        y_kwargs['tickformat'] = 'd'
        y_kwargs['dtick'] = _integer_dtick(integer_y)
    fig.update_yaxes(**y_kwargs)
    return fig


def _line_panel(df, columns, title, x_col='cip_index', y_range=None, area_fill=False, integer_y=False):
    fig = go.Figure()
    xs = _x_values(df, x_col)
    for col in columns:
        if col not in df.columns:
            continue
        color = COLORS.get(col)
        hovertemplate = '%{y:d}<extra></extra>' if col in INTEGER_METRICS else '%{y:.3f}<extra></extra>'
        trace_kwargs = dict(
            x=xs, y=df[col], name=label(col),
            mode='lines+markers',
            line=dict(width=2, color=color),
            marker=dict(size=8, color=color),
            connectgaps=False,
            hovertemplate=hovertemplate,
        )
        if area_fill and len(columns) == 1:
            trace_kwargs['fill'] = 'tozeroy'
            trace_kwargs['fillgradient'] = dict(
                type='vertical',
                colorscale=[[0, _rgba(color, 0.0)], [1, _rgba(color, 0.28)]],
            )
        fig.add_trace(go.Scatter(**trace_kwargs))
    integer_series = df[columns[0]] if integer_y and columns and columns[0] in df.columns else None
    return _apply_layout(fig, title, x_col=x_col, y_range=y_range, integer_y=integer_series, x_series=xs)


def resource_ratios_chart(df, x_col='cip_index'):
    return _line_panel(df, ['af_size_ratio', 'sti_concentration', 'link_density'],
                        'Resources', x_col=x_col, y_range=[0, 1])


def effectiveness_chart(df, x_col='cip_index'):
    return _line_panel(df, ['effectiveness', 'local_effectiveness',
                             'metric_delta', 'resource_cost'],
                        'Effectiveness', x_col=x_col)


def coherence_retention_chart(df, x_col='cip_index'):
    return _line_panel(df, ['attention_coherence', 'context_retention',
                             'connection_ratio', 'distributed_importance'],
                        'Coherence & Retention', x_col=x_col)


def modulation_chart(df, x_col='cip_index'):
    return _line_panel(df, ['selective_modulation', 'preallocation_space'],
                        'Modulation', x_col=x_col)


def af_size_chart(df, x_col='cip_index'):
    return _line_panel(df, ['af_size'], 'AF size', x_col=x_col, area_fill=True, integer_y=True)


def triangles_chart(df, x_col='cip_index', log_scale=False):
    fig = _line_panel(df, ['triangles'], 'Triangles', x_col=x_col,
                       area_fill=not log_scale, integer_y=not log_scale)
    if log_scale:
        fig.update_yaxes(type='log')
    return fig


def betti_subplots_chart(df, x_col='cip_index'):
    betti_cols = ['betti_0', 'betti_1', 'betti_2']
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                         subplot_titles=tuple(label(c) for c in betti_cols),
                         vertical_spacing=0.14)
    xs = _x_values(df, x_col)
    x_kwargs = _x_axis_kwargs(x_col, xs)
    for i, col in enumerate(betti_cols, start=1):
        if col not in df.columns:
            continue
        fig.add_trace(go.Scatter(
            x=xs, y=df[col], name=label(col), mode='lines+markers',
            line=dict(width=2, color=COLORS.get(col)),
            marker=dict(size=8, color=COLORS.get(col)),
            connectgaps=False, showlegend=False,
            hovertemplate='%{y:d}<extra></extra>',
        ), row=i, col=1)
        fig.update_yaxes(tickformat='d', dtick=_integer_dtick(df[col]),
                          title_standoff=8, **_AXIS_DEFAULTS, row=i, col=1)
        # Ticks only on bottom row — avoids stacked CIP labels between panels.
        row_x = {**x_kwargs, 'showticklabels': (i == 3), 'title': None}
        fig.update_xaxes(**row_x, row=i, col=1)
    layout = {k: v for k, v in _LAYOUT_DEFAULTS.items() if k != 'hovermode'}
    layout['margin'] = dict(l=48, r=20, t=48, b=56)
    fig.update_layout(
        title=dict(text='Betti numbers', font=dict(size=14, color=INK_PRIMARY)),
        height=620,
        **layout,
    )
    fig.update_annotations(font=dict(size=12, color=INK_MUTED))
    return fig


def volatility_histogram(trends_df):
    fig = go.Figure(go.Histogram(x=trends_df['volatility'], marker=dict(color=SEQUENTIAL_CYAN[3]),
                                  hovertemplate='%{x:.3f}: %{y}<extra></extra>'))
    return _apply_layout(fig, 'Volatility distribution', x_col='volatility')


def trend_category_bar(trends_df):
    counts = trends_df['trend'].value_counts()
    order = [t for t in ['rising', 'stable', 'falling'] if t in counts.index]
    status_color = {'rising': STATUS_GOOD, 'stable': STATUS_NEUTRAL, 'falling': STATUS_CRITICAL}
    fig = go.Figure(go.Bar(
        x=order, y=[counts[t] for t in order],
        marker=dict(color=[status_color[t] for t in order]),
        hovertemplate='%{x}: %{y}<extra></extra>',
    ))
    return _apply_layout(fig, 'Trends', x_col='vs')
