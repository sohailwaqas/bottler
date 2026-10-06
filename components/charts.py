"""
components/charts.py — thin helpers shared by chart-heavy pages. The actual
chart figures are built per-module with plotly express / graph_objects so
each one can be tailored, but they all draw colors from here so red/orange/
yellow/green stay consistent everywhere a status is being plotted.
"""
import config

STATUS_COLOR = {
    "critical": config.COLORS["critical"],
    "warning": config.COLORS["warning"],
    "caution": config.COLORS["caution"],
    "ok": config.COLORS["ok"],
}


def colors_for_statuses(statuses: list[str]) -> list[str]:
    return [STATUS_COLOR.get(s, config.COLORS["primary"]) for s in statuses]


def base_layout_kwargs(title: str = None, height: int = 380):
    kw = dict(height=height, showlegend=True)
    if title:
        kw["title"] = title
    return kw
