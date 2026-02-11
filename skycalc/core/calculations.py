"""Astronomical calculations using Astropy and Astroplan."""

from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from astropy import units as u
from astropy.coordinates import AltAz, SkyCoord, get_body
from astropy.time import Time
from astroplan import Observer

from .telescope import TelescopeConfig


def compute_airmass_curve(
    target_coord: SkyCoord,
    observer: Observer,
    time_start: Time,
    time_end: Time,
    n_points: int = 100,
) -> pd.DataFrame:
    """
    Compute airmass curve for a target over a time range.

    Parameters
    ----------
    target_coord : SkyCoord
        Target coordinates
    observer : Observer
        Astroplan Observer object
    time_start : Time
        Start of time range
    time_end : Time
        End of time range
    n_points : int
        Number of time points to compute

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: time, airmass, altitude, azimuth, hour_angle
    """
    times = time_start + (time_end - time_start) * np.linspace(0, 1, n_points)

    # Compute AltAz frame for all times
    altaz_frame = AltAz(obstime=times, location=observer.location)
    target_altaz = target_coord.transform_to(altaz_frame)

    altitude = target_altaz.alt.deg
    azimuth = target_altaz.az.deg

    # Compute airmass using Pickering (2002) formula for accuracy near horizon
    # This is more accurate than sec(z) for large zenith angles
    airmass = compute_airmass(altitude)

    # Compute hour angle
    lst = observer.local_sidereal_time(times)
    hour_angle = (lst - target_coord.ra).wrap_at(12 * u.hour).hour

    return pd.DataFrame({
        "time": times.datetime,
        "airmass": airmass,
        "altitude": altitude,
        "azimuth": azimuth,
        "hour_angle": hour_angle,
    })


def compute_airmass(altitude_deg: np.ndarray) -> np.ndarray:
    """
    Compute true airmass using Pickering (2002) formula.

    More accurate than simple sec(z) especially near the horizon.

    Parameters
    ----------
    altitude_deg : array-like
        Altitude in degrees

    Returns
    -------
    np.ndarray
        Airmass values (NaN for negative altitudes)
    """
    altitude_deg = np.asarray(altitude_deg)
    airmass = np.full_like(altitude_deg, np.nan, dtype=float)

    # Only compute for positive altitudes
    mask = altitude_deg > 0
    alt = altitude_deg[mask]

    # Pickering (2002) formula - accurate to 0.003 airmass at horizon
    # X = 1 / sin(h + 244/(165 + 47*h^1.1))
    # where h is altitude in degrees
    arg = alt + 244.0 / (165.0 + 47.0 * alt**1.1)
    airmass[mask] = 1.0 / np.sin(np.radians(arg))

    return airmass


def compute_twilight_times(observer: Observer, date: Time) -> dict:
    """
    Compute twilight times for a given date, returned in local time.

    Parameters
    ----------
    observer : Observer
        Astroplan Observer object
    date : Time
        Date to compute twilight for (uses midnight of this date)

    Returns
    -------
    dict
        Dictionary with twilight times in LOCAL TIME:
        - sunset, sunrise
        - civil_evening, civil_morning
        - nautical_evening, nautical_morning
        - astronomical_evening, astronomical_morning
    """
    import pytz

    # Use noon of the given date as reference
    midnight = observer.midnight(date, which="next")

    # Get timezone for conversion - observer.timezone may be string or pytz object
    try:
        if isinstance(observer.timezone, str):
            tz = pytz.timezone(observer.timezone)
        else:
            tz = observer.timezone  # Already a pytz timezone object
    except Exception:
        tz = pytz.UTC

    def to_local(astro_time):
        """Convert Astropy Time to local datetime."""
        if astro_time is None:
            return None
        # Get UTC datetime, make it aware, convert to local, return naive local
        utc_dt = astro_time.to_datetime(timezone=pytz.UTC)
        local_dt = utc_dt.astimezone(tz)
        return local_dt.replace(tzinfo=None)  # Return naive datetime in local time

    twilights = {}

    try:
        twilights["sunset"] = to_local(observer.sun_set_time(midnight, which="previous"))
        twilights["sunrise"] = to_local(observer.sun_rise_time(midnight, which="next"))
    except Exception:
        twilights["sunset"] = None
        twilights["sunrise"] = None

    # Civil twilight (sun 6 degrees below horizon)
    try:
        twilights["civil_evening"] = to_local(observer.twilight_evening_civil(
            midnight, which="previous"
        ))
        twilights["civil_morning"] = to_local(observer.twilight_morning_civil(
            midnight, which="next"
        ))
    except Exception:
        twilights["civil_evening"] = None
        twilights["civil_morning"] = None

    # Nautical twilight (sun 12 degrees below horizon)
    try:
        twilights["nautical_evening"] = to_local(observer.twilight_evening_nautical(
            midnight, which="previous"
        ))
        twilights["nautical_morning"] = to_local(observer.twilight_morning_nautical(
            midnight, which="next"
        ))
    except Exception:
        twilights["nautical_evening"] = None
        twilights["nautical_morning"] = None

    # Astronomical twilight (sun 18 degrees below horizon)
    try:
        twilights["astronomical_evening"] = to_local(observer.twilight_evening_astronomical(
            midnight, which="previous"
        ))
        twilights["astronomical_morning"] = to_local(observer.twilight_morning_astronomical(
            midnight, which="next"
        ))
    except Exception:
        twilights["astronomical_evening"] = None
        twilights["astronomical_morning"] = None

    return twilights


def compute_moon_info(
    observer: Observer,
    time_start: Time,
    time_end: Time,
    n_points: int = 50,
) -> pd.DataFrame:
    """
    Compute Moon position and illumination over a time range.

    Parameters
    ----------
    observer : Observer
        Astroplan Observer object
    time_start : Time
        Start of time range
    time_end : Time
        End of time range
    n_points : int
        Number of time points

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: time, altitude, azimuth, illumination
    """
    times = time_start + (time_end - time_start) * np.linspace(0, 1, n_points)

    # Get Moon position
    moon = get_body("moon", times, location=observer.location)
    altaz_frame = AltAz(obstime=times, location=observer.location)
    moon_altaz = moon.transform_to(altaz_frame)

    # Compute illumination fraction
    sun = get_body("sun", times, location=observer.location)
    moon_sun_angle = moon.separation(sun)
    illumination = (1 - np.cos(moon_sun_angle.rad)) / 2

    return pd.DataFrame({
        "time": times.datetime,
        "altitude": moon_altaz.alt.deg,
        "azimuth": moon_altaz.az.deg,
        "illumination": illumination,
    })


def compute_moon_separation(
    target_coord: SkyCoord,
    observer: Observer,
    times: Time,
) -> np.ndarray:
    """
    Compute angular separation between target and Moon.

    Parameters
    ----------
    target_coord : SkyCoord
        Target coordinates
    observer : Observer
        Astroplan Observer object
    times : Time
        Array of times

    Returns
    -------
    np.ndarray
        Angular separation in degrees
    """
    moon = get_body("moon", times, location=observer.location)
    separation = target_coord.separation(moon)
    return separation.deg


def get_night_time_range(
    observer: Observer,
    date: Time,
    twilight: str = "astronomical",
) -> tuple[Time, Time]:
    """
    Get the start and end times for a night's observations.

    Parameters
    ----------
    observer : Observer
        Astroplan Observer object
    date : Time
        Date of observation (evening)
    twilight : str
        Type of twilight to use: 'civil', 'nautical', 'astronomical', or 'sunset'

    Returns
    -------
    tuple[Time, Time]
        Start and end times for the night
    """
    midnight = observer.midnight(date, which="next")

    if twilight == "sunset":
        start = observer.sun_set_time(midnight, which="previous")
        end = observer.sun_rise_time(midnight, which="next")
    elif twilight == "civil":
        start = observer.twilight_evening_civil(midnight, which="previous")
        end = observer.twilight_morning_civil(midnight, which="next")
    elif twilight == "nautical":
        start = observer.twilight_evening_nautical(midnight, which="previous")
        end = observer.twilight_morning_nautical(midnight, which="next")
    else:  # astronomical
        start = observer.twilight_evening_astronomical(midnight, which="previous")
        end = observer.twilight_morning_astronomical(midnight, which="next")

    return start, end


def check_pointing_limits(
    airmass_df: pd.DataFrame,
    telescope: TelescopeConfig,
) -> pd.Series:
    """
    Check if target violates pointing limits at each time.

    Parameters
    ----------
    airmass_df : pd.DataFrame
        DataFrame from compute_airmass_curve
    telescope : TelescopeConfig
        Telescope configuration with limits

    Returns
    -------
    pd.Series
        Boolean series, True where target is observable (within limits)
    """
    observable = pd.Series(True, index=airmass_df.index)

    # Check altitude limits
    if telescope.min_altitude is not None:
        observable &= airmass_df["altitude"] >= telescope.min_altitude
    if telescope.max_altitude is not None:
        observable &= airmass_df["altitude"] <= telescope.max_altitude

    # Check hour angle limits
    if telescope.min_hour_angle is not None:
        observable &= airmass_df["hour_angle"] >= telescope.min_hour_angle
    if telescope.max_hour_angle is not None:
        observable &= airmass_df["hour_angle"] <= telescope.max_hour_angle

    return observable
