"""Dash callbacks for SkyCalc interactivity."""

import base64
import io
import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time
from dash import Input, Output, State, callback, html
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from ..core.calculations import (
    check_pointing_limits,
    compute_airmass_curve,
    compute_moon_info,
    compute_twilight_times,
    get_night_time_range,
)
from ..core.targets import Target, load_targets, targets_to_dataframe
from ..core.telescope import load_default_telescopes

# Load telescopes
TELESCOPES = load_default_telescopes()

# Color palette for targets
COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
]


def register_callbacks(app):
    """Register all callbacks with the Dash app."""

    @app.callback(
        Output("targets-store", "data"),
        Output("upload-status", "children"),
        Output("target-checklist", "options"),
        Output("target-checklist", "value"),
        Input("upload-targets", "contents"),
        State("upload-targets", "filename"),
    )
    def parse_uploaded_file(contents, filename):
        """Parse uploaded CSV file and store targets."""
        if contents is None:
            raise PreventUpdate

        # Decode the uploaded file
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string)

        try:
            # Parse CSV
            df = pd.read_csv(io.StringIO(decoded.decode("utf-8")), comment="#")

            # Try to load as targets
            with io.StringIO(decoded.decode("utf-8")) as f:
                # Write to temp file-like object
                temp_file = io.StringIO(decoded.decode("utf-8"))
                # Save to temp file for load_targets
                import tempfile
                with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tf:
                    tf.write(decoded.decode("utf-8"))
                    temp_path = tf.name

            targets = load_targets(temp_path)

            # Serialize targets for storage (convert numpy types to Python types)
            targets_data = [
                {
                    "name": t.name,
                    "ra_deg": float(t.coord.ra.deg),
                    "dec_deg": float(t.coord.dec.deg),
                    "priority": int(t.priority) if t.priority else 1,
                    "magnitude": float(t.magnitude) if t.magnitude else None,
                    "target_type": t.target_type,
                }
                for t in targets
            ]

            # Create checklist options
            options = [
                {"label": f" {t['name']}", "value": t["name"]}
                for t in targets_data
            ]

            # Select all by default
            selected = [t["name"] for t in targets_data]

            status = html.Span(
                [
                    html.I(className="fas fa-check-circle text-success me-1"),
                    f"Loaded {len(targets)} targets from {filename}",
                ],
            )

            # Clean up temp file
            import os
            os.unlink(temp_path)

            return targets_data, status, options, selected

        except Exception as e:
            status = html.Span(
                [
                    html.I(className="fas fa-exclamation-circle text-danger me-1"),
                    f"Error: {str(e)}",
                ],
            )
            return None, status, [], []

    @app.callback(
        Output("telescope-info", "children"),
        Input("telescope-dropdown", "value"),
    )
    def update_telescope_info(telescope_id):
        """Update telescope information display."""
        if telescope_id is None or telescope_id not in TELESCOPES:
            return ""

        tel = TELESCOPES[telescope_id]
        lat_str = f"{abs(tel.latitude):.2f}° {'N' if tel.latitude >= 0 else 'S'}"
        lon_str = f"{abs(tel.longitude):.2f}° {'W' if tel.longitude < 0 else 'E'}"

        limits_str = ""
        if tel.min_altitude is not None:
            limits_str += f"Alt ≥ {tel.min_altitude}°"
        if tel.min_hour_angle is not None and tel.max_hour_angle is not None:
            if limits_str:
                limits_str += ", "
            # Format HA limits as HH:MM
            def fmt_ha(ha):
                sign = "+" if ha >= 0 else "-"
                ha_abs = abs(ha)
                h = int(ha_abs)
                m = int((ha_abs - h) * 60)
                return f"{sign}{h}:{m:02d}"
            limits_str += f"HA: {fmt_ha(tel.min_hour_angle)} to {fmt_ha(tel.max_hour_angle)}"

        return f"{lat_str}, {lon_str} | Elev: {tel.elevation}m | {limits_str}"

    @app.callback(
        Output("airmass-plot", "figure"),
        Input("telescope-dropdown", "value"),
        Input("date-picker", "date"),
        Input("start-time", "value"),
        Input("target-checklist", "value"),
        Input("display-options", "value"),
        Input("airmass-limit", "value"),
        State("targets-store", "data"),
    )
    def update_airmass_plot(
        telescope_id,
        obs_date,
        start_time_str,
        selected_targets,
        display_options,
        airmass_limit,
        targets_data,
    ):
        """Update the airmass plot."""
        if telescope_id is None or telescope_id not in TELESCOPES:
            fig = go.Figure()
            fig.update_layout(template="plotly_dark")
            fig.add_annotation(
                text="Select a telescope",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20, color="gray"),
            )
            return fig

        telescope = TELESCOPES[telescope_id]
        observer = telescope.observer

        # Parse observation date (HTML5 date input gives YYYY-MM-DD string)
        if obs_date is None or obs_date == "":
            obs_date = datetime.now()
        elif isinstance(obs_date, str):
            # Handle YYYY-MM-DD format from HTML5 date input
            try:
                # Remove any time component
                date_str = obs_date.split("T")[0].strip()
                parts = date_str.split("-")
                if len(parts) == 3:
                    obs_date = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                else:
                    obs_date = datetime.fromisoformat(date_str)
            except (ValueError, IndexError):
                obs_date = datetime.now()

        # Get night time range
        obs_time = Time(obs_date)
        try:
            time_start, time_end = get_night_time_range(observer, obs_time, twilight="sunset")
        except Exception:
            # Fallback if twilight calculation fails
            midnight = observer.midnight(obs_time, which="next")
            time_start = midnight - 6 * u.hour
            time_end = midnight + 6 * u.hour

        # Override start time if provided (HTML5 time input gives HH:MM string)
        if start_time_str and start_time_str.strip():
            try:
                # Parse HH:MM format
                time_parts = start_time_str.strip().split(":")
                if len(time_parts) >= 1:
                    hh = int(time_parts[0])
                    mm = int(time_parts[1]) if len(time_parts) > 1 else 0
                    custom_start = datetime(obs_date.year, obs_date.month, obs_date.day, hh, mm)
                    time_start = Time(custom_start)
            except (ValueError, IndexError):
                pass  # Keep default sunset time

        # Set plot range: 1 hour before start, 15 hours after start (16 hour window)
        plot_start = time_start - 1 * u.hour
        plot_end = time_start + 15 * u.hour

        # Convert to datetime for plotting
        start_dt = plot_start.datetime
        end_dt = plot_end.datetime

        # Generate 30-minute tick values for grid lines
        # Round to nearest 30 min
        tick_start = start_dt.replace(second=0, microsecond=0)
        if tick_start.minute < 30:
            tick_start = tick_start.replace(minute=0)
        else:
            tick_start = tick_start.replace(minute=30)
        if tick_start < start_dt:
            tick_start = tick_start + timedelta(minutes=30)

        tick_vals = []
        tick_text = []
        current = tick_start
        while current <= end_dt:
            tick_vals.append(current)
            # Show HH:MM for all ticks
            tick_text.append(current.strftime("%H:%M"))
            current = current + timedelta(minutes=30)

        # Create figure with proper time axis
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(30,30,30,0.8)",
            margin=dict(l=70, r=70, t=100, b=70),
            xaxis_title="Local Time",
            yaxis_title="Airmass",
            font=dict(size=14),  # Base font size
            yaxis=dict(
                autorange="reversed",  # Airmass increases downward
                range=[1.0, airmass_limit],
                gridcolor="rgba(100,100,100,0.4)",
                dtick=2.0,  # Airmass grid every 2
                tick0=1.0,  # Start ticks at 1
                tickfont=dict(size=13),
                title_font=dict(size=15),
            ),
            xaxis=dict(
                gridcolor="rgba(100,100,100,0.4)",
                range=[start_dt, end_dt],
                tickmode="array",
                tickvals=tick_vals,
                ticktext=tick_text,
                tickangle=45,
                tickfont=dict(size=11),
                title_font=dict(size=15),
            ),
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=1.02,
                font=dict(size=12),
            ),
            hovermode="x unified",
            hoverlabel=dict(
                bgcolor="rgba(30, 30, 30, 0.95)",
                font_size=13,
                font_color="white",
                bordercolor="rgba(100, 100, 100, 0.8)",
            ),
        )

        # Add twilight bands if enabled
        if "twilight" in display_options:
            twilights = compute_twilight_times(observer, obs_time)
            _add_twilight_bands(fig, twilights, start_dt, end_dt, airmass_limit)

        # Add pointing limit shading if enabled
        if "limits" in display_options:
            _add_limit_shading(fig, telescope, start_dt, end_dt, airmass_limit)

        # Add current time line if enabled
        if "now" in display_options:
            now = datetime.now()
            if start_dt <= now <= end_dt:
                fig.add_vline(
                    x=now,
                    line_dash="dash",
                    line_color="yellow",
                    annotation_text="Now",
                    annotation_position="top",
                )

        # Plot targets
        if targets_data and selected_targets:
            for i, target_data in enumerate(targets_data):
                if target_data["name"] not in selected_targets:
                    continue

                # Reconstruct SkyCoord
                coord = SkyCoord(
                    ra=target_data["ra_deg"] * u.deg,
                    dec=target_data["dec_deg"] * u.deg,
                    frame="icrs",
                )

                # Compute airmass curve over full plot range
                airmass_df = compute_airmass_curve(
                    coord, observer, plot_start, plot_end, n_points=150
                )

                # Check pointing limits
                observable = check_pointing_limits(airmass_df, telescope)

                color = COLORS[i % len(COLORS)]

                # Plot observable portions as solid
                obs_df = airmass_df[observable]
                if not obs_df.empty:
                    fig.add_trace(
                        go.Scatter(
                            x=obs_df["time"],
                            y=obs_df["airmass"],
                            mode="lines",
                            name=target_data["name"],
                            line=dict(color=color, width=2),
                            hovertemplate=(
                                f"<b style='color:white;font-size:14px'>{target_data['name']}</b><br>"
                                "<span style='color:#eee'>Time: %{x|%H:%M}</span><br>"
                                "<span style='color:#eee'>Airmass: %{y:.2f}</span><br>"
                                "<span style='color:#eee'>Alt: %{customdata[0]:.1f}°</span><br>"
                                "<span style='color:#eee'>Az: %{customdata[1]:.1f}°</span><br>"
                                "<span style='color:#eee'>HA: %{customdata[2]:.2f}h</span>"
                                "<extra></extra>"
                            ),
                            customdata=np.column_stack([
                                obs_df["altitude"],
                                obs_df["azimuth"],
                                obs_df["hour_angle"],
                            ]),
                        )
                    )

                # Plot unobservable portions as dashed with hover info
                if "limits" in display_options:
                    unobs_df = airmass_df[~observable]
                    if not unobs_df.empty:
                        # Determine why each point is unobservable
                        limit_reasons = []
                        for _, row in unobs_df.iterrows():
                            reasons = []
                            if telescope.min_altitude and row["altitude"] < telescope.min_altitude:
                                reasons.append(f"Alt {row['altitude']:.1f}° < {telescope.min_altitude}°")
                            if telescope.min_hour_angle and row["hour_angle"] < telescope.min_hour_angle:
                                reasons.append(f"HA {row['hour_angle']:.2f}h < {telescope.min_hour_angle:.2f}h (E limit)")
                            if telescope.max_hour_angle and row["hour_angle"] > telescope.max_hour_angle:
                                reasons.append(f"HA {row['hour_angle']:.2f}h > {telescope.max_hour_angle:.2f}h (W limit)")
                            limit_reasons.append("; ".join(reasons) if reasons else "Outside limits")

                        fig.add_trace(
                            go.Scatter(
                                x=unobs_df["time"],
                                y=unobs_df["airmass"],
                                mode="lines",
                                name=f"{target_data['name']} (outside limits)",
                                line=dict(color=color, width=1, dash="dot"),
                                opacity=0.5,
                                showlegend=False,
                                hovertemplate=(
                                    f"<b style='color:#ffaa66;font-size:14px'>{target_data['name']}</b> <span style='color:#ff6b6b'>(OUTSIDE LIMITS)</span><br>"
                                    "<span style='color:#eee'>Time: %{x|%H:%M}</span><br>"
                                    "<span style='color:#eee'>Airmass: %{y:.2f}</span><br>"
                                    "<span style='color:#eee'>HA: %{customdata[0]:.2f}h</span><br>"
                                    "<span style='color:#ff6b6b'>%{customdata[1]}</span>"
                                    "<extra></extra>"
                                ),
                                customdata=np.column_stack([
                                    unobs_df["hour_angle"],
                                    limit_reasons,
                                ]),
                            )
                        )

        # Add moon if enabled
        if "moon" in display_options:
            moon_df = compute_moon_info(observer, plot_start, plot_end, n_points=80)
            # Normalize moon altitude to airmass scale (just for visualization)
            moon_airmass_equiv = 1 + (90 - moon_df["altitude"].clip(0, 90)) / 30

            fig.add_trace(
                go.Scatter(
                    x=moon_df["time"],
                    y=moon_airmass_equiv,
                    mode="lines",
                    name="Moon",
                    line=dict(color="silver", width=2, dash="dash"),
                    hovertemplate=(
                        "<b style='color:silver;font-size:14px'>Moon</b><br>"
                        "<span style='color:#eee'>Time: %{x|%H:%M}</span><br>"
                        "<span style='color:#eee'>Alt: %{customdata[0]:.1f}°</span><br>"
                        "<span style='color:#eee'>Illum: %{customdata[1]:.0%}</span>"
                        "<extra></extra>"
                    ),
                    customdata=np.column_stack([
                        moon_df["altitude"],
                        moon_df["illumination"],
                    ]),
                )
            )

        if not targets_data or not selected_targets:
            fig.add_annotation(
                text="Upload a target list and select targets to plot",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray"),
            )

        # Add UT and LST axes at the top
        _add_ut_lst_axes(fig, observer, plot_start, plot_end)

        return fig

    @app.callback(
        Output("target-table-container", "children"),
        Input("targets-store", "data"),
        Input("telescope-dropdown", "value"),
        Input("date-picker", "date"),
    )
    def update_target_table(targets_data, telescope_id, obs_date):
        """Update the target summary table."""
        if not targets_data:
            return html.P(
                "Upload a CSV file to see target information.",
                className="text-muted",
            )

        if telescope_id is None or telescope_id not in TELESCOPES:
            return html.P("Select a telescope to compute observability.", className="text-muted")

        telescope = TELESCOPES[telescope_id]
        observer = telescope.observer

        # Parse observation date
        if isinstance(obs_date, str):
            obs_date = datetime.fromisoformat(obs_date)

        obs_time = Time(obs_date)

        # Compute observability metrics for each target
        rows = []
        for t in targets_data:
            coord = SkyCoord(ra=t["ra_deg"] * u.deg, dec=t["dec_deg"] * u.deg, frame="icrs")

            try:
                time_start, time_end = get_night_time_range(observer, obs_time, twilight="astronomical")
                airmass_df = compute_airmass_curve(coord, observer, time_start, time_end, n_points=50)
                observable = check_pointing_limits(airmass_df, telescope)

                # Compute metrics
                obs_airmass = airmass_df.loc[observable, "airmass"]
                if not obs_airmass.empty:
                    min_airmass = obs_airmass.min()
                    obs_hours = len(obs_airmass) / 50 * (time_end - time_start).to(u.hour).value
                else:
                    min_airmass = float("nan")
                    obs_hours = 0.0
            except Exception:
                min_airmass = float("nan")
                obs_hours = 0.0

            ra_str = f"{t['ra_deg'] / 15:.4f}h"
            dec_str = f"{t['dec_deg']:+.4f}°"

            rows.append({
                "Name": t["name"],
                "RA": ra_str,
                "Dec": dec_str,
                "Priority": t.get("priority", 1),
                "Best Airmass": f"{min_airmass:.2f}" if not np.isnan(min_airmass) else "N/A",
                "Observable Hours": f"{obs_hours:.1f}h" if obs_hours > 0 else "—",
            })

        df = pd.DataFrame(rows)

        table = dbc.Table.from_dataframe(
            df,
            striped=True,
            bordered=True,
            hover=True,
            size="sm",
            className="mb-0",
        )

        return table


def _add_twilight_bands(fig, twilights, time_start, time_end, airmass_limit):
    """Add twilight lines to the plot (no shading, just annotated lines)."""

    # Sunset line
    if twilights.get("sunset"):
        fig.add_vline(x=twilights["sunset"], line_dash="solid",
                      line_color="rgba(255, 150, 50, 0.8)", line_width=2)
        fig.add_annotation(
            x=twilights["sunset"], y=1.0, yref="y",
            text="Sunset", showarrow=False,
            font=dict(size=10, color="orange"),
            yanchor="bottom", xanchor="center",
        )

    # Sunrise line
    if twilights.get("sunrise"):
        fig.add_vline(x=twilights["sunrise"], line_dash="solid",
                      line_color="rgba(255, 150, 50, 0.8)", line_width=2)
        fig.add_annotation(
            x=twilights["sunrise"], y=1.0, yref="y",
            text="Sunrise", showarrow=False,
            font=dict(size=10, color="orange"),
            yanchor="bottom", xanchor="center",
        )

    # -12° twilight lines (nautical)
    if twilights.get("nautical_evening"):
        fig.add_vline(x=twilights["nautical_evening"], line_dash="dash",
                      line_color="rgba(150, 100, 255, 0.7)", line_width=1)
        fig.add_annotation(
            x=twilights["nautical_evening"], y=1.0, yref="y",
            text="-12°", showarrow=False,
            font=dict(size=9, color="mediumpurple"),
            yanchor="bottom", xanchor="center",
        )
    if twilights.get("nautical_morning"):
        fig.add_vline(x=twilights["nautical_morning"], line_dash="dash",
                      line_color="rgba(150, 100, 255, 0.7)", line_width=1)
        fig.add_annotation(
            x=twilights["nautical_morning"], y=1.0, yref="y",
            text="-12°", showarrow=False,
            font=dict(size=9, color="mediumpurple"),
            yanchor="bottom", xanchor="center",
        )

    # -18° twilight lines (astronomical)
    if twilights.get("astronomical_evening"):
        fig.add_vline(x=twilights["astronomical_evening"], line_dash="dot",
                      line_color="rgba(100, 100, 200, 0.7)", line_width=1)
        fig.add_annotation(
            x=twilights["astronomical_evening"], y=1.0, yref="y",
            text="-18°", showarrow=False,
            font=dict(size=9, color="slateblue"),
            yanchor="bottom", xanchor="center",
        )
    if twilights.get("astronomical_morning"):
        fig.add_vline(x=twilights["astronomical_morning"], line_dash="dot",
                      line_color="rgba(100, 100, 200, 0.7)", line_width=1)
        fig.add_annotation(
            x=twilights["astronomical_morning"], y=1.0, yref="y",
            text="-18°", showarrow=False,
            font=dict(size=9, color="slateblue"),
            yanchor="bottom", xanchor="center",
        )


def _add_limit_shading(fig, telescope, time_start, time_end, airmass_limit):
    """Add shading to indicate pointing limit violations."""
    # Add horizontal line at min altitude airmass if applicable
    if telescope.min_altitude is not None:
        # Compute airmass at min altitude
        from ..core.calculations import compute_airmass
        min_alt_airmass = compute_airmass(np.array([telescope.min_altitude]))[0]
        if min_alt_airmass < airmass_limit:
            fig.add_hline(
                y=min_alt_airmass,
                line_dash="dash",
                line_color="rgba(255, 100, 100, 0.5)",
                annotation_text=f"Alt limit ({telescope.min_altitude}°)",
                annotation_position="bottom right",
            )

            # Shade below limit
            fig.add_hrect(
                y0=min_alt_airmass,
                y1=airmass_limit,
                fillcolor="rgba(255, 100, 100, 0.1)",
                layer="below",
                line_width=0,
            )

    # Add HA limits annotation if applicable
    if telescope.min_hour_angle is not None or telescope.max_hour_angle is not None:
        ha_text_parts = []
        if telescope.min_hour_angle is not None:
            # Convert to HH:MM format
            ha_min_h = int(telescope.min_hour_angle)
            ha_min_m = int(abs(telescope.min_hour_angle - ha_min_h) * 60)
            ha_text_parts.append(f"E: {ha_min_h:+d}h{ha_min_m:02d}m")
        if telescope.max_hour_angle is not None:
            ha_max_h = int(telescope.max_hour_angle)
            ha_max_m = int(abs(telescope.max_hour_angle - ha_max_h) * 60)
            ha_text_parts.append(f"W: +{ha_max_h}h{ha_max_m:02d}m")

        ha_text = "HA Limits: " + ", ".join(ha_text_parts)

        fig.add_annotation(
            text=ha_text,
            xref="paper", yref="paper",
            x=0.01, y=0.01,
            showarrow=False,
            font=dict(size=11, color="rgba(255, 150, 150, 0.9)"),
            bgcolor="rgba(50, 50, 50, 0.7)",
            bordercolor="rgba(255, 100, 100, 0.5)",
            borderwidth=1,
            borderpad=4,
            xanchor="left",
            yanchor="bottom",
        )


def _add_ut_lst_axes(fig, observer, time_start, time_end):
    """Add UT and LST time axes at the top of the plot."""
    from astropy.time import Time as AstroTime
    import pytz

    # Get timezone offset from observer - may be string or pytz object
    try:
        if isinstance(observer.timezone, str):
            tz = pytz.timezone(observer.timezone)
        else:
            tz = observer.timezone  # Already a pytz timezone object
    except Exception:
        tz = pytz.UTC

    # Generate 2-hourly tick positions
    start_dt = time_start.datetime
    end_dt = time_end.datetime

    # Round to nearest even hour for clean ticks
    current = start_dt.replace(minute=0, second=0, microsecond=0)
    if current.hour % 2 != 0:
        current = current + timedelta(hours=1)
    if current < start_dt:
        current = current + timedelta(hours=2)

    tick_times = []
    while current <= end_dt:
        tick_times.append(current)
        current = current + timedelta(hours=2)

    if not tick_times:
        return

    # Compute UT and LST for each tick
    ut_labels = []
    lst_labels = []

    for local_time in tick_times:
        # Create astropy Time object
        astro_time = AstroTime(local_time)

        # Get UT by applying timezone offset
        # Assume local_time is in observer's timezone
        try:
            local_aware = tz.localize(local_time)
            ut_time = local_aware.astimezone(pytz.UTC)
            ut_labels.append(ut_time.strftime("%H:%M"))
        except Exception:
            # Fallback: just show the time
            ut_labels.append(local_time.strftime("%H:%M"))

        # Compute LST
        try:
            lst = observer.local_sidereal_time(astro_time)
            lst_hours = lst.hour
            lst_h = int(lst_hours)
            lst_m = int((lst_hours - lst_h) * 60)
            lst_labels.append(f"{lst_h:02d}:{lst_m:02d}")
        except Exception:
            lst_labels.append("--:--")

    # Calculate x positions as fraction of plot width
    total_duration = (end_dt - start_dt).total_seconds()
    if total_duration <= 0:
        return

    # Add shaded background for UT/LST axes
    fig.add_shape(
        type="rect",
        xref="paper", yref="paper",
        x0=0, x1=1,
        y0=1.0, y1=1.14,
        fillcolor="rgba(40, 50, 70, 0.8)",
        line=dict(width=0),
        layer="below",
    )

    # Add axis labels
    fig.add_annotation(
        text="UT",
        xref="paper", yref="paper",
        x=-0.04, y=1.10,
        showarrow=False,
        font=dict(size=12, color="cyan", family="monospace"),
        xanchor="right",
    )
    fig.add_annotation(
        text="LST",
        xref="paper", yref="paper",
        x=-0.04, y=1.04,
        showarrow=False,
        font=dict(size=12, color="orange", family="monospace"),
        xanchor="right",
    )

    # Add tick labels at the top
    for i, local_time in enumerate(tick_times):
        x_frac = (local_time - start_dt).total_seconds() / total_duration

        # UT label (top row)
        fig.add_annotation(
            text=ut_labels[i],
            xref="paper", yref="paper",
            x=x_frac, y=1.10,
            showarrow=False,
            font=dict(size=11, color="cyan", family="monospace"),
            xanchor="center",
        )

        # LST label (second row)
        fig.add_annotation(
            text=lst_labels[i],
            xref="paper", yref="paper",
            x=x_frac, y=1.04,
            showarrow=False,
            font=dict(size=11, color="orange", family="monospace"),
            xanchor="center",
        )
