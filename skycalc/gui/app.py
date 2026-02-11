"""Main Dash application for SkyCalc."""

import base64
import io
from datetime import date, datetime, timedelta
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from astropy.time import Time
from dash import dcc, html

from ..core.targets import targets_to_dataframe
from ..core.telescope import load_default_telescopes

# Load default telescopes
TELESCOPES = load_default_telescopes()

# Default empty targets (user uploads their own)
DEFAULT_TARGETS = []
DEFAULT_TARGET_OPTIONS = []
DEFAULT_TARGET_NAMES = []

# Initialize Dash app with Bootstrap theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True,
)

app.title = "SkyCalc - Airmass Plotter"

# Sidebar layout
sidebar = dbc.Card(
    [
        dbc.CardHeader(html.H4("Settings", className="mb-0")),
        dbc.CardBody(
            [
                # Telescope selector
                html.Label("Telescope", className="fw-bold"),
                dcc.Dropdown(
                    id="telescope-dropdown",
                    options=[
                        {"label": t.name, "value": tid}
                        for tid, t in TELESCOPES.items()
                    ],
                    value=list(TELESCOPES.keys())[0] if TELESCOPES else None,
                    className="mb-3",
                    style={"color": "#333"},
                ),
                # Date input
                html.Label("Observation Date", className="fw-bold"),
                dbc.Input(
                    id="date-picker",
                    type="date",
                    value=date.today().isoformat(),
                    className="mb-2",
                    style={"width": "100%"},
                ),
                # Start time input
                html.Label("Start Time (local)", className="fw-bold"),
                dbc.Input(
                    id="start-time",
                    type="time",
                    placeholder="HH:MM",
                    value="18:00",
                    className="mb-1",
                    style={"width": "100%"},
                ),
                html.Div(
                    "Default: 6:00 PM",
                    className="small text-muted mb-3",
                ),
                html.Hr(),
                # File upload
                html.Label("Target List (CSV)", className="fw-bold"),
                dcc.Upload(
                    id="upload-targets",
                    children=html.Div([
                        "Drag and Drop or ",
                        html.A("Select File", className="text-primary"),
                    ]),
                    style={
                        "width": "100%",
                        "height": "60px",
                        "lineHeight": "60px",
                        "borderWidth": "1px",
                        "borderStyle": "dashed",
                        "borderRadius": "5px",
                        "textAlign": "center",
                        "marginBottom": "10px",
                    },
                    multiple=False,
                ),
                html.Div(
                    id="upload-status",
                    className="small text-muted mb-3",
                ),
                html.Hr(),
                # Target selection
                html.Label("Select Targets", className="fw-bold"),
                html.Div(
                    id="target-checklist-container",
                    children=[
                        dcc.Checklist(
                            id="target-checklist",
                            options=DEFAULT_TARGET_OPTIONS,
                            value=DEFAULT_TARGET_NAMES,
                            labelStyle={"display": "block"},
                            className="mb-2",
                        ),
                    ],
                    style={"maxHeight": "200px", "overflowY": "auto"},
                ),
                html.Hr(),
                # Display options
                html.Label("Display Options", className="fw-bold"),
                dcc.Checklist(
                    id="display-options",
                    options=[
                        {"label": " Show twilight bands", "value": "twilight"},
                        {"label": " Show Moon altitude", "value": "moon"},
                        {"label": " Show pointing limits", "value": "limits"},
                        {"label": " Show current time", "value": "now"},
                    ],
                    value=["twilight", "limits"],
                    labelStyle={"display": "block"},
                    className="mb-3",
                ),
                html.Hr(),
                # Plot Options
                html.Label("Plot Options", className="fw-bold"),
                # Y-axis controls
                html.Div([
                    html.Label("Y-Axis (Airmass)", className="small text-muted"),
                    dbc.Row([
                        dbc.Col([
                            html.Label("Min", className="small"),
                            dbc.Input(
                                id="yaxis-min",
                                type="number",
                                value=1,
                                min=1,
                                max=5,
                                step=0.5,
                                size="sm",
                            ),
                        ], width=4),
                        dbc.Col([
                            html.Label("Max", className="small"),
                            dbc.Input(
                                id="yaxis-max",
                                type="number",
                                value=10,
                                min=2,
                                max=20,
                                step=1,
                                size="sm",
                            ),
                        ], width=4),
                        dbc.Col([
                            html.Label("Step", className="small"),
                            dbc.Input(
                                id="yaxis-step",
                                type="number",
                                value=2,
                                min=0.5,
                                max=5,
                                step=0.5,
                                size="sm",
                            ),
                        ], width=4),
                    ], className="mb-2"),
                ], className="mb-2"),
                # X-axis controls
                html.Div([
                    html.Label("X-Axis (Time Range)", className="small text-muted"),
                    dbc.Row([
                        dbc.Col([
                            html.Label("Hrs Before", className="small"),
                            dbc.Input(
                                id="xaxis-before",
                                type="number",
                                value=1,
                                min=0,
                                max=6,
                                step=1,
                                size="sm",
                            ),
                        ], width=4),
                        dbc.Col([
                            html.Label("Hrs After", className="small"),
                            dbc.Input(
                                id="xaxis-after",
                                type="number",
                                value=15,
                                min=6,
                                max=24,
                                step=1,
                                size="sm",
                            ),
                        ], width=4),
                        dbc.Col([
                            html.Label("Tick (min)", className="small"),
                            dbc.Input(
                                id="xaxis-tick-step",
                                type="number",
                                value=30,
                                min=15,
                                max=120,
                                step=15,
                                size="sm",
                            ),
                        ], width=4),
                    ], className="mb-2"),
                ], className="mb-3"),
            ],
        ),
    ],
    className="h-100",
)

# Main content layout
main_content = dbc.Card(
    [
        dbc.CardHeader(
            dbc.Row(
                [
                    dbc.Col(html.H4("Airmass Plot", className="mb-0"), width="auto"),
                    dbc.Col(
                        html.Div(id="telescope-info", className="text-muted small"),
                        width="auto",
                        className="ms-auto",
                    ),
                ],
                align="center",
            ),
        ),
        dbc.CardBody(
            [
                dcc.Loading(
                    id="loading-plot",
                    type="default",
                    children=[
                        dcc.Graph(
                            id="airmass-plot",
                            config={
                                "displayModeBar": True,
                                "toImageButtonOptions": {
                                    "format": "png",
                                    "filename": "airmass_plot",
                                    "height": 600,
                                    "width": 1200,
                                    "scale": 2,
                                },
                            },
                            style={"height": "500px"},
                        ),
                    ],
                ),
            ],
        ),
    ],
    className="h-100",
)

# Target table
target_table = dbc.Card(
    [
        dbc.CardHeader(html.H5("Target Summary", className="mb-0")),
        dbc.CardBody(
            [
                html.Div(
                    id="target-table-container",
                    children=[
                        html.P(
                            "Upload a CSV file to see target information.",
                            className="text-muted",
                        ),
                    ],
                ),
            ],
        ),
    ],
)

# App layout
app.layout = dbc.Container(
    [
        # Header
        dbc.Row(
            [
                dbc.Col(
                    html.H2("SkyCalc", className="text-primary mb-0"),
                    width="auto",
                ),
                dbc.Col(
                    html.Span(
                        "Interactive Airmass Plotter",
                        className="text-muted align-middle",
                    ),
                    width="auto",
                    className="ms-2 pt-2",
                ),
            ],
            className="mb-3 pt-3",
            align="center",
        ),
        # Main content
        dbc.Row(
            [
                dbc.Col(sidebar, width=3),
                dbc.Col(
                    [
                        main_content,
                        html.Div(className="mt-3"),
                        target_table,
                    ],
                    width=9,
                ),
            ],
            className="g-3",
        ),
        # Hidden storage for targets (preloaded with example data)
        dcc.Store(id="targets-store", data=DEFAULT_TARGETS),
    ],
    fluid=True,
    className="pb-4",
)


def get_app():
    """Get the Dash app instance."""
    return app
