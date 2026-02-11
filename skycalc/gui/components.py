"""Reusable UI components for SkyCalc."""

import dash_bootstrap_components as dbc
from dash import html


def create_info_card(title: str, value: str, icon: str = None) -> dbc.Card:
    """Create an information card with title and value."""
    content = []
    if icon:
        content.append(html.I(className=f"{icon} me-2"))
    content.append(html.Span(value, className="fw-bold"))

    return dbc.Card(
        [
            dbc.CardHeader(title, className="py-1 small"),
            dbc.CardBody(content, className="py-2"),
        ],
        className="text-center",
    )


def create_target_badge(name: str, color: str, selected: bool = True) -> dbc.Badge:
    """Create a target badge with color indicator."""
    return dbc.Badge(
        [
            html.Span(
                style={
                    "display": "inline-block",
                    "width": "8px",
                    "height": "8px",
                    "borderRadius": "50%",
                    "backgroundColor": color,
                    "marginRight": "5px",
                }
            ),
            name,
        ],
        color="dark" if selected else "secondary",
        className="me-1 mb-1",
        style={"cursor": "pointer"},
    )


def create_limit_indicator(telescope) -> html.Div:
    """Create a visual indicator for telescope pointing limits."""
    items = []

    if telescope.min_altitude is not None:
        items.append(
            html.Div(
                [
                    html.Span("Min Alt: ", className="text-muted"),
                    html.Span(f"{telescope.min_altitude}°", className="fw-bold"),
                ],
                className="small",
            )
        )

    if telescope.max_altitude is not None and telescope.max_altitude < 90:
        items.append(
            html.Div(
                [
                    html.Span("Max Alt: ", className="text-muted"),
                    html.Span(f"{telescope.max_altitude}°", className="fw-bold"),
                ],
                className="small",
            )
        )

    if telescope.min_hour_angle is not None and telescope.max_hour_angle is not None:
        items.append(
            html.Div(
                [
                    html.Span("HA Range: ", className="text-muted"),
                    html.Span(
                        f"{telescope.min_hour_angle:+.1f}h to {telescope.max_hour_angle:+.1f}h",
                        className="fw-bold",
                    ),
                ],
                className="small",
            )
        )

    if not items:
        items.append(html.Span("No limits configured", className="text-muted small"))

    return html.Div(items)


def create_observability_badge(hours: float) -> dbc.Badge:
    """Create a colored badge based on observable hours."""
    if hours >= 6:
        color = "success"
        text = f"{hours:.1f}h"
    elif hours >= 3:
        color = "warning"
        text = f"{hours:.1f}h"
    elif hours > 0:
        color = "danger"
        text = f"{hours:.1f}h"
    else:
        color = "dark"
        text = "N/A"

    return dbc.Badge(text, color=color, className="ms-1")
